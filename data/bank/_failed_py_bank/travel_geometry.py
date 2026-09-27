# -*- coding: utf-8 -*-
"""题库 3/4：行程问题（目标 12 分）+ 空间与图形（目标 10 分）。

两个模块合并在一个文件里，因为几何类的几道题会用到 SV G 图形；
约定：SVG 的 viewBox 由模板自己声明，绘图元素必须留出 >= 8 单位的文字边距，
否则出卷体检器会判定"图形标签越界"并强制换题（首次验证时真的踩到了这个坑）。
"""
from __future__ import annotations

TRAVEL: list[dict] = [
    {
        "id": "tv_basic_01",
        "knowledge_id": "travel_basic",
        "slot": "fill",
        "stem": "一辆汽车从甲地开往乙地，每小时行驶 {v} 千米，{h} 小时到达。"
                "甲、乙两地相距（　　）千米；返回时每小时多行驶 {dv} 千米，"
                "返回需要（　　）小时。",
        "answer_expr": "{v} * {h}",
        "answer_display": "{dist} 千米；{back} 小时",
        "params": {
            "v": {"type": "choice", "from": [40, 45, 50, 60, 75, 80]},
            "h": {"type": "choice", "from": [2, 3, 4, 5]},
            "dv": {"type": "choice", "from": [10, 15, 20, 25]},
        },
        "solution": "先用“速度 × 时间 = 路程”求全程：{v} × {h} = {dist}（千米）。"
                    "返回时速度变为 {v} + {dv} = {vb}（千米/时），"
                    "时间 = 路程 ÷ 速度 = {dist} ÷ {vb} = {back}（小时）。"
                    "注意往返的路程相同，这是解题的连接点。",
        "difficulty": 2,
        "unit": None,
    },
    {
        "id": "tv_meet_01",
        "knowledge_id": "travel_meet_chase",
        "slot": "solve",
        "stem": "甲、乙两地相距 {dist} 千米。客车和货车同时从两地相向开出，"
                "客车每小时行 {v1} 千米，货车每小时行 {v2} 千米。"
                "经过几小时两车相遇？",
        "answer_expr": "round({dist} / ({v1} + {v2}), 2)",
        "answer_display": "{ans} 小时",
        "params": {
            "dist": {"type": "choice", "from": [270, 315, 360, 420, 450, 540, 630]},
            "v1": {"type": "choice", "from": [60, 65, 70, 75, 80, 90]},
            "v2": {"type": "choice", "from": [45, 50, 55, 60, 70]},
        },
        "solution": "相遇问题的核心是“速度和”：两车同时相向而行，"
                    "每小时一共前进 {v1} + {v2} = {vs}（千米）。"
                    "相遇时间 = 总路程 ÷ 速度和 = {dist} ÷ {vs} = {ans}（小时）。"
                    "与"追及问题用速度差"形成对照，二者不要混。",
        "difficulty": 4,
        "unit": "小时",
    },
    {
        "id": "tv_water_01",
        "knowledge_id": "travel_water_air",
        "slot": "choice",
        "stem": "一艘轮船在静水中的速度是每小时 {s} 千米，水流速度是每小时 {w} 千米。"
                "这艘轮船顺水航行 {h} 小时，可以航行（　　）千米。",
        "answer_expr": "({s} + {w}) * {h}",
        "answer_display": "{ans}",
        "choices_expr": "['{ans}', '{wrong1}', '{wrong2}', '{wrong3}']",
        "params": {
            "s": {"type": "choice", "from": [18, 20, 24, 25, 30]},
            "w": {"type": "choice", "from": [2, 3, 4, 5]},
            "h": {"type": "choice", "from": [3, 4, 5, 6]},
        },
        "solution": "顺水航行时，水的流动对船有帮助，"
                    "顺水速度 = 船在静水中的速度 + 水流速度 = {s} + {w} = {vs}（千米/时）。"
                    "再乘时间：{vs} × {h} = {ans}（千米）。"
                    "对照记忆：逆水速度 = 船速 − 水速，切勿用混。",
        "difficulty": 3,
        "unit": "千米",
    },
    {
        "id": "tv_circular_01",
        "knowledge_id": "travel_circular",
        "slot": "extra",
        "stem": "一个环形跑道一周长 {lap} 米。甲、乙两人同时同地出发，"
                "同向跑步，甲每秒跑 {v1} 米，乙每秒跑 {v2} 米。"
                "经过多少秒甲第一次追上乙？此时甲一共跑了多少米？",
        "answer_expr": "round({lap} / ({v1} - {v2}), 2)",
        "answer_display": "{ans} 秒；{dist} 米",
        "params": {
            "lap": {"type": "choice", "from": [400, 300, 600, 500]},
            "v1": {"type": "choice", "from": [6, 7, 8, 9]},
            "v2": {"type": "choice", "from": [4, 5, 6]},
            "v1_offset": {"type": "choice", "from": [2, 3, 4]},
        },
        "solution": "环形跑道上同向而行，甲要追上乙，必须比乙多跑整整一圈。"
                    "两人的速度差 = {v1} − {v2} = {vd}（米/秒），"
                    "追上的时间 = 一圈的长度 ÷ 速度差 = {lap} ÷ {vd} = {ans}（秒）。"
                    "这段时间甲跑的路程 = {v1} × {ans} = {dist}（米）。"
                    "易错点：环形跑道的追及要用周长而不是直线距离。",
        "difficulty": 5,
        "unit": None,
    },
    {
        "id": "tv_ratio_01",
        "knowledge_id": "travel_with_ratio",
        "slot": "choice",
        "stem": "甲、乙两车行驶同样的路程，甲车用的时间是乙车的 [[{a}/{b}]]。"
                "甲、乙两车的速度比是（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['{ans}', '{w1}', '{w2}', '{w3}']",
        "params": {
            "a": {"type": "int", "min": 2, "max": 5},
            "b": {"type": "int", "min": 6, "max": 9},
        },
        "solution": "路程一定时，速度与时间成反比。"
                    "甲、乙时间比是 {a} : {b}，"
                    "那么甲、乙速度比就是它的反比，即 {b} : {a}。"
                    "记住这条反比关系，很多行程题可以一步到位。",
        "difficulty": 4,
        "unit": None,
    },
    {
        "id": "tv_meet_02",
        "knowledge_id": "travel_meet_chase",
        "slot": "extra",
        "stem": "甲、乙两人分别从 A、B 两地同时出发相向而行，"
                "第一次相遇时距 A 地 {x} 千米。相遇后两人继续前进，"
                "到达对方出发点后立即返回，第二次相遇时距 B 地 {y} 千米。"
                "A、B 两地相距多少千米？",
        "answer_expr": "3 * {x} - {y}",
        "answer_display": "{ans} 千米",
        "params": {
            "x": {"type": "choice", "from": [40, 45, 50, 60, 70]},
            "y": {"type": "choice", "from": [20, 25, 30, 35, 40]},
        },
        "solution": "这是经典的“两次相遇”问题，关键结论："
                    "从出发到第二次相遇，两人合起来走的路程是全程的 3 倍。"
                    "第一次相遇时甲走了 {x} 千米；"
                    "到第二次相遇时甲一共走了 3 × {x} = {x3}（千米）。"
                    "而甲到达 B 地后又返回走了 {y} 千米，"
                    "所以全程 = 3 × {x} − {y} = {ans}（千米）。",
        "difficulty": 5,
        "unit": "千米",
    },
]


