"""参数渲染与答案求值。

设计要点：
  - 答案永不由模型生成，一律由 answer_expr 这个 Python 表达式代入变量后算出，
    从机制上杜绝答案错误。
  - eval 用空 builtins + 白名单函数，避免题库文件里的表达式变成任意代码执行。
  - 小学分数答案用 Fraction 保证最简，呈现为 "3/4" 形式。
"""
from __future__ import annotations

import ast
import math
import random
from fractions import Fraction

_SAFE_FUNCS = {
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
    "str": str,
    "len": len,
    "sum": sum,
    "sorted": sorted,
    "Fraction": Fraction,
    "math": math,
}


def _div(a, b):
    """统一除法入口：两侧都是整数 → 精确分数；否则走原生浮点语义。"""
    if isinstance(a, bool) or isinstance(b, bool):
        return a / b
    if isinstance(a, int) and isinstance(b, int):
        if b == 0:
            raise ZeroDivisionError("除数为 0")
        return Fraction(a, b)
    if isinstance(a, Fraction) or isinstance(b, Fraction):
        return Fraction(a) / Fraction(b)
    return a / b


def _round(value, ndigits: int | None = None):
    """小学题里的 round 一律是"保留几位小数"，必须返回浮点数。

    真实回归：改用精确除法后，round(1/3, 2) 会因为参数已是 Fraction
    而返回 Fraction(33, 100)，金额题、浓度题（结果保留一位小数）全被
    印成 "33/100" 这种分数 —— 与题意直接冲突。这里把 round 显式转回浮点，
    让 Fraction 只服务于「答案是分数」的题，round 服务于「答案是小数」的题。
    """
    x = float(value)
    return round(x) if ndigits is None else round(x, ndigits)


class _DivRewriter(ast.NodeTransformer):
    """把表达式里的真除 a / b 改写成 _div(a, b)。

    为什么必须动 AST 而不能靠给变量换类型（真实踩坑）：
        evaluate_answer 的流程是「substitute 先把 {a} 换成 '12' 得到字符串，
        再 eval」。到 eval 这一刻，表达式里已经全是字面量，
        命名空间里包成什么类型都影响不了 12 / 20 的结果 ——
        试过用 int 子类包裹，1/{a} 依旧算出 0.08333333333333333。
        只有改写语法树，才能让「除法的语义」真正变掉。

    只改 BinOp(/)：// 与 % 保持原生语义（小学题的整除判定依赖它们），
    也不碰字符串与函数调用。
    """

    def visit_BinOp(self, node: ast.BinOp):  # noqa: N802
        self.generic_visit(node)
        if isinstance(node.op, ast.Div):
            return ast.Call(func=ast.Name(id="_div", ctx=ast.Load()),
                            args=[node.left, node.right], keywords=[])
        return node


_REWRITER = _DivRewriter()


def _compile(expr: str):
    """编译表达式；整数除法会在语法树上被换成精确除法。

    编译失败时回退到原始表达式 —— 让 eval 抛出它原本该抛的错，
    这样错误信息仍然是「哪一行语法错」，而不是被 AST 层的异常掩盖。
    """
    try:
        tree = _REWRITER.visit(ast.parse(expr, mode="eval"))
        ast.fix_missing_locations(tree)
        return compile(tree, "<answer_expr>", "eval")
    except SyntaxError:
        return compile(expr, "<answer_expr>", "eval")


_SAFE_FUNCS = {
    # 不是内置 round：见 _round 里关于 Fraction 的回归说明
    "round": _round,
    "abs": abs,
    "min": min,
    "max": max,
    "int": int,
    "float": float,
    "str": str,
    "len": len,
    "sum": sum,
    "sorted": sorted,
    "Fraction": Fraction,
    "math": math,
    "_div": _div,
}


def _trim(value: object) -> object:
    """把整数值的 Fraction / float 还原成 int。

    _Rat 让 "8/2" 算出 Fraction(2,1) 而不是 2；若原样留在 values 里，
    后续 "{expr} 米" 这类文本替换会带上分数语义，累乘还可能把分母越滚越大。
    统一在求值出口收口。

    float 也要收口（真实踩坑）：_round 为了保证金额题不印成分数而强制转浮点，
    于是派生参数 profit = round(c * 0.12, 2) 得到 24.0，题干就印成
    "仍获利 24.0 元" —— 孩子看到的题面不该有这种机器味的小数尾巴。
    """
    if isinstance(value, Fraction) and value.denominator == 1:
        return value.numerator
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def safe_eval(expr: str, values: dict | None = None) -> object:
    """在受限命名空间里求值表达式，整数除法保留为精确分数。

    白名单只放纯函数与 Fraction/math；__builtins__ 置空，
    因此 __import__ / open / eval / exec 全部不可达。
    已实测：'__import__("os")' 会被 NameError 拦下。

    values 参数保留只为兼容旧调用点，直接 eval 的路径不依赖它
    （表达式里的变量名由 substitute 提前换成字面量）。
    """
    return eval(_compile(expr), {"__builtins__": {}}, dict(_SAFE_FUNCS))  # noqa: S307


