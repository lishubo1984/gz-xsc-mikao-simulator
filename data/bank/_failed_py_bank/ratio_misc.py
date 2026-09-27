# -*- coding: utf-8 -*-
"""题库 4/4：比和比例（目标 10 分）+ 其他综合应用（目标 8 分）。"""
from __future__ import annotations

RATIO_PROPORTION: list[dict] = [
    {
        "id": "rp_meaning_01",
        "knowledge_id": "ratio_meaning",
        "slot": "fill",
        "stem": "{a} : {b} 的比值是（　　），化成最简整数比是（　　）。",
        "answer_expr": "Fraction({a}, {b})",
        "answer_display": "{ans}；{simplest}",
        "params": {
            "a": {"type": "choice", "from": [12, 18, 24, 36, 48]},
            "b": {"type": "choice", "from": [16, 20, 30, 40, 60]},
        },
        "solution": "比值是一个数，用前项除以后项求得：{a} ÷ {b} = {ans}；"
                    "化简比是一个比，要把前项和后项同时除以它们的最大公因数，"
                    "得到最简整数比 {simplest}。"
                    "易错点：化简比的结果必须写成"a : b"的形式，不能写成一个数。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "rp_distribution_01",
        "knowledge_id": "ratio_distribution",
        "slot": "solve",
        "stem": "学校把 {total} 本图书按 {a} : {b} : {c} 分给四、五、六三个年级。"
                "六年级分到多少本？",
        "answer_expr": "{total} // ({a} + {b} + {c}) * {c}",
        "answer_display": "{ans} 本",
        "params": {
            "total": {"type": "choice", "from": [360, 540, 630, 720, 900]},
            "a": {"type": "choice", "from": [2, 3, 4]},
            "b": {"type": "choice", "from": [3, 4, 5]},
            "c": {"type": "choice", "from": [4, 5, 6]},
        },
        "solution": "按比例分配的做法是“先求总份数，再求每份数”："
                    "总份数 = {a} + {b} + {c} = {s}（份）；"
                    "每一份 = {total} ÷ {s} = {per}（本）；"
                    "六年级占 {c} 份，即 {per} × {c} = {ans}（本）。"
                    "也可以直接用 {total} × {c}/{s} 求出来。",
        "difficulty": 3,
        "unit": "本",
    },
    {
        "id": "rp_proportion_01",
        "knowledge_id": "proportion_property",
        "slot": "fill",
        "stem": "如果 {a} : {b} = x : {d}，那么 x = （　　）。",
        "answer_expr": "Fraction({a} * {d}, {b})",
        "answer_display": "{ans}",
        "params": {
            "a": {"type": "int", "min": 2, "max": 12},
            "b": {"type": "int", "min": 2, "max": 12},
            "d": {"type": "int", "min": 2, "max": 12},
        },
        "solution": "根据比例的基本性质：两个内项的积等于两个外项的积。"
                    "这里内项是 {b} 和 x，外项是 {a} 和 {d}，"
                    "所以 {b}x = {a} × {d} = {ad}，"
                    "两边同除以 {b}，得 x = {ans}。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "rp_direct_01",
        "knowledge_id": "direct_inverse_proportion",
        "slot": "judge",
        "stem": "路程一定时，行驶的速度和时间成反比例。（　　）",
        "answer_expr": "1",
        "answer_display": "√",
        "params": None,
        "solution": "判断正反比例，要看两个量的乘积或比值是不是一定。"
                    "速度 × 时间 = 路程，路程一定，说明这两个量的乘积一定，"
                    "所以速度和时间成反比例，打 √。"
                    "对照记忆：乘积一定 → 反比例；比值一定 → 正比例。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "rp_meaning_02",
        "knowledge_id": "ratio_meaning",
        "slot": "choice",
        "stem": "把 {w} 克盐放入 {wt} 克水中，盐与盐水的质量比是（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['{ans}', '{w1}', '{w2}', '{w3}']",
        "params": {
            "w": {"type": "choice", "from": [10, 15, 20, 25, 30]},
            "wt": {"type": "choice", "from": [90, 100, 180, 200, 270]},
        },
        "solution": "关键区分"盐水"和"水"：盐水的质量 = 盐 + 水 = {w} + {wt} = {total}（克）。"
                    "题目问的是盐与盐水的比，所以是 {w} : {total}。"
                    "如果把"盐水"错看成"水"，就会得到错误答案 —— 这是本知识点最常见的失分点。",
        "difficulty": 3,
        "unit": None,
    },
]


