# -*- coding: utf-8 -*-
"""把题库中的 choices_expr 从「Python 列表字面量字符串」转成「JSON 数组」。

设计不一致的根源：早期模板照搬了 Python 源码里的写法
    "choices_expr": "['{a}', '{b}']"
在 JSON 里它是一个字符串，需要二次解析才能用；而其余字段都是原生 JSON 类型。
统一为 JSON 数组后，加载、校验、渲染三处用同一份语义，不再需要二次解析。

转换是幂等的：已是数组的条目跳过。
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

BANK = Path(__file__).resolve().parent.parent / "data" / "bank"

# 匹配  "choices_expr": "[ ... ]"
PATTERN = re.compile(r'"choices_expr"\s*:\s*"(\[[^\n]*?\])"', re.S)


def convert(text: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        raw = m.group(1)
        # 把 python 风格的列表字面量转成 JSON：单引号 -> 双引号
        body = raw.strip()
        try:
            py_list = json.loads(body.replace("'", '"'))
            n += 1
            return '"choices_expr": ' + json.dumps(py_list, ensure_ascii=False)
        except json.JSONDecodeError:
            return m.group(0)

    return PATTERN.sub(repl, text), n


total = 0
for p in sorted(BANK.glob("*.jsonc")):
    src = p.read_text(encoding="utf-8")
    p.with_suffix(".jsonc.bak").write_text(src, encoding="utf-8")
    new, cnt = convert(src)
    if cnt:
        parts = new.splitlines(keepends=True)
        # 保持 JSON 缩进风格：把内联数组还原到一行（原文件本就单行）
        p.write_text(new, encoding="utf-8")
        total += cnt
        print(f"  {p.name}: 转换 {cnt} 处")
    else:
        print(f"  {p.name}: 无需转换")

print(f"合计 {total} 处")

print("=== 转换后逐文件 JSON 校验 ===")
bad = False
for p in sorted(BANK.glob("*.jsonc")):
    src = "\n".join(
        line for line in p.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//")
    )
    try:
        data = json.loads(src)
        choices_ok = all(
            isinstance(q["choices_expr"], list) for q in data if q.get("choices_expr")
        )
        print(f"  OK   {p.name}: {len(data)} 题，choices_expr 均为数组 = {choices_ok}")
    except json.JSONDecodeError as e:
        bad = True
        print(f"  FAIL {p.name}: {e}")
if bad:
    sys.exit(1)
print("ALL_OK")
