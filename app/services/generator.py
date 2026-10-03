"""出卷引擎。

流程：读知识图谱 → 按卷面配额(cell)抽题 → 注入随机参数 → 代码算答案 →
渲染题干/选项/图形 → 体检 → 未过则换题重抽 → 落库。

答案的正确性来自机制而非运气：所有答案都由 answer_expr 在 Python 里算出来，
不经过任何模型生成环节。
"""
from __future__ import annotations

import json
import random
import re
import uuid
from fractions import Fraction
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import MODULE_LABELS, settings
from app.services import qa_checker
from app.services.renderer import (  # noqa: E401
    evaluate_answer, fmt_answer, roll_params, safe_eval, substitute,
)


# --------------------------------------------------------------------------
# 知识图谱
# --------------------------------------------------------------------------
def load_graph(path: Path | None = None) -> dict:
    path = path or settings.graph_yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_bank(bank_dir: Path | None = None) -> list[dict]:
    """从 data/bank/*.jsonc 读取题库。

    题库选择 JSONC 而非 Python 源码，原因见 SKILL 复盘：
    Python 源码里中文题干常带引号，一旦字符串被内部引号截断就是 SyntaxError，
    要靠正则修补永远追不上；JSON 的引号语义唯一，且有标准库可严格校验。
    本函数加载时会做一次强制校验，任何结构问题立即抛出，不允许静默通过。
    """
    bank_dir = bank_dir or (settings.data_dir / "bank")
    templates: list[dict] = []
    for path in sorted(bank_dir.glob("*.jsonc")):
        raw = path.read_text(encoding="utf-8")
        # 剥离整行注释（JSONC 允许 // 注释）
        stripped = "\n".join(
            line for line in raw.splitlines() if not line.lstrip().startswith("//")
        )
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"题库文件 {path.name} 解析失败：{exc}") from exc
        if not isinstance(data, list):
            raise ValueError(f"题库文件 {path.name} 顶层必须是数组")
        for item in data:
            _validate_template(item, path.name)
        templates.extend(data)

    if not templates:
        raise ValueError(f"题库为空，请检查目录 {bank_dir}")

    ids = [t["id"] for t in templates]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise ValueError(f"题库存在重复 id：{sorted(dup)}")
    return templates


_REQUIRED_FIELDS = {"id", "knowledge_id", "slot", "stem", "answer_expr"}
_VALID_SLOTS = {"fill", "choice", "judge", "calc", "geometry", "solve", "extra"}
# SVG 里写死的尺寸标注（形如 >30cm< / >20米<），有参数化题干时必须换成占位符
_HARD_LABEL_RE = re.compile(r'>\s*\d+(?:\.\d+)?\s*(?:cm|dm|km|m|厘米|分米|千米|米)\s*<')


# 由代码自动注入、不需要模板作者声明的变量
_AUTO_NAMES = {
    # 答案与干扰项
    "ans", "correct", "w1", "w2", "w3", "wrong1", "wrong2", "wrong3",
    # _derived 提供的中间量
    "ab", "a2", "b2", "abc", "s",
    "n1d", "n12d", "n13d", "n14d",
    "mn", "ma", "na", "est",
}
_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def _validate_template(item: dict, fname: str) -> None:
    """结构校验：字段齐全 + 取值合法。宁可加载时报错，也不要出卷时才炸。"""
    errs = validate_template_safe(item, fname)
    if errs:
        raise ValueError(f"{fname} 题目 {item.get('id', '?')}：" + "；".join(errs))


