# -*- coding: utf-8 -*-
"""生成一份"人看的"样卷文本，用于人工验收题面质量。

自动化断言能保证「答案对、选项不重复、不出现假分数」，
但「读起来像不像一张真的小升初密考卷」只能靠人过目。
这个脚本把一份卷的题目、选项、答案、解题思路打成纯文本，
方便直接贴出来看，不必开浏览器。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.generator import generate_paper  # noqa: E402
from app.db.session import engine  # noqa: E402


def main() -> int:
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 20260930
    paper = generate_paper(engine=engine, seed=seed)
    items = paper["items"]

    out: list[str] = []
    out.append(f"《{paper['title']}》")
    out.append(f"满分 {paper['total_score']} 分 · 时间 {paper['duration_min']} 分钟 · "
               f"共 {len(items)} 题 · 体检 {'通过' if paper['check_report']['passed'] else '不通过'}")
    out.append("=" * 78)

    cur = None
    for it in items:
        if it["section_title"] != cur:
            cur = it["section_title"]
            out.append("")
            out.append(f"【{cur}】")
            if it.get("section_instruction"):
                out.append(f"  （{it['section_instruction']}）")
        out.append("")
        out.append(f"{it['seq']}. （{it['score']} 分）{it['stem']}")
        if it.get("figure_svg"):
            out.append(f"    [附图形 SVG，{len(it['figure_svg'])} 字节]")
        if it.get("choices"):
            out.append("    " + "　".join(
                f"{'ABCD'[i]}. {c}" for i, c in enumerate(it["choices"])))
        out.append(f"    ✔ 答案：{it['answer']}")

    out.append("")
    out.append("=" * 78)
    out.append("参考答案与解题思路")
    out.append("=" * 78)
    for it in items:
        out.append("")
        out.append(f"{it['seq']}. 答案：{it['answer']}")
        sol = (it.get('solution') or "").strip()
        if sol:
            out.append(f"   思路：{sol}")

    text = "\n".join(out)
    dst = ROOT / "exports" / f"sample_paper_{seed}.txt"
    dst.write_text(text, encoding="utf-8")
    print(text)
    print()
    print("已保存：", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
