"""试卷相关接口：生成、查询、删除前的校验报告。"""
from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.session import engine
from app.services import repository as repo
from app.services.generator import generate_paper

router = APIRouter(tags=["papers"])


class GenerateIn(BaseModel):
    title: str | None = None
    seed: int | None = None
    student: str = "练习者"


@router.post("/papers")
def create_paper(body: GenerateIn) -> dict:
    """出一份卷。体检不通过会抛异常 —— 宁可报错，也不交付有问题的卷。"""
    t0 = time.time()
    try:
        paper = generate_paper(engine=engine, seed=body.seed, title=body.title)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    attempt_id = repo.start_attempt(engine, paper["paper_id"], body.student)
    return {
        "paper_id": paper["paper_id"],
        "attempt_id": attempt_id,
        "title": paper["title"],
        "total_score": paper["total_score"],
        "duration_min": paper["duration_min"],
        "question_count": len(paper["items"]),
        "check_passed": paper["check_report"]["passed"],
        "elapsed_ms": int((time.time() - t0) * 1000),
    }


@router.get("/papers")
def list_papers(limit: int = 20) -> dict:
    return {"items": repo.list_papers(engine, limit)}


@router.get("/papers/{paper_id}")
def paper_detail(paper_id: str) -> dict:
    p = repo.get_paper(engine, paper_id)
    if not p:
        raise HTTPException(status_code=404, detail="试卷不存在")
    p["items"] = repo.get_items(engine, paper_id)
    return p


@router.get("/papers/{paper_id}/answers")
def paper_answers(paper_id: str) -> dict:
    """标准答案与解题思路 —— 用于答案页与家长核对。"""
    items = repo.get_items(engine, paper_id)
    if not items:
        raise HTTPException(status_code=404, detail="试卷不存在或没有题目")
    return {
        "paper_id": paper_id,
        "items": [
            {"seq": it["seq"], "slot": it["slot"], "answer": it["answer"],
             "solution": it["rendered_solution"], "score": it["score"],
             "knowledge_id": it["knowledge_id"],
             "knowledge_name": it.get("knowledge_name")}
            for it in items
        ],
    }
