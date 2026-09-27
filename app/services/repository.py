"""数据访问层：把所有 SQL 收口在这里，上层不直接写语句。"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.services import grader
from app.services.knowledge import diagnose, load_graph


def create_paper_row(engine: Engine, result: dict) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO papers (id, title, seed, total_score, duration_min,
                     status, check_report) VALUES (:id, :title, :seed, :ts, :dm, :st, :cr)"""),
            {"id": result["paper_id"], "title": result["title"], "seed": result["seed"],
             "ts": result["total_score"], "dm": result["duration_min"], "st": "checked",
             "cr": json.dumps(result["check_report"], ensure_ascii=False)},
        )
        for it in result["items"]:
            conn.execute(
                text("""INSERT INTO paper_items (paper_id, seq, slot, section_title,
                         knowledge_id, question_id, score, rendered_stem, rendered_solution,
                         figure_svg, choices, answer, answer_unit)
                     VALUES (:pid, :seq, :slot, :st, :kid, :qid, :sc, :stem, :sol,
                             :svg, :ch, :ans, :unit)"""),
                {"pid": result["paper_id"], "seq": it["seq"], "slot": it["slot"],
                 "st": it["section_title"], "kid": it["knowledge_id"],
                 "qid": it["question_id"], "sc": it["score"], "stem": it["stem"],
                 "sol": it["solution"], "svg": it["figure_svg"],
                 "ch": json.dumps(it["choices"], ensure_ascii=False) if it["choices"] else None,
                 "ans": it["answer"], "unit": it.get("unit")},
            )


def get_paper(engine: Engine, paper_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, title, seed, total_score, duration_min, status, created_at"
                 " FROM papers WHERE id = :id"),
            {"id": paper_id},
        ).mappings().first()
        if not row:
            return None
        return dict(row)


def list_papers(engine: Engine, limit: int = 20) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT p.id, p.title, p.created_at,
                           COUNT(a.id) AS attempt_cnt,
                           MAX(a.total_score) AS best_score
                    FROM papers p LEFT JOIN attempts a ON a.paper_id = p.id
                    GROUP BY p.id ORDER BY p.created_at DESC LIMIT :lim"""),
            {"lim": limit},
        ).mappings().all()
        return [dict(r) for r in rows]


def get_items(engine: Engine, paper_id: str) -> list[dict]:
    """取一道卷的全部题目。module 由知识点表补出（paper_items 不冗余存模块）。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT pi.id, pi.seq, pi.slot, pi.section_title, pi.section_instruction,
                           pi.knowledge_id, pi.question_id, pi.score, pi.rendered_stem,
                           pi.rendered_solution, pi.figure_svg, pi.choices, pi.answer,
                           pi.answer_unit, kn.name AS knowledge_name, kn.module AS module
                    FROM paper_items pi
                    LEFT JOIN knowledge_nodes kn ON kn.id = pi.knowledge_id
                    WHERE pi.paper_id = :pid ORDER BY pi.seq"""),
            {"pid": paper_id},
        ).mappings().all()
    items = []
    for r in rows:
        d = dict(r)
        if d.get("choices"):
            try:
                d["choices"] = json.loads(d["choices"])
            except json.JSONDecodeError:
                d["choices"] = []
        items.append(d)
    return items


# --------------------------------------------------------------------------
# 作答
# --------------------------------------------------------------------------
def start_attempt(engine: Engine, paper_id: str, student: str = "练习者") -> str:
    aid = uuid.uuid4().hex[:12]
    with engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO attempts (id, paper_id, student_name, started_at)
                     VALUES (:id, :pid, :name, datetime('now','localtime'))"""),
            {"id": aid, "pid": paper_id, "name": student or "练习者"},
        )
    return aid


def save_answers(engine: Engine, attempt_id: str, answers: dict[str, str],
                 scratch: dict[str, str] | None = None) -> None:
    """保存草稿。重复调用以最新一次为准（幂等，支持前端定时自动保存）。

    answers 存作答结果，scratch 存解题过程 —— 后者不参与判分，
    但孩子在网上做应用题必须有个地方写思路，否则这个功能就是残缺的。
    """
    scratch = scratch or {}
    with engine.begin() as conn:
        for item_id, val in answers.items():
            conn.execute(
                text("""INSERT INTO attempt_answers (attempt_id, item_id, student_answer,
                         scratch, is_correct, got_score) VALUES (:aid, :iid, :val, :sc, 0, 0)
                     ON CONFLICT(attempt_id, item_id) DO UPDATE SET
                         student_answer = excluded.student_answer,
                         scratch = excluded.scratch"""),
                {"aid": attempt_id, "iid": int(item_id), "val": val,
                 "sc": scratch.get(str(item_id), "")},
            )