MISC_COMPREHENSIVE: list[dict] = [
    {
        "id": "mc_tree_01",
        "knowledge_id": "tree_planting",
        "slot": "fill",
        "stem": "在一条长 {len_m} 米的公路一侧植树，每隔 {gap} 米栽一棵"
                "（两端都栽），一共要栽（　　）棵树；"
                "如果只有一端栽，一共要栽（　　）棵。",
        "answer_expr": "{len_m} // {gap} + 1",
        "answer_display": "{ans}；{one_end}",
        "params": {
            "len_m": {"type": "choice", "from": [40, 60, 80, 100, 120, 200]},
            "gap": {"type": "choice", "from": [4, 5, 8, 10, 20]},
        },
        "solution": "两端都栽时，棵数比间隔数多 1："
                    "间隔数 = 总长 ÷ 间隔距离 = {len_m} ÷ {gap} = {n}（个），"
                    "棵数 = {n} + 1 = {ans}（棵）。"
                    "只有一端栽时，棵数 = 间隔数 = {one_end}（棵）。"
                    "口诀：两端都栽加 1，只栽一端不加，两端都不栽减 1。",
        "difficulty": 3,
        "unit": "棵",
    },
    {
        "id": "mc_avg_01",
        "knowledge_id": "average_problem",
        "slot": "fill",
        "stem": "小明前 {n} 次数学测验的平均分是 {avg1} 分，"
                "为了使 {total_n} 次的平均分达到 {avg2} 分，"
                "他第 {tn} 次测验至少要考（　　）分。",
        "answer_expr": "{total_n} * {avg2} - {n} * {avg1}",
        "answer_display": "{ans}",
        "params": {
            "n": {"type": "choice", "from": [3, 4, 5]},
            "avg1": {"type": "choice", "from": [82, 84, 85, 88, 90]},
            "total_n": {"type": "choice", "from": [4, 5, 6]},
            "avg2": {"type": "choice", "from": [86, 88, 90, 92, 94]},
        },
        "solution": "用“总分”来建立等量关系："
                    "{total_n} 次的总分要达到 {total_n} × {avg2} = {need}（分）；"
                    "前 {n} 次已经得到 {n} × {avg1} = {got}（分）；"
                    "所以第 {tn} 次至少考 {need} − {got} = {ans}（分）。"
                    "这类题的关键是抓住"总分不变"这个整体量。",
        "difficulty": 3,
        "unit": "分",
    },
    {
        "id": "mc_pigeon_01",
        "knowledge_id": "pigeonhole",
        "slot": "judge",
        "stem": "袋中有红、黄、蓝三种颜色的球各若干个，"
                "至少摸出 4 个球，才能保证一定有 2 个球的颜色相同。（　　）",
        "answer_expr": "1",
        "answer_display": "√",
        "params": None,
        "solution": "用抽屉原理（最不利原则）：三种颜色看作 3 个“抽屉”。"
                    "最不巧的情况是先摸到的 3 个球颜色各不相同（红、黄、蓝各 1 个），"
                    "第 4 个球无论什么颜色，都会和前面某一个同色。"
                    "所以摸 4 个能保证有 2 个同色，打 √。"
                    "结论要有"保证"两个字，就必须按最不利情况来想。",
        "difficulty": 4,
        "unit": None,
    },
    {
        "id": "mc_probability_01",
        "knowledge_id": "stats_probability",
        "slot": "choice",
        "stem": "袋中有 {r} 个红球和 {b} 个黄球（除颜色外完全相同），"
                "任意摸出一个球，摸到红球的可能性是（　　）。",
        "answer_expr": "Fraction({r}, {r} + {b})",
        "answer_display": "{ans}",
        "choices_expr": "['{ans}', '{w1}', '{w2}', '{w3}']",
        "params": {
            "r": {"type": "int", "min": 1, "max": 9},
            "b": {"type": "int", "min": 1, "max": 9},
        },
        "solution": "摸到红球的可能性 = 红球的个数 ÷ 球的总个数 = {r} ÷ （{r} + {b}） = {ans}。"
                    "注意：可能性是一个分数（小于或等于 1），"
                    "分母是球的总数而不是黄球数。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "mc_counting_01",
        "knowledge_id": "counting_principle",
        "slot": "choice",
        "stem": "从 {m} 种主食和 {n} 种饮料中各选一种，搭配成一份套餐，"
                "一共有（　　）种不同的搭配方法。",
        "answer_expr": "{m} * {n}",
        "answer_display": "{ans}",
        "choices_expr": "['{ans}', '{w1}', '{w2}', '{w3}']",
        "params": {
            "m": {"type": "int", "min": 2, "max": 6},
            "n": {"type": "int", "min": 2, "max": 6},
        },
        "solution": "这是乘法原理：完成“搭配套餐”这件事要分两步 —— "
                    "第一步选主食有 {m} 种方法，第二步选饮料有 {n} 种方法，"
                    "两步都完成才算完成这件事，所以用乘法：{m} × {n} = {ans}（种）。"
                    "对照：如果是"或者"的关系就用加法原理。",
        "difficulty": 4,
        "unit": "种",
    },
]


# 兼容性说明：travel_geometry.py 里的图 SVG 使用了 30cm / 20cm 这样较长的标签，
# 首次验证时出现过"最后一位被裁切"（10cm 显示成 10c）。
# 因此题库约定：SVG viewBox 的宽度必须 >= 图形最右 x 坐标 + 40，高度 >= 最下 y 坐标 + 30。
# 该约束由 app/services/qa_checker.py 的 check_figure_bounds() 强制执行。
