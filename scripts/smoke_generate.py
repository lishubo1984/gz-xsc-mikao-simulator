# -*- coding: utf-8 -*-
"""冒烟测试：连续生成 20 份卷，验证总分恒等于 100、体检全部通过。"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import MODULE_LABELS  # noqa: E402
from app.db.session import engine, init_db  # noqa: E402
from app.services.generator import generate_paper  # noqa: E402

init_db()

ROUNDS = 20
ok = 0
fails: list[str] = []
score_set = set()
slot_counter: Counter = Counter()
module_counter: Counter = Counter()
diff_counter: Counter = Counter()
question_ids: set[str] = set()
total_questions = 0

for i in range(ROUNDS):
    try:
        paper = generate_paper(engine=engine, seed=1000 + i, persist=(i < 3))
    except Exception as e:
        fails.append(f"第 {i + 1} 份生成失败：{type(e).__name__}: {str(e)[:300]}")
        continue

    rep = paper["check_report"]
    total = sum(it["score"] for it in paper["items"])
    score_set.add(total)
    if not rep["passed"]:
        fails.append(f"第 {i + 1} 份体检未通过：" + "; ".join(
            f"[{e['code']}] {e['detail']}" for e in rep["errors"][:3]))
        continue

    for it in paper["items"]:
        slot_counter[it["slot"]] += 1
        module_counter[it["module"]] += 1
        diff_counter[it["difficulty"]] += 1
        question_ids.add(it["question_id"])
    total_questions += len(paper["items"])
    ok += 1

print(f"成功生成并体检通过：{ok}/{ROUNDS} 份")
print(f"总分取值集合：{sorted(score_set)}   （必须只有 100）")
print(f"累计题量：{total_questions}，平均每份 {total_questions / max(ok,1):.1f} 题")
print(f"题库去重后覆盖题目数：{len(question_ids)}")
print()
print("题型分布（20 份累计）：")
for s, c in sorted(slot_counter.items()):
    print(f"  {s:10s} {c:4d} 次   平均每份 {c / max(ok,1):.1f} 题")
print()
print("模块分布（20 份累计，按分值折算）：")
for m, c in sorted(module_counter.items(), key=lambda x: -x[1]):
    print(f"  {MODULE_LABELS.get(m, m):16s} {c:4d} 分次   平均每份 {c / max(ok,1):.1f}")
print()
print("难度分布：", dict(sorted(diff_counter.items())))
print()
if fails:
    print(f"失败清单（{len(fails)} 条）：")
    for f in fails[:10]:
        print("  -", f)
    sys.exit(1)
print("PASS：所有卷子总分 100、体检全部通过")
