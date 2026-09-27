# -*- coding: utf-8 -*-
"""全题库逐题审计：每个模板随机渲染 N 次，把所有潜伏缺陷一次性揪出来。

为什么不追 seq 编号：
  组卷是随机抽样，每次跑出来的 seq=18 / seq=24 指向的模板都不一样，
  顺着编号查等于用散弹枪打靶。正确做法是把缺陷定位前移到「模板」这一层：
  每个模板独立渲染几百次，任何参数组合下会出的问题，这里必然暴露。
"""
import random
import sys
import zlib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from app.core.config import MODULE_LABELS  # noqa: E402
from app.services import qa_checker  # noqa: E402
from app.services.generator import (  # noqa: E402
    _k_map, build_module_index, load_bank, load_graph, render_question,
)

ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 300

graph = load_graph()
bank = load_bank()
build_module_index(graph, bank)
kn_map = _k_map(graph)

print(f"题库模板数：{len(bank)}，每个渲染 {ROUNDS} 次")
print("=" * 78)

# template_id -> Counter(issue_code) ; 以及每个 code 的一个样例
summary: dict[str, Counter] = defaultdict(Counter)
samples: dict[tuple[str, str], tuple[dict, str, dict]] = {}
render_errors: dict[str, str] = {}

for tpl in bank:
    tid = tpl["id"]
    for i in range(ROUNDS):
        seed = zlib.crc32(f"{tid}#{i}".encode("utf-8"))
        rng = random.Random(seed)
        try:
            r = render_question(tpl, kn_map, rng)
        except Exception as exc:
            render_errors[tid] = f"{type(exc).__name__}: {exc}"
            break

        rep = qa_checker.CheckReport()
        qa_checker.check_placeholders(r["stem"], "题干", 1, rep)
        qa_checker.check_placeholders(r["solution"] or "", "解题思路", 1, rep)
        for idx, ch in enumerate(r["choices"] or []):
            qa_checker.check_placeholders(ch, f"选项{idx + 1}", 1, rep)
            qa_checker.check_math_marks(ch, f"选项{idx + 1}", 1, rep)
            qa_checker.check_fraction_form(ch, f"选项{idx + 1}", 1, rep)
        qa_checker.check_math_marks(r["stem"], "题干", 1, rep)
        qa_checker.check_fraction_form(r["stem"], "题干", 1, rep)
        qa_checker.check_fraction_form(r["solution"] or "", "解题思路", 1, rep)
        qa_checker.check_answer_domain(r["answer"], r["module"], r["unit"], 1, rep)
        qa_checker.check_figure_bounds(r["figure_svg"] or "", 1, rep)

        if tpl["slot"] == "choice":
            ch = [str(c).strip() for c in (r["choices"] or [])]
            ans = str(r["answer"]).strip()
            if len(ch) != 4:
                rep.add("ERROR", "CHOICE_COUNT", f"选项数 {len(ch)}：{ch}", 1)
            else:
                if ans not in ch:
                    rep.add("ERROR", "CHOICE_ANSWER_MISSING", f"答案 {ans} 不在 {ch}", 1)
                if len(set(ch)) != 4:
                    rep.add("ERROR", "CHOICE_DUPLICATE", f"选项重复：{ch}", 1)
        if tpl["slot"] == "judge":
            if str(r["answer"]).strip() not in ("√", "×"):
                rep.add("ERROR", "JUDGE_ANSWER", f"判断题答案 {r['answer']!r}", 1)

        for iss in rep.issues:
            summary[tid][iss.code] += 1
            key = (tid, iss.code)
            if key not in samples:
                params = {}
                # 复算一次拿到参数，便于定位具体是哪组取值出问题
                from app.services.renderer import roll_params
                rng2 = random.Random(seed)
                params = roll_params(tpl.get("params", {}), rng2) if tpl.get("params") else {}
                samples[key] = (params, iss.detail, r)

print("渲染崩溃（模板本身有 bug）：")
if render_errors:
    for tid, err in render_errors.items():
        print(f"  ✗ {tid}: {err}")
else:
    print("  无")
print()

bad_tpls = sorted(summary.keys())
print(f"有问题的模板：{len(bad_tpls)} / {len(bank)}")
print("-" * 78)

for tid in bad_tpls:
    codes = summary[tid]
    tpl = next(t for t in bank if t["id"] == tid)
    node = kn_map.get(tpl["knowledge_id"], {})
    print(f"\n[{tid}]  slot={tpl['slot']}  kn={tpl['knowledge_id']}  "
          f"module={MODULE_LABELS.get(node.get('module', ''), '?')}")
    print(f"   stem: {tpl['stem'][:70]}")
    for code, cnt in codes.most_common():
        rate = cnt / ROUNDS * 100
        params, detail, rendered = samples[(tid, code)]
        print(f"   - {code}  命中 {cnt}/{ROUNDS} ({rate:.1f}%)")
        print(f"       params: {params}")
        print(f"       detail: {detail}")
        if code in ("CHOICE_DUPLICATE", "CHOICE_ANSWER_MISSING", "CHOICE_COUNT"):
            print(f"       choices: {rendered['choices']}  answer: {rendered['answer']}")

print()
print("=" * 78)
print(f"审计结论：{'存在问题' if (bad_tpls or render_errors) else '全部通过'}，"
      f"共 {len(bad_tpls)} 个模板有缺陷、{len(render_errors)} 个渲染崩溃")