def validate_template_safe(item: dict, fname: str) -> list[str]:
    """与 _validate_template 同规则，但收集全部问题而不是遇到第一个就抛。

    scripts/lint_bank.py 用它做一次性全量体检，避免"改一个跑一次"的低效循环。
    """
    errs: list[str] = []
    tid = item.get("id", "?")
    missing = _REQUIRED_FIELDS - set(item)
    if missing:
        errs.append(f"缺字段 {sorted(missing)}")
    if item.get("slot") not in _VALID_SLOTS:
        errs.append(f"slot 非法：{item.get('slot')}")
    if item.get("slot") == "choice":
        exprs = item.get("choices_expr")
        if not isinstance(exprs, list):
            errs.append("选择题的 choices_expr 必须是 JSON 数组")
        elif len(exprs) != 4:
            errs.append(f"选择题必须有 4 个选项，实际 {len(exprs)} 个")
    if item.get("slot") == "judge" and not item.get("answer_expr"):
        errs.append("判断题缺少 answer_expr")
    for key in ("stem", "solution", "answer_display", "figure_svg"):
        val = item.get(key)
        if val is not None and not isinstance(val, str):
            errs.append(f"{key} 必须是字符串")
    dExpr = item.get("distractor_expr")
    if dExpr is not None:
        if not isinstance(dExpr, list) or len(dExpr) != 3:
            errs.append("distractor_expr 必须是长度为 3 的 JSON 数组")
    if item.get("constraints") is not None and not isinstance(item["constraints"], list):
        errs.append("constraints 必须是 JSON 数组")
    if item.get("choices_expr") is not None and not isinstance(item["choices_expr"], list):
        errs.append("choices_expr 必须是 JSON 数组，不能是字符串")
    if item.get("figure_svg") and not re.search(r'viewBox\s*=\s*"', item["figure_svg"]):
        errs.append("figure_svg 缺少 viewBox，打印时会被裁切")
    # 真实踩坑：gm_composite_01 的 SVG 里写死 ">30cm<" ">20cm<"，
    # 题干却随机成 长50 宽40 —— 图注和题干对不上，孩子没法做题。
    # 题干只要带参数，图里的尺寸标注就必须用占位符跟着变。
    if item.get("figure_svg") and item.get("params"):
        if _HARD_LABEL_RE.search(item["figure_svg"]):
            errs.append("figure_svg 里有写死的尺寸标注（如 >30cm<），"
                        "题干参数一变图注就对不上，请改成 {l}cm 这类占位符")
    errs.extend(f"{n}" for n in _validate_placeholders_safe(item, fname))
    return [f"<{tid}> {e}" if not e.startswith("<") else e for e in errs]


def _validate_placeholders_safe(item: dict, fname: str) -> list[str]:
    """静态占位符校验：模板里引用的变量必须有人负责提供。

    这是把缺陷从"出卷时才炸"前移到"加载时就报错"的关键一步。
    真实踩坑：sup_judge_mc_02 题干写了 '{n}' 但 params 里叫 'n_guard'，
    tv_circular_01 的答案写了 '{dist}' 却从没定义过 ——
    两者都稳定 100% 残留占位符，到出卷阶段才发现就太晚了。
    """
    params = item.get("params") or {}
    declared = set(params.keys())
    declared |= {n for n, cfg in params.items()
                 if isinstance(cfg, dict) and cfg.get("type") == "expr"}

    blob_parts = [
        item.get("stem", ""), item.get("solution", "") or "",
        item.get("answer_expr", ""), item.get("answer_display", "") or "",
        item.get("figure_svg", "") or "",
    ]
    blob_parts += [str(c) for c in (item.get("choices_expr") or [])]
    blob_parts += [str(c) for c in (item.get("constraints") or [])]
    blob_parts += [str(cfg.get("expr", ""))
                   for cfg in params.values() if isinstance(cfg, dict)]

    used = {p[1:-1] for part in blob_parts for p in _PLACEHOLDER_RE.findall(str(part))}
    unknown = sorted(used - declared - _AUTO_NAMES)
    if unknown:
        return [f"引用了未定义的变量 {unknown}；已声明参数 {sorted(declared)}，"
                "请在 params 中补充或改用 expr 派生"]
    return []


# --------------------------------------------------------------------------
# 单题渲染
# --------------------------------------------------------------------------
def _k_map(graph: dict) -> dict[str, dict]:
    return {n["id"]: n for n in graph["nodes"]}


