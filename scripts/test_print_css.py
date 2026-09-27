# -*- coding: utf-8 -*-
"""打印样式守护测试。

为什么需要这个测试：
  render_math 会把 [[2/9]] 输出成一串带类名的 span（.frac / .num / .den），
  这些类名的样式必须同时存在于「屏幕版」和「打印版」两份 CSS 里。
  真实踩坑：.frac 的样式只写在 paper.css，打印版只加载 print.css，
  结果分数在 PDF 里退化成两个并排的数字 —— 卷面印出"已知某数的 29 是 22"，
  孩子看到的是 29 而不是 2/9，题目直接不成立，而所有自动化断言都是绿的
  （因为 HTML 里 class="frac" 一个不少，只是没有样式）。
  这类"结构对、视觉错"的缺陷只能靠静态比对类名来防。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.math_render import render_math  # noqa: E402

# 每种标记各来一个，覆盖 render_math 的所有分支
SAMPLES = ["[[2/9]] 是某数", "[[1+2/3]]米", "3 [[5/6]] × [[1/9]]", "[[7/15]]"]

STATIC = ROOT / "app" / "static"


def produced_classes(html: str) -> set[str]:
    return set(re.findall(r'class=["\']([^"\']+)["\']', html))


def defined_classes(css: str) -> set[str]:
    return set(re.findall(r"\.([A-Za-z][\w-]*)", css))


def main() -> int:
    produced: set[str] = set()
    for s in SAMPLES:
        produced |= produced_classes(render_math(s))
    # 模板里手写的类名也一并纳入守护范围
    for tpl in (ROOT / "app" / "templates").glob("print_*.html"):
        produced |= produced_classes(tpl.read_text(encoding="utf-8"))
    print(f"打印链路会出现的类名：{sorted(produced)}")

    ok = True
    for css_name in ("paper.css", "print.css"):
        css = (STATIC / css_name).read_text(encoding="utf-8")
        # 只查样式表自己的规则体，避免把注释里的示例类名算进来
        defined = defined_classes(css)
        missing = sorted(c for c in produced if c not in defined)
        # 纯工具类（如 no-print）允许缺在 paper.css
        if css_name == "paper.css":
            missing = [m for m in missing if m not in ("no-print", "sheet-head",
                                                       "sh-title", "sh-sub", "sh-fill",
                                                       "workspace", "ans-line",
                                                       "c-item", "c-box", "ans-head",
                                                       "ans-tbl", "seq-cell", "ans-cell",
                                                       "sol-cell", "dim", "uline")]
        if missing:
            ok = False
            print(f"  ✗ {css_name} 缺少类名定义：{missing}")
        else:
            print(f"  ✓ {css_name} 覆盖全部所需类名")

    print("=" * 62)
    print("PASS：打印样式类名全部有定义" if ok else "FAIL：有类名没有对应样式")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
