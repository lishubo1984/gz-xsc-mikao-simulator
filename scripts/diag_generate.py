# -*- coding: utf-8 -*-
"""诊断出卷失败的具体环节：是抽题数量不足，还是体检拦下。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.services import qa_checker  # noqa: E402
from app.services.generator import (  # noqa: E402
    _k_map, _pick_templates, build_module_index, load_bank, load_graph,
    render_question,
)

graph = load_graph()
bank = load_bank()
build_module_index(graph, bank)
kn_map = _k_map(graph)
layout = graph["paper_layout"]
module_targets = {m["id"]: m["target_ratio"] for m in graph["modules"]}

print(f"题库题数：{len(bank)}")
print()
print("各 slot × module 的可用题数（对照卷面配额）：")
print(f"{'slot':10s} {'module':22s} {'可用':>4s} {'需要':>4s}  判定")
print("-" * 62)
short = []
for sec in sorted(layout["sections"], key=lambda s: s["order"]):
    slot = sec["slot"]
    for module, cell in sec["quota"].items():
        pool = [t for t in bank
                if t["slot"] == slot
                and kn_map.get(t["knowledge_id"], {}).get("module") == module]
        flag = "OK" if len(pool) >= cell else "!! 不足"
        if len(pool) < cell:
            short.append((slot, module, len(pool), cell))
        print(f"{slot:10s} {module:22s} {len(pool):4d} {cell:4d}  {flag}")

print()
if short:
    print(f"发现 {len(short)} 个格子题量不足，无法组卷：")
    for s, m, have, need in short:
        print(f"  {s} / {m}: 有 {have} 题，需要 {need} 题")
    sys.exit(1)

print("题量充足，实际跑一遍看体检报告：")
import random  # noqa: E402

rng = random.Random(1)
items = []
seq = 0
seen: set[str] = set()
for sec in sorted(layout["sections"], key=lambda s: s["order"]):
    for module, cell in sec["quota"].items():
        picked = _pick_templates(bank, sec["slot"], module, cell, seen, rng, kn_map)
        for tpl in picked:
            seq += 1
            r = render_question(tpl, kn_map, rng)
            r.update({"seq": seq, "score": sec["per_score"],
                      "section_title": sec["title"]})
            seen.add(tpl["id"])
            items.append(r)

print(f"组卷完成，共 {len(items)} 题，总分 {sum(i['score'] for i in items)}")
rep = qa_checker.check_paper(items, layout, module_targets)
print(f"体检：通过={rep.passed}  ERROR={len(rep.errors)}  WARN={len(rep.warnings)}")
print()
if rep.errors:
    print("ERROR 明细：")
    for e in rep.errors:
        print(f"  [{e.code}] seq={e.seq} {e.detail}")
print()
if rep.warnings:
    print("WARN 明细：")
    for w in rep.warnings:
        print(f"  [{w.code}] seq={w.seq} {w.detail}")
print()
print("统计：", rep.stats)