def render_question(tpl: dict, kn_map: dict[str, dict],
                    rng: random.Random) -> dict:
    """把一条模板变成一道具体的题（含答案、选项、图形、解题思路）。"""
    params = roll_params(tpl["params"], rng, tpl.get("constraints")) if tpl.get("params") else {}
    node = kn_map.get(tpl["knowledge_id"], {})

    # 派生出解答思路里常用但模板未显式声明的中间量，降低模板书写负担
    values = dict(params)
    values.update(_derived(values, tpl))

    # 顺序很重要：必须先算出答案，才能让解题思路里引用 {ans}。
    # 反过来把 {ans} 注入题干则是绝对禁止的 —— 那等于把答案印在题目上。
    stem = substitute(tpl["stem"], values)
    raw_answer = evaluate_answer(tpl["answer_expr"], values)
    ans_value = fmt_answer(raw_answer)
    solution = substitute(tpl.get("solution", "") or "",
                          {**values, "ans": ans_value})
    svg = substitute(tpl.get("figure_svg", "") or "", values) if tpl.get("figure_svg") else None

    slot = tpl["slot"]
    choices = None
    answer = ans_value
    display = tpl.get("answer_display")

    if slot == "judge":
        answer = "√" if str(raw_answer).strip() in ("1", "True", "true") else "×"
    elif slot == "choice":
        # 选择题有两种写法，靠 answer_display 区分：
        #   ① answer_display = "{ans}"     —— answer_expr 算出的就是正确答案文本
        #   ② answer_display = "{correct}" —— 答案是文字概念（如"乘法分配律"），
        #      约定 choices_expr 第一项为正确答案，干扰项由后三项充当。
        #
        # 两种写法共用同一套占位符注入（ans/correct/w1/w2/w3）。
        # 真实踩坑：早期只在分支①派生 w1/w2/w3，分支②直接跳过，
        # 于是写了 {w1} 的模板四个选项全部残留占位符，且 100% 复现。
        # 现在不管走哪条路都先算好全部替换量，缺陷不可能再出现。
        dvals = _distractors(tpl, values, ans_value, rng)
        keys = {
            **values,
            "ans": ans_value,
            "correct": ans_value,
            "w1": dvals[0], "w2": dvals[1], "w3": dvals[2],
            "wrong1": dvals[0], "wrong2": dvals[1], "wrong3": dvals[2],
        }

        if display == "{correct}":
            ans_text = substitute(tpl["choices_expr"][0], keys)
        else:
            ans_text = substitute(display or "{ans}", keys)

        # 选项里的 {ans}/{correct} 必须指向最终答案文本（而不是裸数值），
        # 否则像 '[[{ans}]]' 这类带标记的写法会对不上答案。
        keys["ans"] = ans_text
        keys["correct"] = ans_text
        raw_choices = [substitute(c, keys) for c in tpl["choices_expr"]]

        choices = _dedupe_choices(raw_choices, ans_text, rng)
        rng.shuffle(choices)
        # 关键：答案统一记录为「选项文本」而不是 A/B/C/D 字母。
        # 原因：字母取决于打乱后的顺序，而答案文本是稳定可校验的，
        # 体检器、判分器、PDF 答案页三处用同一份文本才不会错位。
        answer = ans_text

    if display and slot not in ("choice", "judge"):
        answer = substitute(display, {**values, "ans": answer})

    return {
        "question_id": tpl["id"],
        "knowledge_id": tpl["knowledge_id"],
        "knowledge_name": node.get("name", tpl["knowledge_id"]),
        "module": node.get("module", "unknown"),
        "module_name": MODULE_LABELS.get(node.get("module", ""), "未分类"),
        "slot": slot,
        "stem": stem,
        "choices": choices,
        "answer": answer,
        "solution": solution,
        "figure_svg": svg,
        "unit": tpl.get("unit"),
        "difficulty": tpl.get("difficulty", node.get("difficulty", 2)),
    }


def _derived(v: dict, tpl: dict) -> dict:
    """生成模板思路文本里常用到的派生量，让题库写法保持简洁。

    派生放在代码里而不是塞进 params，是为了让同一件事只写一次：
    早期 na_pattern_01 在题干里写 {n1d} 却没人计算它，
    每次渲染都残留 3 个占位符，靠改模板要改几十处，收口到这儿只改一处。
    """
    d: dict = {}
    a = v.get("a")
    b = v.get("b")
    c = v.get("c")
    k = v.get("k")
    m = v.get("m")
    n = v.get("n")
    n1 = v.get("n1")

    def _int(x: object) -> int | None:
        return int(x) if isinstance(x, int) else None

    A, B, C, K, M, N, N1 = map(_int, (a, b, c, k, m, n, n1))
    step = v.get("d")

    if A is not None and B is not None:
        d["ab"] = A + B
        d["a2"] = A * 2
        d["b2"] = B * 2
    if A is not None and B is not None and C is not None:
        d["abc"] = A + B + C
        d["s"] = A + B + C

    # 等差数列前几项：{n1}, {n1d}, {n12d}, {n13d}, …
    if N1 is not None and isinstance(step, int):
        d["n1d"] = N1 + step
        d["n12d"] = N1 + 2 * step
        d["n13d"] = N1 + 3 * step
        d["n14d"] = N1 + 4 * step

    # 估算用的近似值与估算结果：{ma} 近似到百位，{na} 近似到十位
    if M is not None and N is not None:
        d["mn"] = M * N
        d["ma"] = int(round(M / 100.0)) * 100
        d["na"] = int(round(N / 10.0)) * 10
        d["est"] = d["ma"] * d["na"]
    return d


