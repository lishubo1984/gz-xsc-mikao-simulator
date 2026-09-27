# -*- coding: utf-8 -*-
"""题库 1/4：数与代数（目标 30 分）

每道题是一个参数化模板：
  stem          题干，{var} 为占位，[[a/b]] 为分数标记
  answer_expr   答案表达式，代入参数后由代码求值 —— 答案永不出错
  params        参数空间
  solution      解题思路
"""
from __future__ import annotations

NUMBER_ALGEBRA: list[dict] = [
    {
        "id": "na_notation_01",
        "knowledge_id": "num_notation",
        "slot": "fill",
        "stem": "一个数由 {yi} 个亿、{wan} 个万、{qian} 个千和 {ge} 个一组成，这个数写作（　　），"
                "省略"万"后面的尾数约是（　　）万。",
        "answer_expr": "int(str({yi}) + '00000000') + int(str({wan}).zfill(4) + '0000') "
                       "+ int(str({qian}) + '000') + {ge}",
        "answer_display": "{ans}；约 {wan_part} 万",
        "params": {
            "yi": {"type": "int", "min": 1, "max": 9},
            "wan": {"type": "int", "min": 10, "max": 99},
            "qian": {"type": "int", "min": 1, "max": 9},
            "ge": {"type": "int", "min": 1, "max": 9},
        },
        "solution": "按照数位顺序表逐位写数：{yi} 个亿写在亿位，{wan} 个万写在万级，"
                    "{qian} 个千写在千位，{ge} 个一写在个位。"
                    "省略"万"后面的尾数，要看千位上的数 {qian}："
                    "{round_hint}，所以约是 {wan_part} 万。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "na_convert_01",
        "knowledge_id": "decimal_fraction_pct_convert",
        "slot": "fill",
        "stem": "把 {dec} 化成最简分数是（　　），化成百分数是（　　）%。",
        "answer_expr": "Fraction(int({dec} * 100), 100)",
        "answer_display": "{ans}；{pct}%",
        "params": {
            "dec": {"type": "choice", "from": [0.24, 0.4, 0.48, 0.6, 0.64, 0.75, 0.8, 0.85]},
        },
        "solution": "先把小数化成分母是 100 的分数，再约成最简分数；"
                    "化成百分数只需把小数点向右移动两位并添上百分号。"
                    "比如 {dec} = {dec_num}/100，分子分母同时除以它们的最大公因数化简。",
        "difficulty": 1,
        "unit": "%",
    },
    {
        "id": "na_divisibility_01",
        "knowledge_id": "divisibility",
        "slot": "choice",
        "stem": "下面四个数中，能同时被 2、3、5 整除的是（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['{a1}', '{a2}', '{a3}', '{a4}']",
        "params": {
            "a1": {"type": "choice", "from": [230, 450, 630, 870, 1230]},
            "a2": {"type": "choice", "from": [232, 452, 634, 872, 1232]},
            "a3": {"type": "choice", "from": [235, 455, 635, 875, 1235]},
            "a4": {"type": "choice", "from": [330, 550, 830, 970, 1330]},
        },
        "solution": "能同时被 2、3、5 整除的数，必须满足三个条件："
                    "① 个位是 0（被 2、5 整除）；② 各位数字之和能被 3 整除。"
                    "逐个检验：{a2} 个位是 2，不能被 5 整除；{a3} 个位是 5，不能被 2 整除；"
                    "{a4} 各位数字之和不能被 3 整除。只有 {correct} 同时满足。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "na_prime_01",
        "knowledge_id": "prime_composite",
        "slot": "judge",
        "stem": "所有的质数都是奇数，所有的偶数都是合数。（　　）",
        "answer_expr": "0",
        "answer_display": "×",
        "params": None,
        "solution": "两道判断都要过一遍：① 质数 2 是偶数，所以“所有质数都是奇数”错；"
                    "② 偶数 0、2 中，2 是质数，0 既不是质数也不是合数，所以"所有偶数都是合数"也错。"
                    "两句话都错，故打 ×。",
        "difficulty": 1,
        "unit": None,
    },
    {
        "id": "na_gcd_01",
        "knowledge_id": "gcd_lcm",
        "slot": "fill",
        "stem": "A = 2 × 3 × 7，B = 2 × 5 × 7，A 和 B 的最大公因数是（　　），最小公倍数是（　　）。",
        "answer_expr": "2 * 7",
        "answer_display": "{ans}；{lcm}",
        "params": None,
        "solution": "用分解质因数法：最大公因数取两个数公有的质因数，各取一次相乘，"
                    "即 2 × 7 = 14；最小公倍数取公有质因数和各自独有的质因数，"
                    "即 2 × 7 × 3 × 5 = 210。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "na_simple_01",
        "knowledge_id": "simple_calc",
        "slot": "calc",
        "stem": "简算：999 × {a} + {b} × {c}",
        "answer_expr": "999 * {a} + {b} * {c}",
        "answer_display": "{ans}",
        "params": {
            "a": {"type": "choice", "from": [222, 223, 224, 225]},
            "b": {"type": "choice", "from": [333, 334, 335, 336]},
            "c": {"type": "choice", "from": [333, 334, 335, 666]},
        },
        "solution": "观察数的特点：999 = 3 × 333，{b} 与 333 有关系。"
                    "把 999 × {a} 改写成 333 × {a3}（因为 999 = 3 × 333，"
                    "故 999 × {a} = 333 × {a3}），再提取公因数 333，"
                    "得 333 × （{a3} + {b2}），算出结果 {ans}。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "na_mixed_01",
        "knowledge_id": "four_mixed_ops",
        "slot": "calc",
        "stem": "计算：{a} ÷ [[1/{b}]] × [[{c}/{d}]]",
        "answer_expr": "{a} * {b} * Fraction({c}, {d})",
        "answer_display": "{ans}",
        "params": {
            "a": {"type": "int", "min": 2, "max": 12},
            "b": {"type": "int", "min": 2, "max": 9},
            "c": {"type": "int", "min": 1, "max": 8},
            "d": {"type": "int", "min": 2, "max": 9},
        },
        "solution": "除以一个数（0 除外）等于乘这个数的倒数，所以 {a} ÷ 1/{b} = {a} × {b} = {ab}；"
                    "再乘 {c}/{d}，得 {ab} × {c}/{d} = {ans}。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "na_equation_01",
        "knowledge_id": "equation_solve",
        "slot": "calc",
        "stem": "解方程：{a}x : {b} = {c} : {d}",
        "answer_expr": "Fraction({b} * {c}, {a} * {d})",
        "answer_display": "x = {ans}",
        "params": {
            "a": {"type": "int", "min": 2, "max": 9},
            "b": {"type": "int", "min": 2, "max": 12},
            "c": {"type": "int", "min": 2, "max": 12},
            "d": {"type": "int", "min": 1, "max": 9},
        },
        "solution": "根据比例的基本性质，内项之积等于外项之积："
                    "{d} × {a}x = {b} × {c}，即 {ad}x = {bc}，"
                    "两边同除以 {ad}，得 x = {ans}。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "na_pattern_01",
        "knowledge_id": "number_pattern",
        "slot": "fill",
        "stem": "观察下面的数列：{n1}，{n2}，{n3}，{n4}，…… 第 {k} 个数是（　　）。",
        "answer_expr": "{n1} + ({k} - 1) * {d}",
        "answer_display": "{ans}",
        "params": {
            "n1": {"type": "int", "min": 2, "max": 12},
            "d": {"type": "int", "min": 3, "max": 9},
            "k": {"type": "int", "min": 8, "max": 20},
        },
        "solution": "这是一个等差数列，首项是 {n1}，公差是 {d}。"
                    "第 k 项 = 首项 + （k − 1）× 公差，"
                    "所以第 {k} 项 = {n1} + （{k} − 1）× {d} = {ans}。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "na_estimation_01",
        "knowledge_id": "estimation",
        "slot": "choice",
        "stem": "下面哪个数最接近 {m} × {n} 的准确结果，而不用算出精确值也能判断？（　　）",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['{w1}', '{w2}', '{w3}', '{w4}']",
        "params": {
            "m": {"type": "choice", "from": [198, 201, 299, 402]},
            "n": {"type": "choice", "from": [21, 31, 41, 51]},
        },
        "solution": "估算时把接近整十整百的数先近似：{m} 看作 {ma}，{n} 看作 {na}，"
                    "{ma} × {na} = {est}，与它最接近的选项是 {correct}。"
                    "估算的关键是判断结果的数量级，而不是精确计算。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "na_unit_conv_01",
        "knowledge_id": "unit_conversion",
        "slot": "fill",
        "stem": "{v1} 立方米 = （　　）立方分米 = （　　）升；{t1} 小时 = （　　）分。",
        "answer_expr": "{v1} * 1000",
        "answer_display": "{ans}；{ans}；{mins}",
        "params": {
            "v1": {"type": "choice", "from": [1.5, 2.4, 3.6, 0.75, 1.25]},
            "t1": {"type": "choice", "from": [1.5, 2.25, 0.75, 2.5, 1.2]},
        },
        "solution": "体积单位进率：1 立方米 = 1000 立方分米，1 立方分米 = 1 升，"
                    "这两个进率连起来用；时间单位进率：1 小时 = 60 分。"
                    "{v1} × 1000 = {ans}；{t1} × 60 = {mins}。",
        "difficulty": 1,
        "unit": None,
    },
    {
        "id": "na_convert_02",
        "knowledge_id": "decimal_fraction_pct_convert",
        "slot": "judge",
        "stem": "因为 [[1/2]] = 50%，所以 [[1/2]] 米 = 50% 米。（　　）",
        "answer_expr": "0",
        "answer_display": "×",
        "params": None,
        "solution": "百分数只表示两个数的倍比关系，不能带单位名称。"
                    "1/2 米是一个具体的长度（0.5 米），而 50% 米这种写法本身就是错的，"
                    "所以打 ×。这也是考试常考的"量"与"率"的区别。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "na_column_01",
        "knowledge_id": "column_calc",
        "slot": "calc",
        "stem": "列方程计算：一个数的 {a} 倍比它的 {b} 倍多 {c}，求这个数。",
        "answer_expr": "Fraction({c}, {a} - {b})",
        "answer_display": "{ans}",
        "params": {
            "a": {"type": "int", "min": 5, "max": 9},
            "b": {"type": "int", "min": 2, "max": 4},
            "c": {"type": "int", "min": 6, "max": 30},
        },
        "solution": "设这个数为 x。根据"一个数的 {a} 倍比它的 {b} 倍多 {c}"列方程："
                    "{a}x − {b}x = {c}，合并同类项得 {ab}x = {c}，"
                    "两边同除以 {ab}，得 x = {ans}。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "na_simple_02",
        "knowledge_id": "simple_calc",
        "slot": "choice",
        "stem": "计算 [[{n}/{d}]] × {k} + [[{n}/{d}]] × {m}，简便算法是用（　　）。",
        "answer_expr": "Fraction({n}, {d}) * ({k} + {m})",
        "answer_display": "{ans}",
        "choices_expr": "['乘法分配律', '乘法交换律', '乘法结合律', '加法结合律']",
        "params": {
            "n": {"type": "int", "min": 1, "max": 8},
            "d": {"type": "int", "min": 3, "max": 9},
            "k": {"type": "int", "min": 3, "max": 9},
            "m": {"type": "int", "min": 3, "max": 9},
        },
        "solution": "两项都含有相同因数 {n}/{d}，把它提取出来，"
                    "剩下 ({k} + {m}) 相加，这就是乘法分配律的逆用。"
                    "结果 = {n}/{d} × {km} = {ans}。",
        "difficulty": 2,
        "unit": None,
    },
]
