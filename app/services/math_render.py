"""数学文本渲染：把自研轻量标记转成 HTML，Web 与 PDF 共用同一份输出。

支持的标记（刻意保持极小，避免引入 KaTeX/ MathJax 依赖）：
    [[3/4]]        普通分数
    [[2/3]]米      分数后紧跟单位
    [[1又2/3]]     带分数（写作 [[1+2/3]]）
不做 LaTeX，因为 PDF 链路不需要 JS 渲染，标记越小越不容易出错。
"""
from __future__ import annotations

import re

_FRAC_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _render_one(expr: str) -> str:
    """单个 [[ ]] 片段 -> HTML 分数。"""
    body = expr.strip()
    if "/" in body:
        whole = ""
        if "+" in body and body.index("+") < body.index("/"):
            whole, body = body.split("+", 1)
        num, den = body.split("/", 1)
        frac = (
            '<span class="frac"><span class="num">'
            f"{num.strip()}</span>"
            f'<span class="den">{den.strip()}</span></span>'
        )
        if whole:
            return f'<span class="mixed">{whole.strip()}{frac}</span>'
        return frac
    return f"<span class='math-inline'>{body}</span>"


def render_math(text: str) -> str:
    """把整段文本中的分数标记替换为 HTML。"""
    if not text:
        return text
    return _FRAC_RE.sub(lambda m: _render_one(m.group(1)), text)


def check_marks(text: str) -> list[str]:
    """校验标记是否配对正确。返回问题描述列表（空表示通过）。"""
    problems: list[str] = []
    if not text:
        return problems
    if text.count("[[") != text.count("]]"):
        problems.append(f"分数标记不配对：[[ 出现 {text.count('[[')} 次，]] 出现 {text.count(']]')} 次")
    depth = 0
    i = 0
    while i < len(text):
        if text.startswith("[[", i):
            depth += 1
            i += 2
            continue
        if text.startswith("]]", i):
            depth -= 1
            i += 2
            if depth < 0:
                problems.append("出现多余的 ]]")
            continue
        i += 1
    if depth != 0:
        problems.append(f"存在未闭合的 [[ （深度={depth}）")
    for frag in _FRAC_RE.findall(text):
        body = frag.strip()
        core = body.split("+")[-1] if "+" in body else body
        if "/" in core:
            parts = core.split("/")
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                problems.append(f"分数片段格式错误：[[{frag}]]")
            elif parts[1].strip() == "0":
                problems.append(f"分母为零：[[{frag}]]")
    return problems