def _letter_of(text: str, choices: list[str]) -> str:
    idx = choices.index(text)
    return "ABCD"[idx]


def derive_distractors(answer: str, values: dict,
                       rng: random.Random) -> list[str]:
    """自动派生 3 个合理的干扰项。

    为什么要自动派生：实测发现题库作者（包括我）极易只写 ['{ans}', '{w1}', ...]
    却在 params 里漏定义 w1/w2/w3，导致选项里残留占位符、整卷被体检拦下。
    把干扰项的生成收口到代码里，这类缺陷在结构上就不会再出现。

    干扰项的选取原则（模拟真实试卷的常见错误）：
      - 分数：分母/分子写错、倒数
      - 整数：加减一个档位、乘以常见倍率
      - 必须与正确答案不同、互不重复、且非负
    """
    out: list[str] = []
    seen = {_text(answer)}

    def _add(cand) -> bool:
        # 统一走 _text：派生出来的可能是 Fraction（精确除法之后到处都是），
        # 直接 str() 会让选项印出 "Fraction(1, 3)" 这种字样给孩子看。
        t = _text(cand)
        if t not in seen:
            out.append(t)
            seen.add(t)
            return True
        return False

    # 情况一：答案是分数 "a/b"
    if "/" in answer and not answer.strip().startswith("-"):
        parts = answer.split("/")
        try:
            num, den = int(parts[0]), int(parts[1])
        except ValueError:
            num = den = 0
        if den and num > 0:
            proper = num < den
            cands = [
                Fraction(num, den + 1),
                Fraction(num + 1, den),
                Fraction(num, den * 2),
                Fraction(den, num) if num else Fraction(0),
            ]
            # "盐占盐水的几分之几"这类题的真分数答案，选项里出现 41/5 这种假分数
            # 一眼假，学生不化简就选对了 —— 必须把干扰项限制在同一值域内。
            if proper:
                cands = [x for x in cands if 0 < x < 1]
            for c in cands:
                if _add(c) and len(out) == 3:
                    return out
            if proper:
                for i in range(1, 8):
                    for cand in (Fraction(num + i, den), Fraction(num, den + i)):
                        if 0 < cand < 1 and _add(cand) and len(out) == 3:
                            return out

    # 情况二：答案是数值
    try:
        val = float(answer)
    except (TypeError, ValueError):
        val = None

    if val is not None:
        # 针对不同数量级选不同扰动策略：
        #   估算题的答案常在 4000 量级，此时 ±1/±2/±5 出来的选项毫无区分度，
        #   必须用相对扰动让学生真的去估数量级。
        if abs(val) < 10:
            deltas: tuple[float, ...] = (1, 2, 3)
        elif abs(val) < 100:
            deltas = (1, 2, 5)
        elif abs(val) < 1000:
            deltas = (10, 20, 50)
        else:
            deltas = ()
            unit = 100.0 if abs(val) < 100000 else 1000.0
            for f in (0.75, 1.3, 1.6, 0.5, 2.2):
                cand = _round_to(val * f, unit)
                if cand >= 0 and _add(fmt_answer(cand)) and len(out) == 3:
                    return out

        for dd in deltas:
            for sign in (1, -1):
                cand_val = val + sign * dd
                if cand_val < 0:
                    continue
                if _add(fmt_answer(cand_val)):
                    break
            if len(out) == 3:
                return out
        # 数值扰动不够时用整数倍补足
        for mul in (2, 3):
            cand_mul = fmt_answer(val * mul)
            if cand_mul not in seen and float(cand_mul) >= 0:
                _add(cand_mul)
            if len(out) == 3:
                return out

    # 兜底：保证一定有 3 个互斥且非负的选项，避免选项数不足
    filler = 0
    while len(out) < 3:
        cand = str(filler)
        if cand not in seen:
            out.append(cand)
            seen.add(cand)
        filler += 1
    return out


