"""知识图谱入库与知识链回溯。

knowledge_nodes 必须先入库，否则 wrong_book 的外键会直接把交卷写失败 ——
这是启动顺序上的硬约束，放在 sync_graph() 里由应用启动时调用。
"""
from __future__ import annotations

import ast
import json
from fractions import Fraction

import yaml
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import settings


def as_list(value: object) -> list:
    """图谱里 prereq/slots/points 在不同编辑阶段可能是真列表、也可能是列表字面量字符串。

    统一收敛到 list，避免下游到处写 isinstance 判断。
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    txt = str(value).strip()
    if not txt or txt in ("[]", "null", "None"):
        return []
    try:
        parsed = ast.literal_eval(txt)
        if isinstance(parsed, (list, tuple)):
            return list(parsed)
    except (ValueError, SyntaxError):
        pass
    try:
        parsed = json.loads(txt)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    return [txt]


def load_graph(path=None) -> dict:
    path = path or settings.graph_yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def sync_graph(engine: Engine, graph: dict | None = None) -> int:
    """把 YAML 里的知识点与前置依赖写入 SQLite。幂等，可反复调用。"""
    graph = graph or load_graph()
    nodes = graph["nodes"]
    with engine.begin() as conn:
        for n in nodes:
            conn.execute(
                text("""INSERT INTO knowledge_nodes
                        (id, name, module, difficulty, frequency, points, slots, updated_at)
                        VALUES (:id, :name, :module, :diff, :freq, :points, :slots,
                                datetime('now', 'localtime'))
                        ON CONFLICT(id) DO UPDATE SET
                            name = excluded.name,
                            module = excluded.module,
                            difficulty = excluded.difficulty,
                            frequency = excluded.frequency,
                            points = excluded.points,
                            slots = excluded.slots,
                            updated_at = datetime('now', 'localtime')"""),
                {
                    "id": n["id"],
                    "name": n["name"],
                    "module": n["module"],
                    "diff": int(n.get("difficulty", 2)),
                    "freq": n.get("frequency", "mid"),
                    "points": json.dumps(as_list(n.get("points")), ensure_ascii=False),
                    "slots": json.dumps(as_list(n.get("slots")), ensure_ascii=False),
                },
            )
            conn.execute(
                text("DELETE FROM knowledge_prereq WHERE node_id = :id"),
                {"id": n["id"]},
            )
            for p in as_list(n.get("prereq")):
                # 前置节点可能尚未写入（依赖顺序不定），用 INSERT OR IGNORE 兜底由外键校验兜住
                conn.execute(
                    text("""INSERT OR IGNORE INTO knowledge_nodes
                            (id, name, module, difficulty, frequency, points, slots)
                            VALUES (:id, :id, 'misc_comprehensive', 2, 'low', '[]', '[]')"""),
                    {"id": p},
                )
                conn.execute(
                    text("INSERT OR IGNORE INTO knowledge_prereq (node_id, prereq_id)"
                         " VALUES (:n, :p)"),
                    {"n": n["id"], "p": p},
                )
    return len(nodes)


def prereq_map(graph: dict | None = None) -> dict[str, list[str]]:
    graph = graph or load_graph()
    return {n["id"]: as_list(n.get("prereq")) for n in graph["nodes"]}


def node_index(graph: dict | None = None) -> dict[str, dict]:
    graph = graph or load_graph()
    return {n["id"]: n for n in graph["nodes"]}


# --------------------------------------------------------------------------
# 薄弱点回溯：错题 -> 断在哪一环
# --------------------------------------------------------------------------
def diagnose(weak_ids: list[str], graph: dict | None = None,
             top: int = 6) -> list[dict]:
    """对错题知识点，沿前置依赖往上找，定位最上游的薄弱环节。

    为什么要有这一步（产品价值）：
      学生错一道"盐水的浓度"题，根子可能在"单位一识别"甚至"分数意义"。
      只报错题知识点等于告诉家长"他浓度题不会"，而真正要补的是链条上游。
    """
    graph = graph or load_graph()
    nodes = node_index(graph)
    pre = prereq_map(graph)

    roots: dict[str, list[str]] = {}
    for kid in weak_ids:
        path = _walk_prereq(kid, pre)
        roots[kid] = path

    # 统计每个疑似根因被多少条错题链命中
    score: dict[str, int] = {}
    evidence: dict[str, list[str]] = {}
    for kid, path in roots.items():
        for step in path:
            score[step] = score.get(step, 0) + 1
            evidence.setdefault(step, [])
            if kid not in evidence[step]:
                evidence[step].append(kid)

    out = []
    for nid, cnt in sorted(score.items(), key=lambda x: (-x[1], x[0]))[:top]:
        node = nodes.get(nid, {})
        out.append({
            "id": nid,
            "name": node.get("name", nid),
            "module": node.get("module", "misc_comprehensive"),
            "hits": cnt,
            "caused_by": [nodes.get(k, {}).get("name", k) for k in evidence.get(nid, [])],
        })
    return out


def _walk_prereq(node_id: str, pre: dict[str, list[str]],
                 depth: int = 4) -> list[str]:
    path: list[str] = []
    seen: set[str] = set()

    def go(cur: str, d: int) -> None:
        if d <= 0 or cur in seen:
            return
        seen.add(cur)
        path.append(cur)
        for p in pre.get(cur, []):
            go(p, d - 1)

    go(node_id, depth)
    return path


def chain_of(graph: dict, node_id: str) -> dict | None:
    """返回该知识点所属的知识链（用于报告里给出整段复习路径）。"""
    for ch in graph.get("chains", []):
        if node_id in ch.get("path", []):
            return ch
    return None


def to_fraction(text: str) -> Fraction | None:
    """把 "3/4" / "0.75" / "75%" 统一转成分数以便数值比较。"""
    try:
        t = str(text).strip()
        if not t:
            return None
        if "/" in t:
            num, den = t.split("/", 1)
            return Fraction(float(num.strip()), float(den.strip()))
        return Fraction(float(t))
    except (ValueError, ZeroDivisionError):
        return None
