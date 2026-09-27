"""出卷体检器：出卷后的自动校验层。

分两级：
  ERROR —— 必须拦截并换题重抽（占位符残留、答案值域非法、图形越界、总分不等）
  WARN  —— 记录但不阻断（模块占比偏差、重复率偏高）

图形边界检查的动机（真实踩坑）：首次排版验证时，
SVG viewBox 宽度设成 240 而 <text x="222">10cm</text> 的文字宽约 24 单位，
导致最后一个字符被裁成 "10c"。这类问题肉眼不一定看得出来，
必须由代码逐一核算元素包围盒才能保证不出印刷事故。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from app.services.math_render import _FRAC_RE, check_marks

# 每个字符在 11px 字号下的估算宽度（单位 = SVG user unit）
_CHAR_W = 6.0
_DEFAULT_FONT = 11.0

# 答案值域规则：命中即拦截。key 为模块或知识点前缀，value 为校验函数
_VALUE_RULES = {
    "percent_max": 100.0,
}


@dataclass
class Issue:
    level: str          # ERROR / WARN
    code: str
    detail: str
    seq: int | None = None


@dataclass
class CheckReport:
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "ERROR"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "WARN"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def add(self, level: str, code: str, detail: str, seq: int | None = None) -> None:
        self.issues.append(Issue(level, code, detail, seq))

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "errors": [i.__dict__ for i in self.errors],
            "warnings": [i.__dict__ for i in self.warnings],
            "stats": self.stats,
        }


# --------------------------------------------------------------------------
# 单项检查
# --------------------------------------------------------------------------
_PLACEHOLDER_RE = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")
# Python 对象被 str() 之后漏进文本的痕迹，如 "Fraction(1, 3)"、"<Fraction ...>"。
# 这类文本一旦出现在卷面上，孩子会直接看到源码字样 —— 属于必须拦下的硬错误。
_PY_OBJECT_RE = re.compile(
    r"\b(?:Fraction|Decimal|OrderedDict|defaultdict)\s*\(|"
    r"<(?:class|function|built-in|module|method)\b"
)


def check_python_leak(text: str, where: str, seq: int, rep: CheckReport) -> None:
    """题面/选项/答案里不允许出现 Python 对象字面量。

    真实事故：引入精确除法后，干扰项开始产出 Fraction 对象，
    模板写 "[[{w1}]]" 时被 str() 成 "Fraction(1, 3)"，
    页面上就成了 [[Fraction(1, 3)]]。派生层已修，这里补一道根因防线：
    以后无论哪条路径漏出对象字面量，组卷阶段就会被拦下，而不是等打印出来才发现。
    """
    if not text:
        return
    m = _PY_OBJECT_RE.search(text)
    if m:
        rep.add("ERROR", "PYTHON_OBJECT_LEAK",
                f"{where} 出现 Python 对象字面量 {m.group(0)!r}：{text[:80]}", seq)


def check_placeholders(text: str, where: str, seq: int, rep: CheckReport) -> None:
    """题干/答案里不允许残留未替换的 {var}。"""
    if not text:
        return
    leftovers = _PLACEHOLDER_RE.findall(text)
    if leftovers:
        rep.add("ERROR", "PLACEHOLDER_LEFT",
                f"{where} 残留未替换占位符 {leftovers}", seq)


def check_math_marks(text: str, where: str, seq: int, rep: CheckReport) -> None:
    """分数标记 [[a/b]] 必须配对且分母不为 0。"""
    for p in check_marks(text or ""):
        rep.add("ERROR", "MATH_MARK", f"{where}: {p}", seq)


def check_fraction_form(text: str, where: str, seq: int, rep: CheckReport) -> None:
    """卷面规范：题面上的分数必须是既约分数。

    印刷成卷时 [[6/9]]、[[5/5]] 这类写法不会出现 —— 小学试卷的分数一律最简。
    这不是数学错误（6/9 等于 2/3），但会被家长一眼看出"不像真题"，
    属于"题干文字有问题"的范畴，正好是本项目要自动校验的那类事情。
    """
    if not text:
        return
    for frag in _FRAC_RE.findall(text):
        core = frag.strip().split("+")[-1]
        if "/" not in core:
            continue
        num_raw, den_raw = core.split("/", 1)
        num_raw, den_raw = num_raw.strip(), den_raw.strip()
        if not (num_raw.isdigit() and den_raw.isdigit()):
            continue
        n_val, d_val = int(num_raw), int(den_raw)
        if d_val == 0:
            continue  # 由 check_math_marks 负责报
        g = math.gcd(n_val, d_val)
        if g != 1:
            rep.add("ERROR", "FRACTION_NOT_SIMPLIFIED",
                    f"{where} 分数 [[{frag}]] 未约成最简"
                    + (f"（可约去 {g}）" if g > 1 else ""), seq)


# 题干里出现这些说法时，答案与选项都应该是真分数：
# 问"几分之几""占几分之几"的题，真题选项不会给 15/2、19 这种一眼假的假分数。
_PROPER_ASK_RE = re.compile(r"几分之几|占.{0,8}的（\s*）|还剩.{0,10}的（\s*）")


def check_proper_fraction(text: str, where: str, seq: int, rep: CheckReport,
                          *, strict: bool) -> None:
    """假分数检查：只在"问几分之几"的题目里生效。

    真实质量问题：fp_engineering_02 问"还剩下这条路的几分之几"，
    自动派生的干扰项却给出 [[15/2]]，rp_meaning_02 给出 [[19]] ——
    孩子一眼就能排除，等于白送一个错项，题目失去区分度。
    加到 >1 才是假分数、或整数 >= 1 时报警。
    """
    if not text:
        return
    for frag in _FRAC_RE.findall(text):
        core = frag.strip().split("+")[-1]
        if "/" not in core:
            # 纯整数出现在"问几分之几"的选项里，等价于 19/1，也是假分数
            if strict and core.strip().isdigit() and int(core) >= 1:
                rep.add("ERROR", "IMPROPER_FRACTION",
                        f"{where} 问的是几分之几，选项却是整数 [[{frag}]]", seq)
            continue
        num_raw, den_raw = core.split("/", 1)
        num_raw, den_raw = num_raw.strip(), den_raw.strip()
        if not (num_raw.isdigit() and den_raw.isdigit()):
            continue
        n_val, d_val = int(num_raw), int(den_raw)
        if d_val and n_val >= d_val:
            rep.add("ERROR", "IMPROPER_FRACTION",
                    f"{where} 问的是几分之几，却出现假分数 [[{frag}]]", seq)


# 答案里带符号的数字前缀，如 "-56 平方厘米" -> -56.0、"10700 元" -> 10700.0。
# 用正则而不是 float()：float 遇到单位后缀一律 ValueError，
# 早期就是靠 except: pass 把负数答案放过去的。
_LEADING_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _leading_number(text: str) -> float | None:
    """取答案开头的数值（允许后面跟单位、汉字），取不到返回 None。

    只认"开头"是有意的：像 "x = 14"、"3 时 20 分" 这类复合答案不该被误判成
    单个数值去做负数/整数检查，否则会刷出一堆假警报。
    """
    m = _LEADING_NUM_RE.match(text.lstrip())
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def check_answer_domain(answer: str, module: str, unit: str | None,
                         seq: int, rep: CheckReport) -> None:
    """答案值域合理性：人数/棵树/个数必须为正整数，百分率不超 100%。"""
    if answer is None or answer == "":
        rep.add("ERROR", "ANSWER_EMPTY", "答案为空", seq)
        return
    txt = str(answer).strip()

    # 含"/"的分数答案单独放行（如 3/4）
    if "/" in txt and not txt.replace("/", "").isdigit():
        pass
    elif "/" in txt:
        parts = txt.split("/")
        if parts[1] == "0":
            rep.add("ERROR", "ANSWER_DIV_ZERO", f"答案分母为 0：{txt}", seq)
    else:
        # 真实踩坑：答案几乎总是带着单位（"-56 平方厘米"、"10700 元"），
        # 直接 float(txt) 必然 ValueError，被 except 吞掉后负数检查形同虚设 ——
        # seed=20261002 第 33 题的 -56 平方厘米就是这样一路漏到卷面上的。
        # 所以先把带符号的数字前缀抠出来再判值域。
        val = _leading_number(txt)
        if val is None:
            pass
        else:
            if val < 0:
                rep.add("ERROR", "ANSWER_NEGATIVE", f"答案出现负数：{txt}", seq)
            if unit in ("本", "人", "棵", "个", "种", "天", "小时", "分") and val != int(val):
                rep.add("WARN", "ANSWER_NOT_INTEGER",
                        f"答案应为整数但为 {txt}（单位 {unit}）", seq)

    if unit == "%":
        try:
            val = float(txt.replace("%", "").strip())
            if val > _VALUE_RULES["percent_max"]:
                rep.add("ERROR", "PERCENT_OVER_100",
                        f"百分率超过 100%：{txt}", seq)
        except ValueError:
            pass


# --------------------------------------------------------------------------
# 图形边界：本次真实踩坑的防线
# --------------------------------------------------------------------------
_TAG_RE = re.compile(r"<(rect|circle|ellipse|line|path|text|polygon)\b([^>]*)>", re.I)
_ATTR_RE = re.compile(r'([a-zA-Z-]+)\s*=\s*"([^"]*)"')


def _num(attrs: dict, key: str, default: float = 0.0) -> float:
    raw = attrs.get(key, "")
    m = re.match(r"-?\d+(?:\.\d+)?", str(raw).strip())
    return float(m.group()) if m else default


def _points_bbox(attr_val: str) -> tuple[float, float, float, float]:
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", attr_val)]
    xs = nums[0::2]
    ys = nums[1::2]
    if not xs or not ys:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def check_figure_bounds(svg: str, seq: int, rep: CheckReport) -> None:
    """逐一核算 SVG 内每个元素的包围盒，越出 viewBox 即拦截。

    对 <text> 按 6 单位/字符估算宽度，并留 4 单位安全边距 —— 
    这正是 "10cm" 被裁成 "10c" 的直接原因。
    """
    if not svg:
        return
    vb = re.search(r'viewBox\s*=\s*"([^"]+)"', svg, re.I)
    if not vb:
        rep.add("ERROR", "FIG_NO_VIEWBOX", "SVG 缺少 viewBox，无法保证打印不被裁切", seq)
        return
    vnums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", vb.group(1))]
    if len(vnums) != 4:
        rep.add("ERROR", "FIG_BAD_VIEWBOX", f"viewBox 格式异常：{vb.group(1)}", seq)
        return
    vx, vy, vw, vh = vnums

    for tag, attr_str in _TAG_RE.findall(svg):
        tag = tag.lower()
        attrs = dict(_ATTR_RE.findall(attr_str))
        x0 = y0 = x1 = y1 = 0.0

        if tag == "rect":
            x0, y0 = _num(attrs, "x"), _num(attrs, "y")
            x1, y1 = x0 + _num(attrs, "width"), y0 + _num(attrs, "height")
        elif tag in ("circle", "ellipse"):
            cx, cy = _num(attrs, "cx"), _num(attrs, "cy")
            rx = _num(attrs, "r") if tag == "circle" else _num(attrs, "rx")
            ry = _num(attrs, "r") if tag == "circle" else _num(attrs, "ry")
            x0, y0, x1, y1 = cx - rx, cy - ry, cx + rx, cy + ry
        elif tag == "line":
            xs = [_num(attrs, "x1"), _num(attrs, "x2")]
            ys = [_num(attrs, "y1"), _num(attrs, "y2")]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        elif tag == "polygon":
            x0, y0, x1, y1 = _points_bbox(attrs.get("points", ""))
        elif tag == "path":
            # path 的 d 属性用同样方式粗估，保守起见放大 10% 余量
            d = attrs.get("d", "")
            nums = [float(v) for v in re.findall(r"-?\d+(?:\.\d+)?", d)]
            if nums:
                xs, ys = nums[0::2], nums[1::2]
                if xs and ys:
                    x0, x1 = min(xs), max(xs)
                    y0, y1 = min(ys), max(ys)
                    pad = 0.1 * max(x1 - x0, y1 - y0)
                    x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        elif tag == "text":
            tx, ty = _num(attrs, "x"), _num(attrs, "y")
            content = ""
            m = re.search(r">([^<]*)<", svg[svg.find(attr_str) + len(attr_str):])
            if m:
                content = m.group(1)
            fs = _num(attrs, "font-size", _DEFAULT_FONT) or _DEFAULT_FONT
            anchor = attrs.get("text-anchor", "start").strip()
            text_w = len(content) * _CHAR_W * (fs / _DEFAULT_FONT)
            if anchor == "middle":
                x0, x1 = tx - text_w / 2, tx + text_w / 2
            elif anchor == "end":
                x0, x1 = tx - text_w, tx
            else:
                x0, x1 = tx, tx + text_w
            y0, y1 = ty - fs, ty + fs * 0.3

        if x0 < vx or y0 < vy or x1 > vx + vw or y1 > vy + vh:
            rep.add("ERROR", "FIG_OUT_OF_BOUNDS",
                    f"图形元素 <{tag}> 包围盒 ({x0:.1f},{y0:.1f})-({x1:.1f},{y1:.1f}) "
                    f"越出 viewBox ({vx:.0f},{vy:.0f},{vw:.0f},{vh:.0f})，打印会被裁切",
                    seq)


# --------------------------------------------------------------------------
# 整卷检查
# --------------------------------------------------------------------------
def check_paper(items: list[dict], layout: dict, module_targets: dict[str, int],
                rep: CheckReport | None = None) -> CheckReport:
    """items: 每个元素含 seq/slot/knowledge_id/module/stem/answer/solution/
    figure_svg/choices/score。"""
    rep = rep or CheckReport()

    for it in items:
        seq = it.get("seq")
        check_placeholders(it.get("stem", ""), "题干", seq, rep)
        check_placeholders(it.get("solution", "") or "", "解题思路", seq, rep)
        for idx, ch in enumerate(it.get("choices") or []):
            check_placeholders(ch, f"选项{idx + 1}", seq, rep)
        check_math_marks(it.get("stem", ""), "题干", seq, rep)
        check_math_marks(it.get("solution", "") or "", "解题思路", seq, rep)
        check_fraction_form(it.get("stem", ""), "题干", seq, rep)
        check_fraction_form(it.get("solution", "") or "", "解题思路", seq, rep)
        for idx, ch in enumerate(it.get("choices") or []):
            check_math_marks(ch, f"选项{idx + 1}", seq, rep)
            check_fraction_form(ch, f"选项{idx + 1}", seq, rep)

        # "问几分之几"的题，答案与选项都必须落在真分数区间，否则选项一眼假。
        # 只看题干是否这样问，避免误伤"答案是 15/2 天"这类正常题。
        asks_fraction = bool(_PROPER_ASK_RE.search(it.get("stem", "")))
        if asks_fraction:
            check_proper_fraction(it.get("answer") or "", "答案", seq, rep, strict=True)
            for idx, ch in enumerate(it.get("choices") or []):
                check_proper_fraction(ch, f"选项{idx + 1}", seq, rep, strict=True)
        check_answer_domain(it.get("answer"), it.get("module", ""),
                            it.get("unit"), seq, rep)
        check_figure_bounds(it.get("figure_svg") or "", seq, rep)

        # 对象字面量泄漏：题干/思路/选项/答案只要有一处印出 "Fraction(1, 3)"
        # 之类字样就是硬错误，孩子会直接看到源码。
        check_python_leak(it.get("stem", ""), "题干", seq, rep)
        check_python_leak(it.get("solution", "") or "", "解题思路", seq, rep)
        check_python_leak(str(it.get("answer", "")), "答案", seq, rep)
        for idx, ch in enumerate(it.get("choices") or []):
            check_python_leak(ch, f"选项{idx + 1}", seq, rep)

        # 选择题：必须恰好 4 个选项、且正确答案在其中
        choices = it.get("choices") or []
        if it.get("slot") == "choice":
            if len(choices) != 4:
                rep.add("ERROR", "CHOICE_COUNT",
                        f"选择题应有 4 个选项，实际 {len(choices)} 个", seq)
            else:
                ans = str(it.get("answer", "")).strip()
                norm = [str(c).strip() for c in choices]
                if ans not in norm:
                    rep.add("ERROR", "CHOICE_ANSWER_MISSING",
                            f"答案 {ans} 不在选项中 {norm}", seq)
                if len(set(norm)) != 4:
                    rep.add("ERROR", "CHOICE_DUPLICATE",
                            f"选择题选项存在重复：{norm}", seq)

        # 判断题：答案必须归一为 √ / ×
        if it.get("slot") == "judge":
            if str(it.get("answer", "")).strip() not in ("√", "×"):
                rep.add("ERROR", "JUDGE_ANSWER",
                        f"判断题答案必须为 √ 或 ×，实际 {it.get('answer')!r}", seq)

    # 总分必须精确等于 layout 声明值
    total = sum(int(it.get("score", 0)) for it in items)
    rep.stats["total_score"] = total
    rep.stats["question_count"] = len(items)
    if total != layout.get("total_score", 100):
        rep.add("ERROR", "TOTAL_SCORE",
                f"卷面总分 {total}，要求 {layout.get('total_score')}")

    # 题量必须与 layout 一致
    want_n = layout.get("total_questions")
    if want_n and len(items) != want_n:
        rep.add("ERROR", "QUESTION_COUNT",
                f"题量 {len(items)}，要求 {want_n}")

    # 各题型题量核对
    for sec in layout.get("sections", []):
        slot = sec["slot"]
        want = sum(sec.get("quota", {}).values())
        got = sum(1 for it in items if it.get("slot") == slot)
        if want != got:
            rep.add("ERROR", "SECTION_QUOTA",
                    f"题型 {slot} 应有 {want} 题，实际 {got} 题")

    # 模块分值占比（WARN，允许重抽优化）
    mod_scores: dict[str, int] = {}
    for it in items:
        mod_scores[it.get("module", "?")] = mod_scores.get(it.get("module", "?"), 0) + int(it.get("score", 0))
    rep.stats["module_scores"] = mod_scores
    for mod, target in module_targets.items():
        actual = mod_scores.get(mod, 0)
        if abs(actual - target) > 3:
            rep.add("WARN", "MODULE_DEVIATION",
                    f"模块 {mod} 实得 {actual} 分，目标 {target} 分，偏差超过 3 分")

    # 同一知识点重复出现次数（同卷内同知识点 > 2 次记 WARN）
    kn_count: dict[str, int] = {}
    for it in items:
        k = it.get("knowledge_id", "?")
        kn_count[k] = kn_count.get(k, 0) + 1
    for k, c in kn_count.items():
        if c > 2:
            rep.add("WARN", "KNOWLEDGE_REPEAT",
                    f"同卷内知识点 {k} 出现 {c} 次，重复偏高")

    return rep