def _text(value) -> str:
    """把任意求值结果转成"小学生看得懂"的文本。

    真实事故：改用精确除法后，干扰项开始产出 Fraction 对象，
    而模板里写作 "[[{w1}]]"，substitute 会走 str() —— 页面与试卷上
    赫然出现「[[Fraction(1, 3)]]」。转换缺失在派生层，就该在这一层修，
    不能在模板层加 Fraction 判断打补丁（那样每个模板都得重复一遍）。
    """
    if isinstance(value, str):
        return value.strip()
    return fmt_answer(value)


_PY_CALL_RE = re.compile(
    r"\b(Fraction|Decimal)\s*\(\s*(-?\d+)\s*(?:,\s*(\d+)\s*)?\)|"
    r"\b(Fraction|Decimal)\s*\(\s*(-?\d+(?:\.\d+)?)\s*\)"
)


def _clean_expr_text(text: str) -> str:
    """把已替换成文本的表达式结果里的 Python 对象写法还原成数学写法。

    为什么需要它（真实事故，第二处漏点）：
      distractor_expr 写的是 "[[{c}/{a}]]"，substitute 之后表达式变成文本
      （'[[4/12]]' 会被精确除法求值，但 '[[Fraction(1,3)]]' 这种是
      eval 出来的 Fraction 对象被 str() 的产物）。上一版只处理了对象，
      没处理"文本里嵌着对象字面量"，于是 [[Fraction(1, 3)]] 照样印在卷面上。
      这里是派生层的最后一道收口：对象/文本两条路都必须变成 7/15 这种写法。
    """
    if not text or ("Fraction" not in text and "Decimal" not in text):
        return text

    def _repl(m: re.Match) -> str:
        if m.group(2) is not None:
            num, den = int(m.group(2)), int(m.group(3) or 1)
        else:
            num, den = _decimal_to_ratio(float(m.group(5)))
        if den == 1:
            return str(num)
        return f"{num}/{den}"

    return _PY_CALL_RE.sub(_repl, text)


def _decimal_to_ratio(x: float) -> tuple[int, int]:
    """把有限小数还原成精确分数（3.5 -> (7, 2)）。"""
    frac = Fraction(x).limit_denominator(10000)
    return frac.numerator, frac.denominator


def _distractors(tpl: dict, values: dict, answer: str,
                 rng: random.Random) -> list[str]:
    """确定三个干扰项：优先用模板显式声明的 distractor_expr，否则自动派生。

    为什么需要显式声明（答案正确性事故）：
      na_divisibility_01 问"哪个数能同时被 2、3、5 整除"，答案 1230。
      自动派生按数量级做相对扰动得到 900 —— 而 900 恰好也能被 2、3、5 整除，
      等于凭空多出一个正确答案。凡是答案带有可判定的数学性质时，
      干扰项必须由作者写死负例（如 base+2 / base+5 / base+4）。

    关于去重（真实缺陷，两次踩到）：
      distractor_expr 是由作者按公式写的，公式在某些参数组合下会与正确答案
      算成同一个值 —— fp_engineering_02 的 [[{c}/{a}]] 在 a=12,b=30,c=5 时
      正好等于答案 5/12，四个选项里出现两个 5/12。先前靠往 constraints 里
      逐条补 {"{c}/{a}" != 答案} 来堵，是打地鼠：换一组参数又冒出新的重合。
      这里改成结构性收口 —— 任何与答案或彼此重复的干扰项，都在同值域内
      重新取值（分数在原分母附近微调，整数用相对扰动），不依赖作者穷举。
    """
    exprs = tpl.get("distractor_expr")
    if exprs:
        raw = []
        for e in exprs:
            filled = substitute(e, values)
            try:
                raw.append(_clean_expr_text(_text(safe_eval(filled))))
            except Exception:
                # 表达式本身就带 [[ ]] 标记、没法当算式求值的写法：
                # 直接当文本处理，再把内嵌的对象写法还原掉。
                raw.append(_clean_expr_text(filled))
        return _dedupe_distractors(raw, answer, rng)
    return derive_distractors(answer, values, rng)