GEOMETRY: list[dict] = [
    {
        "id": "gm_circle_01",
        "knowledge_id": "circle_sector",
        "slot": "geometry",
        "stem": "一个圆柱形水桶，从里面量得底面半径是 {r} 厘米，高是 {h} 厘米。"
                "（π 取 3.14）这个水桶最多能装水多少毫升？",
        "answer_expr": "round(3.14 * {r} * {r} * {h}, 2)",
        "answer_display": "{ans} 立方厘米（毫升）",
        "params": {
            "r": {"type": "choice", "from": [3, 4, 5, 6, 8, 10]},
            "h": {"type": "choice", "from": [10, 12, 15, 20, 25]},
        },
        "solution": "求能装多少水就是求水桶的容积（从里面量）。"
                    "圆柱的体积 = 底面积 × 高 = πr² × h，"
                    "列式：3.14 × {r}² × {h} = 3.14 × {r2} × {h} = {ans}（立方厘米）。"
                    "因为 1 立方厘米 = 1 毫升，所以能装 {ans} 毫升水。",
        "difficulty": 3,
        "unit": "毫升",
    },
    {
        "id": "gm_cone_01",
        "knowledge_id": "cylinder_cone",
        "slot": "geometry",
        "stem": "一个圆锥形沙堆，底面积是 {s} 平方米，高是 {h} 米。"
                "如果把这个沙堆铺在一条宽 {w} 米的路面上，能铺多少米长？"
                "（得数保留整数）",
        "answer_expr": "round({s} * {h} / 3 / {w}, 0)",
        "answer_display": "{ans} 米",
        "params": {
            "s": {"type": "choice", "from": [12, 15, 18, 24, 30, 36]},
            "h": {"type": "choice", "from": [1.5, 2, 2.4, 3]},
            "w": {"type": "choice", "from": [2, 3, 4, 5]},
        },
        "solution": "思路是“体积不变”：沙堆的体积铺到路面上后形是一个薄长方体，体积相等。"
                    "① 圆锥体积 = 底面积 × 高 × 1/3 = {s} × {h} × 1/3 = {vol}（立方米）；"
                    "② 铺成的长方体体积 = 宽 × 长 × 高，这里"高"就是铺设的厚度；"
                    "③ 长 = 体积 ÷ 宽 = {vol} ÷ {w} ≈ {ans}（米）。"
                    "易错点：圆锥体积千万别忘了乘 1/3。",
        "difficulty": 4,
        "unit": "米",
    },
    {
        "id": "gm_scale_01",
        "knowledge_id": "scale_map",
        "slot": "fill",
        "stem": "在比例尺是 1 : {den} 的地图上，量得 A、B 两地的距离是 {d} 厘米。"
                "A、B 两地的实际距离是（　　）千米。",
        "answer_expr": "round({d} * {den} / 100000, 2)",
        "answer_display": "{ans} 千米",
        "params": {
            "den": {"type": "choice", "from": [500000, 1000000, 2000000, 4000000]},
            "d": {"type": "choice", "from": [3, 4, 5, 6, 7.5]},
        },
        "solution": "比例尺 1 : {den} 表示图上 1 厘米相当于实际 {den} 厘米。"
                    "实际距离 = 图上距离 × 比例尺的分母 = {d} × {den} = {cm}（厘米），"
                    "再换算成千米（1 千米 = 100000 厘米）：{cm} ÷ 100000 = {ans}（千米）。"
                    "两个易错点：一是别漏了单位换算；二是别把比例尺用反（乘还是除）。",
        "difficulty": 2,
        "unit": "千米",
    },
    {
        "id": "gm_solid_01",
        "knowledge_id": "solid_volume",
        "slot": "fill",
        "stem": "一个正方体的棱长总和是 {sumlen} 厘米，它的表面积是（　　）平方厘米，"
                "体积是（　　）立方厘米。",
        "answer_expr": "({sumlen} // 12) ** 3",
        "answer_display": "{area}；{ans}",
        "params": {
            "sumlen": {"type": "choice", "from": [36, 48, 60, 72, 84, 96]},
        },
        "solution": "正方体有 12 条棱且长度相等，所以棱长 = 棱长总和 ÷ 12 = {sumlen} ÷ 12 = {a}（厘米）。"
                    "表面积 = 棱长 × 棱长 × 6 = {a} × {a} × 6 = {area}（平方厘米）；"
                    "体积 = 棱长³ = {a} × {a} × {a} = {ans}（立方厘米）。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "gm_composite_01",
        "knowledge_id": "composite_area",
        "slot": "geometry",
        "stem": "如下图，一个长方形（长 {l} 厘米，宽 {w} 厘米）内画了一个最大的圆。"
                "求圆外、长方形内阴影部分的面积。（π 取 3.14）",
        "figure_svg": (
            '<svg viewBox="0 0 260 150" width="260" xmlns="http://www.w3.org/2000/svg">'
            '<rect x="30" y="25" width="200" height="100" fill="#f0f0f0" stroke="#000" stroke-width="1"/>'
            '<circle cx="130" cy="75" r="50" fill="#ffffff" stroke="#c0392b" stroke-width="1.2"/>'
            '<text x="124" y="142" font-size="11" fill="#000">30cm</text>'
            '<text x="238" y="78" font-size="11" fill="#000">20cm</text>'
            "</svg>"
        ),
        "answer_expr": "round({l} * {w} - 3.14 * ({w} / 2) ** 2, 2)",
        "answer_display": "{ans} 平方厘米",
        "params": {
            "l": {"type": "choice", "from": [30, 40, 50, 60]},
            "w": {"type": "choice", "from": [20, 24, 30, 40]},
        },
        "solution": "长方形内画最大的圆，圆的直径等于长方形的宽 {w} 厘米，"
                    "所以半径 r = {w} ÷ 2 = {r}（厘米）。"
                    "阴影面积 = 长方形面积 − 圆的面积 = {l} × {w} − 3.14 × {r}² "
                    "= {rect} − {circ} = {ans}（平方厘米）。"
                    "这是"整体减部分"的经典思路。",
        "difficulty": 4,
        "unit": "平方厘米",
    },
    {
        "id": "gm_transform_01",
        "knowledge_id": "geometry_transform",
        "slot": "choice",
        "stem": "把一个图形先向右平移 {n} 格，再绕某点顺时针旋转 {deg}°，"
                "得到的图形与原图形相比（　　）。",
        "answer_expr": "1",
        "answer_display": "{correct}",
        "choices_expr": "['形状和大小都不变，位置改变', '形状不变，但大小改变', "
                        "'形状改变，大小不变', '形状和大小都改变']",
        "params": {
            "n": {"type": "int", "min": 2, "max": 6},
            "deg": {"type": "choice", "from": [90, 180, 270]},
        },
        "solution": "平移和旋转都属于“图形的运动”，它们只改变图形的位置和方向，"
                    "不改变图形的形状，也不改变图形的大小。"
                    "所以变换后得到的图形与原图形全等，选"形状和大小都不变，位置改变"。",
        "difficulty": 3,
        "unit": None,
    },
    {
        "id": "gm_plane_01",
        "knowledge_id": "plane_area",
        "slot": "solve",
        "stem": "一个梯形的面积是 {area} 平方厘米，上底是 {a} 厘米，下底是 {b} 厘米。"
                "这个梯形的高是多少厘米？",
        "answer_expr": "round(2 * {area} / ({a} + {b}), 2)",
        "answer_display": "{ans} 厘米",
        "params": {
            "a": {"type": "choice", "from": [4, 6, 8, 10]},
            "b": {"type": "choice", "from": [12, 14, 16, 18, 20]},
            "area": {"type": "choice", "from": [60, 80, 96, 120, 150, 180]},
        },
        "solution": "梯形面积 = （上底 + 下底） × 高 ÷ 2，把它反过来推："
                    "高 = 面积 × 2 ÷ （上底 + 下底） = {area} × 2 ÷ （{a} + {b}）"
                    " = {a2} ÷ {ab} = {ans}（厘米）。"
                    "易错点：反求高时千万别忘记先乘 2。",
        "difficulty": 3,
        "unit": "厘米",
    },
    {
        "id": "gm_count_01",
        "knowledge_id": "geometry_count",
        "slot": "extra",
        "stem": "在一个底边被平均分成 {n} 份的三角形中，连接顶点与底边上的所有分点，"
                "一共可以得到多少个三角形？",
        "answer_expr": "{n} * ({n} + 1) // 2",
        "answer_display": "{ans} 个",
        "params": {
            "n": {"type": "int", "min": 3, "max": 8},
        },
        "solution": "底边被分成 {n} 份，可以按“底边占几份”分类计数："
                    "占 1 份的三角形有 {n} 个，占 2 份的有 {n2} 个，……，占 {n} 份的有 1 个。"
                    "总数 = {n} + {n2} + …… + 1 = {n} × （{n} + 1） ÷ 2 = {ans}（个）。"
                    "几何计数要有序分类，避免重复或遗漏。",
        "difficulty": 4,
        "unit": "个",
    },
]
