# -*- coding: utf-8 -*-
"""判分器用例：重点覆盖"容易误判"的边界，而不是 happy path。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.grader import is_correct, normalize  # noqa: E402

# (标准答案, 学生答案, 期望是否判对)
CASES = [
    # --- 必须判对的形式差异 ---
    ("3/4", "0.75", True),
    ("0.75", "3/4", True),
    ("0.5", "1/2", True),
    ("2/4", "1/2", True),
    ("1/2", "2/4", True),
    ("42%", "42", True),
    ("42", "42%", True),
    ("96 元", "96", True),
    ("96", "96元", True),
    ("96", "96 元", True),
    ("240 千米", "240", True),
    ("x = 3", "3", True),
    ("x=3", "3", True),
    ("7 : 2", "7:2", True),
    ("7:2", "7 : 2", True),
    ("√", "✓", True),
    ("√", "对", True),
    ("×", "错", True),
    ("1500；1500；45", "1500；1500；45", True),
    ("1500；1500；45", "1500 1500 45", True),
    ("6；546", "6；546", True),
    ("2/11", "2/11", True),
    ("[[2/11]]", "2/11", True),    # 选项文本带自研分数标记，手输不带
    ("0.24", ".24", True),
    ("294；343", "294；343", True),
    ("13", "13", True),
    ("115/8", "14.375", True),
    ("800918006；80092", "800918006；80092", True),

    # --- 必须判错 ---
    ("3/4", "4/3", False),
    ("3/4", "3/5", False),
    ("96", "95", False),
    ("96", "", False),
    ("96", "   ", False),
    ("×", "√", False),
    ("1500；1500；45", "1500；1500；46", False),
    ("1500；1500；45", "1500；45", False),   # 少填一空不给分
    ("7 : 2", "2 : 7", False),
    ("21", "20", False),
    ("343", "344", False),
]

FAILED = []
for ans, stu, want in CASES:
    try:
        got = is_correct(ans, stu)
    except Exception as exc:  # noqa: BLE001
        got = f"EXC {type(exc).__name__}: {exc}"
    if got != want:
        FAILED.append((ans, stu, want, got))

print(f"用例总数：{len(CASES)}，失败：{len(FAILED)}")
print("=" * 70)
for ans, stu, want, got in FAILED:
    print(f"  答案={ans!r}  学生={stu!r}  期望={want}  实得={got}")

# 归一化本身也要抽查
print()
print("归一化抽查：")
for s in ["96 元", "42%", "x = 3", "7 : 2", "2 400 千米"]:
    print(f"  {s!r:16s} -> {normalize(s)!r}")

print()
print("PASS：判分器全部用例通过" if not FAILED else f"FAIL：{len(FAILED)} 条不符")
sys.exit(1 if FAILED else 0)