def _dedupe_distractors(cands: list[str], answer: str,
                        rng: random.Random) -> list[str]:
    """把与答案重合、或彼此重复的干扰项替换掉，保证 3 个互异且都不等于答案。

    值域策略：原干扰项是分数就在真分数范围内换分子/分母，
    是整数就在原值附近取偏移；这样替换出来的选项与题目问法仍然协调
    （不会在"还剩几分之几"里突然冒出一个小数）。
    """
    seen = {answer.strip()}
    out: list[str] = []
    for cand in cands:
        c = (cand or "").strip()
        if c and c not in seen:
            out.append(c)
            seen.add(c)
            continue
        # 撞车：在同值域内找替代值
        for alt in _alternatives(c, answer, rng):
            if alt not in seen:
                out.append(alt)
                seen.add(alt)
                break
        else:
            # 实在找不到（极端参数组合）：退化为在答案附近扰动，
            # 宁可选项略有生硬，也不能交付重复选项 —— 那会让题目没有唯一答案。
            for alt in _alternatives(answer, answer, rng, wider=True):
                if alt not in seen:
                    out.append(alt)
                    seen.add(alt)
                    break
    while len(out) < 3:
        out.append(f"{len(out) + 1}00")
        seen.add(out[-1])
    return out[:3]


def _alternatives(seed_text: str, answer: str, rng: random.Random,
                  wider: bool = False) -> list[str]:
    """在 seed_text 所在的值域里生成一批候选干扰值。"""
    base = seed_text or answer
    out: list[str] = []

    # 分数值域：保持真分数（0 < x < 1），分子分母双向微调
    m = re.match(r"^\[\[\s*(\d+)\s*/\s*(\d+)\s*\]\]$", base)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        span = range(1, 9) if not wider else range(1, 20)
        for i in span:
            for cand in (Fraction(num + i, den + i * 2),
                         Fraction(num, den + i),
                         Fraction(num + i, den * 2 + i)):
                if 0 < cand < 1:
                    out.append(f"[[{cand.numerator}/{cand.denominator}]]")
        return _uniq(out)

    # 整数值域：相对扰动
    try:
        val = float(base)
    except ValueError:
        return out
    for mul in (1.5, 0.5, 2.0, 0.75, 1.25, 3.0):
        cand = round(val * mul, 4)
        if cand > 0 and abs(cand - val) > 1e-9:
            out.append(fmt_answer(cand))
    return _uniq(out)


def _uniq(seq: list[str]) -> list[str]:
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _round_to(x: float, unit: float) -> float:
    return round(x / unit) * unit


def _dedupe_choices(choices: list[str], correct: str,
                    rng: random.Random) -> list[str]:
    """选项去重：当干扰项与正确答案重合时，用带偏移的数值替换。

    实际踩坑：模板里写 ['{ans}', '{w1}', '{w2}', '{w3}']，
    当某个 w 参数恰好等于 ans 时会出现两个相同选项，
    体检器会判 CHOICE_DUPLICATE 并把整卷拦下。
    这里直接消除该情况，而不是靠重抽碰运气。

    二次踩坑（本函数曾经的判断是错的）：
      原先写的是 `if ch == correct or ch not in seen`，本意是"正确选项原样保留"。
      但正确选项同样会被去重逻辑覆盖一次：当重复项恰好就是正确答案本身
      （第二个 [[5/12]] 且 5/12 就是答案）时，它落进了 append 分支，
      重复原封不动地留在卷面上 —— 审计里 fp_engineering_02 有 10.7% 命中率。
      正确答案之所以"原样保留"，关键是不被替换成别的值；
      至于它出现在第几个位置，交给后面的 shuffle 决定，与本函数无关。
      因此这里只看"是否首次出现"。
    """
    seen: set[str] = set()
    out: list[str] = []
    for ch in choices:
        if ch not in seen:
            out.append(ch)
            seen.add(ch)
            continue
        # 重复项：优先用同值域的候选替换，其次在数值附近偏移
        replaced = False
        for cand in _alternatives(ch, correct, rng):
            if cand not in seen:
                out.append(cand)
                seen.add(cand)
                replaced = True
                break
        if replaced:
            continue
        try:
            val = float(ch)
            for delta in (1, 2, 3, 5, 10):
                cand = fmt_answer(val + delta)
                if cand not in seen:
                    out.append(cand)
                    seen.add(cand)
                    replaced = True
                    break
        except (TypeError, ValueError):
            pass
        if not replaced:
            # 极端参数组合下的保底：也要保证与已有选项不同，
            # 否则"四个选项"里出现两个一样的，这道题就没有唯一答案了。
            k = 1
            while True:
                cand = f"{ch}?{k}" if k < 3 else str(k)
                if cand not in seen:
                    out.append(cand)
                    seen.add(cand)
                    break
                k += 1
    return out


