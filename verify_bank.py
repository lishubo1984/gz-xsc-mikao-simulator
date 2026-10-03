"""一次性验证脚本：跨多个 seed 出卷，统计模板覆盖情况，确认 W5 扩充题库生效。"""
from __future__ import annotations
import json
import urllib.request

BASE = "http://127.0.0.1:8765"
# 全部 25 个 W5 扩充模板（exp_*），用于逐题核对是否真正落卷
EXP_IDS = [
    # expansion.jsonc
    "exp_fp_unit_02", "exp_fp_percent_06", "exp_tv_basic_02", "exp_tv_basic_03",
    "exp_rp_ratio_02", "exp_rp_dist_01", "exp_rp_judge_01", "exp_gm_solid_02",
    "exp_cr_fill_01", "exp_cr_fill_02", "exp_ie_fill_01", "exp_ie_fill_02",
    "exp_na_prime_02", "exp_na_est_02",
    # expansion2.jsonc
    "exp_tv_solve_02", "exp_na_simple_03", "exp_fp_concentration_02",
    "exp_gm_choice_02", "exp_gm_circle_02", "exp_fp_growth_01", "exp_rp_prop_01",
    "exp_na_pattern_02", "exp_tv_choice_01", "exp_na_column_02", "exp_ph_fill_01",
]


def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def get(url):
    req = urllib.request.Request(url, headers={})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def main():
    seeds = list(range(1, 81))
    draw_count = {q: 0 for q in EXP_IDS}   # 每个 exp_ 模板被抽中的次数
    papers_ok = 0
    papers_fail = 0

    for s in seeds:
        try:
            created = post(f"{BASE}/api/papers", {"seed": s, "student": "verify"})
        except Exception as e:  # noqa
            papers_fail += 1
            print(f"seed={s} 生成失败: {e}")
            continue
        if not created.get("check_passed"):
            papers_fail += 1
            print(f"seed={s} 体检未通过")
            continue
        papers_ok += 1
        detail = get(f"{BASE}/api/papers/{created['paper_id']}")
        for it in detail["items"]:
            q = it["question_id"]
            if q in draw_count:
                draw_count[q] += 1

    total_draws = sum(draw_count.values())
    drawn = [q for q in EXP_IDS if draw_count[q] > 0]
    starved = [q for q in EXP_IDS if draw_count[q] == 0]
    print("=" * 64)
    print(f"成功出卷: {papers_ok} 份, 失败: {papers_fail} 份 (80 seeds)")
    print(f"exp_ 模板落卷总条次: {total_draws}")
    print(f"已落卷 exp_ 模板数: {len(drawn)} / {len(EXP_IDS)}")
    print("=" * 64)
    print("\n[逐题] 25 个 W5 exp_ 模板被抽中次数 (80 卷累计):")
    for q in EXP_IDS:
        flag = "OK" if draw_count[q] > 0 else "★★ 仍未被抽中"
        print(f"  {q:22s} x{draw_count[q]:3d}  {flag}")
    print("\n[结论] 仍为零覆盖(可能死模板):", starved if starved else "无 —— 全部 25 个均已落卷")


if __name__ == "__main__":
    main()
