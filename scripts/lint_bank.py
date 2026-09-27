# -*- coding: utf-8 -*-
"""题库静态 Lint：加载前一次性把所有模板缺陷列出来（而不是撞到一个停一次）。

与 audit_bank.py 的分工：
  lint_bank  —— 静态检查（结构、占位符、引用未定义变量），不需要渲染
  audit_bank —— 动态检查（每个模板渲染几百次，抓参数组合导致的越界/负数/去重）

工程理由：第一次接入静态占位符校验时，load_bank 在第一个坏模板处就抛异常退出，
修完再跑又撞下一个，来回五轮。lint 一次性全量列出，一次改完。
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.generator import (  # noqa: E402
    _AUTO_NAMES, _PLACEHOLDER_RE, validate_template_safe,
)

BANK_DIR = ROOT / "data" / "bank"


def load_items():
    for path in sorted(BANK_DIR.glob("*.jsonc")):
        raw = "\n".join(
            line for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("//")
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            yield path.name, None, None, f"JSON 解析失败：{exc}"
            continue
        for item in data:
            yield path.name, item, raw, None


def main() -> int:
    total = 0
    problems: list[str] = []
    ids: dict[str, str] = {}
    for fname, item, raw, parse_err in load_items():
        total += 1
        if parse_err:
            problems.append(f"[{fname}] {parse_err}")
            continue
        tid = item.get("id", "?")
        if tid in ids:
            problems.append(f"[{fname}] id 重复：{tid}（已出现在 {ids[tid]}）")
        ids[tid] = fname
        for err in validate_template_safe(item, fname):
            problems.append(f"[{fname}] {err}")

    print(f"扫描题目：{total} 道，来自 {len(set(ids.values()))} 个文件")
    print(f"发现问题：{len(problems)} 条")
    print("=" * 78)
    for p in problems:
        print(" -", p)
    if not problems:
        print("PASS：静态检查全部通过")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
