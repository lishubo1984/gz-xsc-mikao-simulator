"""判分引擎。

难点不在"比对字符串"，而在于学生写答案的形式五花八门。
本模块的取舍原则：

  【必须判对】
    3/4 与 0.75        —— 分数与小数等价
    0.5 与 1/2         —— 未约分的等值分数
    42% 与 42          —— 题干已带 % 时不必再写
    96 元 与 96        —— 单位已在题干出现时不重复扣
    x = 3 与 3         —— 解方程的书写形式
    3 : 4 与 3:4       —— 空格差异

  【必须判错】
    24 个月 与 2 年     —— 单位不同且未折算，不换算（小学不要求自行换算单位时态）
    1/2 与 2/1         —— 分子分母颠倒

之所以「单位」一律剥离而不是逐题配置：
  题面已经写明"（　　）千米"时，学生在空中写 240 或 240 千米都算对，
  若严格要求完全一致，会把大量其实做对的答案判错，家长体验极差。
  反过来单位错配的情况（把"分"写成"小时"）极少出现，不值得为此牺牲体验。
"""
from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

# 常见单位后缀：剥离后再比对
_UNIT_RE = re.compile(
    r"(平方分米|平方厘米|立方分米|立方厘米|平方米|立方米|千米|分米|厘米|毫米|"
    r"毫升|千克|公里|公顷|元|吨|克|米|升|棵|本|个|人|天|小时|分钟|分|秒|时|种|张|块)"
    r"\s*$"
)
# 解方程里 "x = 3" / "x＝3" 的前缀
_VAR_PREFIX_RE = re.compile(r"^[a-zA-Z]\s*[=＝]\s*")
_MULTI_SEP = re.compile(r"[；;]|(?:\s*,\s*)|(?:，)|(?:、)")


def normalize(text: object) -> str:
    """单空答案归一化。"""
    if text is None:
        return ""
    s = unicodedata.normalize("NFKC", str(text)).strip()
    if not s:
        return ""
    s = _VAR_PREFIX_RE.sub("", s)
    s = re.sub(r"\s+", "", s)
    s = s.replace("％", "%").replace("：", ":").replace("＝", "=")
    # 去掉自研分数标记 [[a/b]]：选择题记录的答案是带标记的选项文本，
    # 而手输答案不带标记，归一化到同一形态后两者才能互认。
    s = s.replace("[[", "").replace("]]", "")
    s = _UNIT_RE.sub("", s)
    s = s.rstrip("%")
    s = _UNIT_RE.sub("", s)  # "240千米%" 这类重叠情况再剥一次
    return s.strip()


def _to_fraction(s: str) -> Fraction | None:
    """支持 "3/4"、"0.75"、"3:4"、"12"。"""
    if not s:
        return None
    try:
        if "/" in s:
            num, den = s.split("/", 1)
            return Fraction(num.strip()) / Fraction(den.strip())
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:
                return Fraction(parts[0].strip()) / Fraction(parts[1].strip())
        return Fraction(s)
    except (ValueError, ZeroDivisionError, ArithmeticError):
        return None


def _single_equal(answer: str, student: str) -> bool:
    a, b = normalize(answer), normalize(student)
    if not b:
        return False
    if a == b:
        return True
    fa, fb = _to_fraction(a), _to_fraction(b)
    if fa is not None and fb is not None:
        return fa == fb
    # 判断题：接受 √/✓/对/V 与 ×/✗/错/X
    return _truthy(a) is not None and _truthy(a) == _truthy(b)


def _truthy(s: str) -> bool | None:
    t = s.strip().upper()
    if t in ("√", "✓", "V", "对", "正确", "T", "TRUE", "是"):
        return True
    if t in ("×", "✗", "X", "错", "错误", "F", "FALSE", "否"):
        return False
    return None


def is_correct(answer: str, student: str) -> bool:
    """判断一道题是否答对。支持多空题（答案以 ；分隔）。"""
    if student is None or not str(student).strip():
        return False
    ans_parts = [p for p in _MULTI_SEP.split(str(answer)) if p.strip()]
    stu_parts = [p for p in _MULTI_SEP.split(str(student)) if p.strip()]
    if len(ans_parts) != len(stu_parts):
        # 学生用空格分隔多空答案时，退化为按空白切分再比一次
        stu_parts = str(student).split()
        stu_parts = [p for p in stu_parts if p.strip()]
    if len(ans_parts) != len(stu_parts):
        return False
    # 多空题整题给分：任何一空错，整题不得分（与真实阅卷一致）
    return all(_single_equal(a, s) for a, s in zip(ans_parts, stu_parts))


def grade_items(items: list[dict], answers: dict[int, str]) -> dict:
    """给整卷判分。

    items: 来自 paper_items 的行（含 id/seq/slot/score/answer/knowledge_id）
    answers: {item_id: 学生答案}
    """
    per_item: list[dict] = []
    got = 0
    total = 0
    for it in items:
        score = int(it["score"])
        total += score
        stu = answers.get(int(it["id"]), "")
        ok = is_correct(str(it["answer"]), stu)
        add = score if ok else 0
        got += add
        per_item.append({
            "item_id": int(it["id"]),
            "seq": int(it["seq"]),
            "slot": it["slot"],
            "knowledge_id": it["knowledge_id"],
            "score": score,
            "got": add,
            "student_answer": stu if str(stu).strip() else "",
            "is_correct": 1 if ok else 0,
            "unanswered": 0 if str(stu).strip() else 1,
        })

    module_stat: dict[str, dict] = {}
    for it, r in zip(items, per_item):
        m = it["module"]
        st = module_stat.setdefault(m, {"module": m, "total": 0, "got": 0, "wrong": 0})
        st["total"] += r["score"]
        st["got"] += r["got"]
        if not r["is_correct"]:
            st["wrong"] += 1

    slot_stat: dict[str, dict] = {}
    for it, r in zip(items, per_item):
        s = it["slot"]
        st = slot_stat.setdefault(s, {"slot": s, "total": 0, "got": 0, "count": 0, "wrong": 0})
        st["total"] += r["score"]
        st["got"] += r["got"]
        st["count"] += 1
        if not r["is_correct"]:
            st["wrong"] += 1

    wrong_knowledge: dict[str, int] = {}
    for it, r in zip(items, per_item):
        if not r["is_correct"]:
            wrong_knowledge[it["knowledge_id"]] = wrong_knowledge.get(it["knowledge_id"], 0) + 1

    return {
        "per_item": per_item,
        "total": total,
        "got": got,
        "unanswered": sum(r["unanswered"] for r in per_item),
        "module_stat": list(module_stat.values()),
        "slot_stat": list(slot_stat.values()),
        "wrong_knowledge": wrong_knowledge,
    }