# --------------------------------------------------------------------------
# 参数生成
# --------------------------------------------------------------------------
def roll_params(spec: dict, rng: random.Random,
                constraints: list[str] | None = None,
                max_retry: int = 200) -> dict:
    """按参数空间生成一组具体取值，并满足上层声明的约束。

    spec 示例：
        {"a": {"type": "int", "min": 2, "max": 9},
         "b": {"type": "int", "min": 2, "max": 9, "exclude": ["a"]},
         "r": {"type": "float", "min": 1, "max": 5, "step": 0.5},
         "op": {"type": "choice", "from": ["+", "-"]},
         "n": {"type": "expr", "expr": "{len_m} // {gap}"}}

    为什么要有 constraints（真实踩坑）：
      题库里 '{{sprout}} <= {{total}}'（发芽数不能超过种子总数）、
      '{{len_m}} % {{gap}} == 0'（间隔必须整除周长）这类跨参数约束，
      早期靠"把取值列表设计成天然相容"来保证，一次参数微调就漏了 —— 
      审计跑出来 38% 的卷子发芽率 225%。把约束写成模板里的声明式布尔表达式，
      由本函数重抽到满足为止，这类缺陷就不会再出现。
    """
    for attempt in range(max_retry):
        values = _roll_once(spec, rng)
        try:
            # expr 参数必须在约束通过前求值，此刻 v1-v2 可能还是 0，
            # tv_circular_01 就在这里被 ZeroDivisionError 打挂过一次。
            # 求值失败视同"这组值不合格"，交给下一轮重抽，而不是让整份卷崩掉。
            _resolve_expr_params(spec, values)
        except (ValueError, ZeroDivisionError, SyntaxError, TypeError):
            continue
        if not constraints or _all_true(constraints, values):
            return values
    raise ValueError(
        f"参数约束 {constraints} 在 {max_retry} 次重试内无解，"
        "请放宽参数空间或修正约束"
    )


def _all_true(constraints: list[str], values: dict) -> bool:
    for expr in constraints:
        filled = substitute(expr, values)
        try:
            if not safe_eval(filled, values):
                return False
        except Exception:
            return False
    return True


def _resolve_expr_params(spec: dict, values: dict) -> None:
    """type=expr 的参数由已 rolled 的变量算出（如 棵数 = 周长 ÷ 间隔）。"""
    for _ in range(10):  # 允许多轮，支持 expr 之间的相互依赖
        changed = False
        for name, cfg in spec.items():
            if cfg.get("type") != "expr" or name in values:
                continue
            if _all_known(cfg["expr"], values):
                values[name] = _trim(safe_eval(substitute(cfg["expr"], values), values))
                changed = True
        if not changed:
            break


def _all_known(expr: str, values: dict) -> bool:
    missing_marker = substitute(expr, values)
    return "{" not in missing_marker


def _roll_once(spec: dict, rng: random.Random) -> dict:
    values: dict[str, object] = {}
    for name, cfg in spec.items():
        kind = cfg.get("type", "int")
        if kind == "expr":
            continue  # 延后到 _resolve_expr_params
        if kind == "choice":
            values[name] = rng.choice(cfg["from"])
        elif kind == "float":
            step = cfg.get("step", 0.1)
            lo = cfg["min"]
            hi = cfg["max"]
            n = int(round((hi - lo) / step))
            values[name] = _clean_float(lo + rng.randint(0, n) * step)
        else:
            lo = int(cfg["min"])
            hi = int(cfg["max"])
            cand = lo
            for _ in range(40):
                cand = rng.randint(lo, hi)
                if _pass_exclude(cand, cfg, values):
                    break
            values[name] = cand
    return values


def _pass_exclude(cand: int, cfg: dict, values: dict) -> bool:
    """处理 equal_to / gt / ne 等约束，保证参数组合不会产生病态题目。"""
    for rule in cfg.get("exclude", []):
        if isinstance(rule, str):
            # 写成 "a" 表示不允许与变量 a 相等
            if rule in values and cand == values[rule]:
                return False
        elif rule.get("equal_to"):
            if cand == values.get(rule["equal_to"]):
                return False
        elif rule.get("gcd_with") is not None:
            other = values.get(rule["gcd_with"])
            if other is not None and math.gcd(int(cand), int(other)) != rule["value"]:
                return False
    for rule in cfg.get("require", []):
        if rule.get("divisible_by") and cand % rule["divisible_by"] != 0:
            return False
        if rule.get("ratio_to") and values.get(rule["ratio_to"]):
            other = Fraction(cand, int(values[rule["ratio_to"]]))
            if other != Fraction(rule["value"]):
                return False
    return True


def _clean_float(x: float) -> float:
    return float(round(x, 6))


# --------------------------------------------------------------------------
# 文本替换
# --------------------------------------------------------------------------
def substitute(text: str, values: dict) -> str:
    """把模板里的 {a} 占位符替换成实际取值。"""
    if not text:
        return text
    try:
        return text.format_map(_DefaultMap(values))
    except (KeyError, ValueError, IndexError) as exc:
        raise ValueError(f"占位符替换失败: {exc} | text={text!r}") from exc


class _DefaultMap(dict):
    """缺失的键留原样，方便体检器发现未替换占位符。"""

    def __missing__(self, key: str) -> str:  # type: ignore[override]
        return "{" + key + "}"


# --------------------------------------------------------------------------
# 答案格式化
# --------------------------------------------------------------------------
def fmt_answer(value: object) -> str:
    """把求值结果格式化成小学生写答案的形式。

    Fraction(3,4) -> "3/4"；Fraction(6,2) -> "3"；1.0 -> "1"；1.20 -> "1.2"
    """
    if isinstance(value, Fraction):
        if value.denominator == 1:
            return str(value.numerator)
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, bool):
        return "√" if value else "×"
    if isinstance(value, float):
        if math.isclose(value, round(value), abs_tol=1e-9):
            return str(int(round(value)))
        s = f"{value:.4f}".rstrip("0").rstrip(".")
        # 常用两位小数：金融/百分数场景下 .4f 尾巴处理
        return s
    return str(value)


def evaluate_answer(answer_expr: str, values: dict) -> object:
    """把 answer_expr 中的变量替换后求值。结果可能是 Fraction，交给 fmt_answer 呈现。"""
    filled = substitute(answer_expr, values)
    return _trim(safe_eval(filled, values))
