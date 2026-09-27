# -*- coding: utf-8 -*-
"""题库 2/4：分数与百分数应用（目标 30 分）

题面用 {var} 占位，[[a/b]] 表示分数。
参数带约束，score = cell 题数 × per_score（每个空按 per_score 折算），
answer_expr 由代码求值，答案从机制上不会错。
"""
from __future__ import annotations

FRACTION_PERCENT: list[dict] = [
    {
        "id": "fp_unit_01",
        "knowledge_id": "unit_one",
        "slot": "fill",
        "stem": "已知某数的 [[{a}/{b}]] 是 {c}，这个数是（　　）。",
        "answer_expr": "Fraction({c} * {b}, {a})",
        "answer_display": "{ans}",
        "params": {
            "a": {"type": "int", "min": 2, "max": 7},
            "b": {"type": "int", "min": 3, "max": 9},
            "c": {"type": "int", "min": 6, "max": 40},
        },
        "solution": "这里单位“1”是未知数，要用除法："
                    "单位"1" = 已知量 ÷ 对应的分率 = {c} ÷ {a}/{b} = {c} × {b}/{a} = {ans}。"
                    "牢记：求单位"1"用除法，求部分量用乘法。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "fp_fraction_01",
        "knowledge_id": "fraction_word_problem",
        "slot": "solve",
        "stem": "学校图书馆有故事书 {total} 本，科技书比故事书多 [[{a}/{b}]]。"
                "科技书有多少本？",
        "answer_expr": "int({total} * Fraction({a} + {b}, {b}))",
        "answer_display": "{ans} 本",
        "params": {
            "total": {"type": "choice", "from": [120, 180, 240, 300, 360, 480]},
            "a": {"type": "int", "min": 1, "max": 5},
            "b": {"type": "int", "min": 3, "max": 9},
        },
        "solution": "把故事书的本数看作单位“1”，科技书就是故事书的 （1 + {a}/{b}）= {ab}/{b}。"
                    "求科技书的数量，就是求 {total} 的 {ab}/{b} 是多少，用乘法："
                    "{total} × {ab}/{b} = {ans}（本）。",
        "difficulty": 3,
        "unit": "本",
    },
    {
        "id": "fp_fraction_02",
        "knowledge_id": "fraction_word_problem",
        "slot": "choice",
        "stem": "一根绳子长 {l} 米，第一次用去 [[{a}/{b}]]，第二次用去 [[{a}/{b}]] 米。"
                "两次用去的长度相比（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['第一次用去的长', '第二次用去的长', '两次一样长', '无法比较']",
        "params": {
            "l": {"type": "choice", "from": [6, 8, 12, 15, 20]},
            "a": {"type": "int", "min": 1, "max": 3},
            "b": {"type": "int", "min": 4, "max": 8},
        },
        "solution": "关键区分"分率"和"具体数量"："
                    "第一次用去的是全长的 {a}/{b}，是分率，实际长度 = {l} × {a}/{b}；"
                    "第二次用去的是 {a}/{b} 米，是具体长度。"
                    "两者含义完全不同，不能直接比较，必须各自算出或按题意判断。"
                    "本题中第一次用去的实际长度往往不等于 {a}/{b} 米，故不能选"一样长"。",
        "difficulty": 4,
        "unit": None,
    },
    {
        "id": "fp_percent_01",
        "knowledge_id": "percent_word_problem",
        "slot": "fill",
        "stem": "科学课上做种子发芽实验，种下 {total} 粒种子，有 {sprout} 粒发芽，"
                "发芽率是（　　）%。",
        "answer_expr": "round({sprout} / {total} * 100, 1)",
        "answer_display": "{ans}%",
        "params": {
            "total": {"type": "choice", "from": [40, 50, 80, 100, 200, 250]},
            "sprout": {"type": "choice", "from": [36, 42, 68, 88, 96, 180, 225]},
        },
        "solution": "发芽率 = 发芽的种子数 ÷ 试验种子总数 × 100%。"
                    "列式：{sprout} ÷ {total} × 100% = {ans}%。"
                    "注意百分率表示的是两个数的比，结果不能超过 100%。",
        "difficulty": 2,
        "unit": "%",
    },
    {
        "id": "fp_percent_02",
        "knowledge_id": "percent_change",
        "slot": "solve",
        "stem": "一件商品原价 {price} 元，商店进行促销活动，先降价 {a}% 后，"
                "又在此基础上提价 {a}%。现在的价格是多少元？",
        "answer_expr": "round({price} * (1 - {a} / 100) * (1 + {a} / 100), 2)",
        "answer_display": "{ans} 元",
        "params": {
            "price": {"type": "choice", "from": [200, 300, 400, 500, 800, 1000]},
            "a": {"type": "choice", "from": [10, 20, 25]},
        },
        "solution": "两次变化要以不同的价格为基准："
                    "① 降价后的价格 = {price} × （1 − {a}%） = {p1}（元），此时基准是原价；"
                    "② 提价后的价格 = {p1} × （1 + {a}%） = {ans}（元），此时基准是降价后的价格。"
                    "易错点：先降后升的百分数不能直接抵消，因为两次的单位"1"不同。",
        "difficulty": 4,
        "unit": "元",
    },
    {
        "id": "fp_percent_03",
        "knowledge_id": "percent_word_problem",
        "slot": "choice",
        "stem": "下面各百分率中，可能超过 100% 的是（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['出勤率', '成活率', '增长率', '合格率']",
        "params": None,
        "solution": "逐项分析：出勤率 = 出勤人数 ÷ 总人数，最多等于 100%；"
                    "成活率 = 成活数 ÷ 种植总数，最多等于 100%；"
                    "合格率 = 合格数 ÷ 抽检总数，最多等于 100%；"
                    "而增长率 = 增长的部分 ÷ 原来的数量，当增长的部分超过原来的数量时，"
                    "增长率就会大于 100%，所以选"增长率"。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "fp_concentration_01",
        "knowledge_id": "concentration",
        "slot": "solve",
        "stem": "在浓度为 {p}% 的盐水 {m} 克中，加入 {n} 克水后，"
                "盐水的浓度变为百分之几？（结果保留一位小数）",
        "answer_expr": "round({m} * {p} / 100 / ({m} + {n}) * 100, 1)",
        "answer_display": "{ans}%",
        "params": {
            "p": {"type": "choice", "from": [10, 12, 15, 20, 25]},
            "m": {"type": "choice", "from": [100, 200, 400, 500]},
            "n": {"type": "choice", "from": [50, 100, 150, 200]},
        },
        "solution": "抓住“加水前后盐的质量不变”这个关键："
                    "① 原来含盐 = {m} × {p}% = {salt}（克）；"
                    "② 加水后盐水总重 = {m} + {n} = {mt}（克），盐仍是 {salt} 克；"
                    "③ 新浓度 = {salt} ÷ {mt} × 100% ≈ {ans}%。"
                    "注意：加水只会让浓度变小，结果应小于原来的 {p}%。",
        "difficulty": 4,
        "unit": "%",
    },
    {
        "id": "fp_interest_01",
        "knowledge_id": "interest",
        "slot": "solve",
        "stem": "妈妈把 {money} 元存入银行，定期 {years} 年，年利率是 {rate}%。"
                "到期时妈妈一共可以取回多少钱？",
        "answer_expr": "round({money} + {money} * {rate} / 100 * {years}, 2)",
        "answer_display": "{ans} 元",
        "params": {
            "money": {"type": "choice", "from": [2000, 5000, 8000, 10000, 20000]},
            "years": {"type": "choice", "from": [2, 3, 5]},
            "rate": {"type": "choice", "from": [2.75, 3.0, 3.25, 3.5, 4.0]},
        },
        "solution": "分两步：① 利息 = 本金 × 利率 × 时间 = {money} × {rate}% × {years} = {interest}（元）；"
                    "② 取回的总钱数 = 本金 + 利息 = {money} + {interest} = {ans}（元）。"
                    "题目问的是"一共可以取回"，别只算利息漏加本金。",
        "difficulty": 2,
        "unit": "元",
    },
    {
        "id": "fp_engineering_01",
        "knowledge_id": "engineering",
        "slot": "solve",
        "stem": "一项工程，甲队单独做需要 {a} 天完成，乙队单独做需要 {b} 天完成。"
                "两队合作，多少天可以完成这项工程？",
        "answer_expr": "round(1 / (1 / {a} + 1 / {b}), 2)",
        "answer_display": "{ans} 天",
        "params": {
            "a": {"type": "choice", "from": [6, 8, 10, 12, 15, 20]},
            "b": {"type": "choice", "from": [12, 15, 20, 24, 30]},
        },
        "solution": "把这项工程的工作总量看作单位“1”："
                    "甲的工作效率 = 1 ÷ {a} = 1/{a}，乙的工作效率 = 1 ÷ {b} = 1/{b}。"
                    "两队合作的工作效率 = 1/{a} + 1/{b}，"
                    "合作时间 = 工作总量 ÷ 合作效率 = 1 ÷ （1/{a} + 1/{b}） ≈ {ans}（天）。",
        "difficulty": 4,
        "unit": "天",
    },
    {
        "id": "fp_engineering_02",
        "knowledge_id": "engineering",
        "slot": "choice",
        "stem": "修一条路，甲队单独修要 {a} 天，乙队单独修要 {b} 天。"
                "两队合修 {c} 天后，还剩下这条路的几分之几没有修？（　　）",
        "answer_expr": "1 - (1 / {a} + 1 / {b}) * {c}",
        "answer_display": "{ans}",
        "choices_expr": "['{ans}', '{w1}', '{w2}', '{w3}']",
        "params": {
            "a": {"type": "choice", "from": [10, 12, 15]},
            "b": {"type": "choice", "from": [20, 24, 30]},
            "c": {"type": "choice", "from": [3, 4, 5]},
        },
        "solution": "仍把全长看作单位“1”：甲乙合修的工作效率 = 1/{a} + 1/{b}；"
                    "{c} 天合修完成了 （1/{a} + 1/{b}）× {c}；"
                    "剩下的 = 1 − 已完成的 = {ans}。"
                    "注意问的是"还剩几分之几"，所以结果用分数表示，不需要具体长度。",
        "difficulty": 4,
        "unit": None,
    },
    {
        "id": "fp_reverse_01",
        "knowledge_id": "reverse_reasoning",
        "slot": "solve",
        "stem": "小明有一些零花钱，第一天花了总数的一半，第二天花了剩下的一半，"
                "第三天又花了剩下的一半，这时还剩 {left} 元。小明原来有多少元？",
        "answer_expr": "{left} * 8",
        "answer_display": "{ans} 元",
        "params": {
            "left": {"type": "choice", "from": [5, 10, 15, 20, 25, 30]},
        },
        "solution": "用倒推法（还原法）从结果往回算："
                    "第三天花掉一半后剩 {left} 元，说明第三天开始时剩 {left} × 2 = {l1} 元；"
                    "第二天花掉一半后剩 {l1} 元，说明第二天开始时剩 {l1} × 2 = {l2} 元；"
                    "第一天花掉一半后剩 {l2} 元，说明原来有 {l2} × 2 = {ans} 元。"
                    "验证：{ans} → {l2} → {l1} → {left}，与题意相符。",
        "difficulty": 3,
        "unit": "元",
    },
    {
        "id": "fp_percent_04",
        "knowledge_id": "percent_word_problem",
        "slot": "judge",
        "stem": "甲数比乙数多 25%，那么乙数就比甲数少 25%。（　　）",
        "answer_expr": "0",
        "answer_display": "×",
        "params": None,
        "solution": "两次比较的单位“1”不同。设乙数为 100，"
                    "甲数比乙数多 25% 则甲数 = 100 × （1 + 25%） = 125。"
                    "反过来，乙数比甲数少多少，要以甲数 125 为单位"1"："
                    "（125 − 100） ÷ 125 = 20%，不是 25%，故打 ×。",
        "difficulty": 4,
        "unit": None,
    },
    {
        "id": "fp_percent_05",
        "knowledge_id": "percent_change",
        "slot": "solve",
        "stem": "某商店把一件衣服按成本价提高 {a}% 后标价，"
                "又按标价打 {z} 折出售，结果每件仍获利 {profit} 元。"
                "这件衣服的成本价是多少元？",
        "answer_expr": "round({profit} / ((1 + {a} / 100) * {z} / 10 - 1), 2)",
        "answer_display": "{ans} 元",
        "params": {
            "a": {"type": "choice", "from": [40, 50, 60, 80, 100]},
            "z": {"type": "choice", "from": [7, 8, 9]},
            "profit": {"type": "choice", "from": [20, 40, 60, 80, 100]},
        },
        "solution": "设成本价为 x 元。按成本提高 {a}% 标价，标价 = （1 + {a}%）x；"
                    "打 {z} 折出售，售价 = （1 + {a}%）x × {z}/10；"
                    "利润 = 售价 − 成本 = {profit}，"
                    "列方程：（1 + {a}%）x × {z}/10 − x = {profit}，"
                    "解得 x = {ans}（元）。"
                    "关键：打"折"就是按标价的十分之几出售，{z} 折 = {z}0%。",
        "difficulty": 4,
        "unit": "元",
    },
]