def get_scratch(engine: Engine, attempt_id: str) -> dict[int, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT item_id, scratch FROM attempt_answers WHERE attempt_id = :aid"),
            {"aid": attempt_id},
        ).mappings().all()
        return {int(r["item_id"]): (r["scratch"] or "") for r in rows}


def get_answers(engine: Engine, attempt_id: str) -> dict[int, str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT item_id, student_answer FROM attempt_answers WHERE attempt_id = :aid"),
            {"aid": attempt_id},
        ).mappings().all()
        return {int(r["item_id"]): (r["student_answer"] or "") for r in rows}


def get_attempt(engine: Engine, attempt_id: str) -> dict | None:
    with engine.connect() as conn:
        row = conn.execute(
            text("""SELECT id, paper_id, student_name, started_at, submitted_at,
                           remaining_sec, total_score, report
                    FROM attempts WHERE id = :id"""),
            {"id": attempt_id},
        ).mappings().first()
        return dict(row) if row else None


def submit_attempt(engine: Engine, attempt_id: str, answers: dict[str, str],
                   scratch: dict[str, str] | None, remaining_sec: int | None) -> dict:
    """交卷：判分 -> 写 attempt_answers -> 写 wrong_book -> 生成报告。"""
    aid = attempt_id
    attempt = get_attempt(engine, aid)
    if attempt is None:
        raise ValueError(f"作答记录不存在：{aid}")
    paper_id = attempt["paper_id"]
    items = get_items(engine, paper_id)
    ans_map = {int(k): v for k, v in answers.items()}
    result = grader.grade_items(items, ans_map)

    save_answers(engine, aid, {str(k): v for k, v in ans_map.items()}, scratch)

    with engine.begin() as conn:
        conn.execute(
            text("""UPDATE attempts SET submitted_at = datetime('now','localtime'),
                     remaining_sec = :rs, total_score = :ts, objective_score = :ts
                     WHERE id = :id"""),
            {"rs": remaining_sec, "ts": result["got"], "id": aid},
        )
        for r in result["per_item"]:
            conn.execute(
                text("""UPDATE attempt_answers SET is_correct = :ok, got_score = :gs
                         WHERE attempt_id = :aid AND item_id = :iid"""),
                {"ok": r["is_correct"], "gs": r["got"], "aid": aid, "iid": r["item_id"]},
            )
        # 错题本：每一道错题一条记录，按知识点聚合后可反查"这块内容错了几次"
        for it, r in zip(items, result["per_item"]):
            if r["is_correct"]:
                continue
            conn.execute(
                text("""INSERT INTO wrong_book (knowledge_id, attempt_id, item_id, paper_id)
                         VALUES (:kid, :aid, :iid, :pid)"""),
                {"kid": it["knowledge_id"], "aid": aid, "iid": r["item_id"], "pid": paper_id},
            )

    graph = load_graph()
    nodes = {n["id"]: n for n in graph["nodes"]}
    weak = diagnose(sorted(result["wrong_knowledge"].keys()), graph)

    report = {
        "total": result["total"],
        "got": result["got"],
        "unanswered": result["unanswered"],
        "module_stat": result["module_stat"],
        "slot_stat": result["slot_stat"],
        "weak_points": weak,
        "wrong_details": [
            {
                "seq": r["seq"],
                "slot": r["slot"],
                "knowledge_name": nodes.get(r["knowledge_id"], {}).get("name", r["knowledge_id"]),
                "knowledge_id": r["knowledge_id"],
                "score": r["score"],
                "student_answer": r["student_answer"],
                "answered": not r["unanswered"],
            }
            for r in result["per_item"] if not r["is_correct"]
        ],
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE attempts SET report = :rp WHERE id = :id"),
            {"rp": json.dumps(report, ensure_ascii=False), "id": aid},
        )
    return report


def wrong_stats(engine: Engine, limit: int = 12) -> list[dict]:
    """历史错题 Top N（按知识点聚合），用于首页展示薄弱点。"""
    with engine.connect() as conn:
        rows = conn.execute(
            text("""SELECT knowledge_id, COUNT(*) AS cnt, MAX(last_wrong_at) AS last_at
                    FROM wrong_book GROUP BY knowledge_id
                    ORDER BY cnt DESC, last_at DESC LIMIT :lim"""),
            {"lim": limit},
        ).mappings().all()
        return [dict(r) for r in rows]