# --------------------------------------------------------------------------
# 整卷生成
# --------------------------------------------------------------------------
# 优先知识点：把每格的名额优先给这些高频考点，避免随机到冷门知识点。
# 注意：同一优先层内用随机顺序平摊（见 _pick_templates 的 shuffle+稳定排序），
# 因此把某知识点加进本表 = 让它"有资格参与竞争"，而不是"永远独占名额"。
# W5 扩充题的 knowledge_id 已全部纳入对应题型优先层，确保它们是"活模板"而非被饿死的死模板。
_SLOT_PRIORITY: dict[str, list[str]] = {
    "fill": ["num_notation", "decimal_fraction_pct_convert", "gcd_lcm",
             "unit_one", "percent_word_problem", "travel_basic",
             "ratio_meaning", "proportion_property",
             # W5 扩充：数与代数填空（质数合数/估算/规律）+ 比和比例（按比例分配）
             "prime_composite", "estimation", "number_pattern", "ratio_distribution",
             # W5 扩充：其他综合填空——补两个原零覆盖知识点（鸡兔同笼 / 容斥原理）+ 抽屉原理
             "tree_planting", "average_problem",
             "chicken_rabbit", "inclusion_exclusion", "pigeonhole"],
    "choice": ["percent_word_problem", "percent_change", "travel_basic",
               "scale_map", "ratio_meaning", "stats_probability",
               "fraction_word_problem",
               # W5 扩充：几何选择（圆/圆柱圆锥/立体体积）与行程（逆水行船）、比例（解比例）
               "circle_sector", "solid_volume", "cylinder_cone",
               "travel_water_air", "proportion_property"],
    "judge": ["percent_word_problem", "geometry_transform", "direct_inverse_proportion",
              "pigeonhole", "stats_probability",
              # W5 扩充：比和比例判断（比的基本性质）
              "ratio_meaning"],
    "calc": ["four_mixed_ops", "simple_calc", "equation_solve", "column_calc"],
    "geometry": ["circle_sector", "cylinder_cone", "composite_area", "plane_area"],
    "solve": ["fraction_word_problem", "percent_word_problem", "percent_change",
              "engineering", "concentration", "travel_meet_chase",
              "ratio_distribution"],
    "extra": ["travel_meet_chase", "travel_circular", "counting_principle"],
}


def _templates_for(bank: list[dict], slot: str, module: str) -> list[dict]:
    return [t for t in bank if t["slot"] == slot and _module_of(t, module)]


_MODULE_CACHE: dict[str, str] = {}


def _module_of(tpl: dict, want: str) -> bool:
    return _MODULE_CACHE.get(tpl["knowledge_id"]) == want


def build_module_index(graph: dict, bank: list[dict]) -> None:
    """建立 knowledge_id -> module 索引，供 _module_of 使用。"""
    _MODULE_CACHE.clear()
    for node in graph["nodes"]:
        _MODULE_CACHE[node["id"]] = node["module"]


def generate_paper(engine: Engine | None = None, seed: int | None = None,
                   title: str | None = None, persist: bool = True,
                   max_rounds: int = 30) -> dict:
    """生成一份卷子。返回 dict，含 items / check_report / paper_id。"""
    graph = load_graph()
    bank = load_bank()
    build_module_index(graph, bank)
    kn_map = _k_map(graph)
    layout = graph["paper_layout"]
    module_targets = {m["id"]: m["target_ratio"] for m in graph["modules"]}

    seed = seed if seed is not None else random.randint(1, 10 ** 9)
    rng = random.Random(seed)

    last_report: qa_checker.CheckReport | None = None
    for _round in range(max_rounds):
        items: list[dict] = []
        seq = 0
        seen_qids: set[str] = set()
        ok = True

        for sec in sorted(layout["sections"], key=lambda s: s["order"]):
            slot = sec["slot"]
            per_score = sec["per_score"]
            for module, cell in sec["quota"].items():
                picked = _pick_templates(bank, slot, module, cell, seen_qids,
                                         rng, kn_map)
                if len(picked) < cell:
                    ok = False
                    break
                for tpl in picked:
                    seq += 1
                    rendered = render_question(tpl, kn_map, rng)
                    rendered.update({
                        "seq": seq,
                        "score": per_score,
                        "section_title": sec["title"],
                        "section_instruction": sec.get("instruction", ""),
                    })
                    seen_qids.add(tpl["id"])
                    items.append(rendered)
            if not ok:
                break

        if not ok:
            continue

        report = qa_checker.check_paper(items, layout, module_targets)
        last_report = report
        if report.passed:
            paper_id = uuid.uuid4().hex[:12]
            result = {
                "paper_id": paper_id,
                "title": title or f"广州小升初数学密考模拟卷（{seed}）",
                "seed": seed,
                "total_score": layout["total_score"],
                "duration_min": layout["duration_minutes"],
                "items": items,
                "check_report": report.to_dict(),
            }
            if persist and engine is not None:
                _persist(engine, result)
            return result

    # 重抽到上限仍未通过：如实返回报告，不伪装成功
    raise RuntimeError(
        "出卷体检未通过，已重抽 "
        f"{max_rounds} 轮。最后一批问题："
        + "; ".join(f"[{i.code}] {i.detail}" for i in (last_report.errors if last_report else []))
    )


def _pick_templates(bank: list[dict], slot: str, module: str, count: int,
                    seen: set[str], rng: random.Random,
                    kn_map: dict[str, dict]) -> list[dict]:
    """为某个格子挑题：优先高频知识点，尽量不重复已出过的题。"""
    pool = [t for t in bank
            if t["slot"] == slot and kn_map.get(t["knowledge_id"], {}).get("module") == module]
    if not pool:
        return []
    priority = _SLOT_PRIORITY.get(slot, [])
    rng.shuffle(pool)
    # 同一优先层内用随机顺序平摊，不再按难度降序硬排。
    # 原因：原写法对 quota=1 的格子，难度最高的优先模板会永远独占名额，
    # 导致同层低难度模板（如 ratio_meaning diff2、solid_volume/circle_sector diff3）
    # 被饿死、永远落不了卷。改为随机后，1 个名额在 N 个同层候选间均匀轮转。
    pool.sort(key=lambda t: (
        0 if t["id"] not in seen else 1,
        0 if t["knowledge_id"] in priority else 1,
        rng.random(),
    ))
    picked: list[dict] = []
    used_kn: set[str] = set()
    for t in pool:
        if len(picked) >= count:
            break
        if t["id"] in seen:
            continue
        if t["knowledge_id"] in used_kn and len(pool) > count:
            continue
        picked.append(t)
        used_kn.add(t["knowledge_id"])
    # 数量不够时放宽知识点去重
    if len(picked) < count:
        for t in pool:
            if len(picked) >= count:
                break
            if t["id"] in seen or t in picked:
                continue
            picked.append(t)
    return picked


# --------------------------------------------------------------------------
# 落库
# --------------------------------------------------------------------------
def _persist(engine: Engine, result: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO papers (id, title, seed, total_score, duration_min,
                     status, check_report) VALUES (:id, :title, :seed, :ts, :dm, :st, :cr)"""),
            {"id": result["paper_id"], "title": result["title"], "seed": result["seed"],
             "ts": result["total_score"], "dm": result["duration_min"],
             "st": "checked", "cr": json.dumps(result["check_report"], ensure_ascii=False)},
        )
        for it in result["items"]:
            conn.execute(
                text("""INSERT INTO paper_items (paper_id, seq, slot, section_title,
                         section_instruction, knowledge_id, question_id, score,
                         rendered_stem, rendered_solution, figure_svg, choices, answer,
                         answer_unit)
                     VALUES (:pid, :seq, :slot, :st, :sins, :kid, :qid, :sc, :stem, :sol,
                             :svg, :ch, :ans, :unit)"""),
                {"pid": result["paper_id"], "seq": it["seq"], "slot": it["slot"],
                 "st": it["section_title"], "sins": it.get("section_instruction", ""),
                 "kid": it["knowledge_id"],
                 "qid": it["question_id"], "sc": it["score"], "stem": it["stem"],
                 "sol": it["solution"], "svg": it["figure_svg"],
                 "ch": json.dumps(it["choices"], ensure_ascii=False) if it["choices"] else None,
                 "ans": it["answer"], "unit": it["unit"]},
            )
