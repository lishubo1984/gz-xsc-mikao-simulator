"""作答接口：自动保存草稿、交卷判分。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.session import engine
from app.services import repository as repo

router = APIRouter(tags=["attempts"])


class SaveIn(BaseModel):
    answers: dict[str, str] = {}
    scratch: dict[str, str] = {}


class SubmitIn(BaseModel):
    answers: dict[str, str] = {}
    scratch: dict[str, str] = {}
    remaining_sec: int | None = None


@router.get("/attempts/{attempt_id}")
def attempt_detail(attempt_id: str) -> dict:
    a = repo.get_attempt(engine, attempt_id)
    if not a:
        raise HTTPException(status_code=404, detail="作答记录不存在")
    paper = repo.get_paper(engine, a["paper_id"])
    a["answers"] = repo.get_answers(engine, attempt_id)
    a["scratch"] = repo.get_scratch(engine, attempt_id)
    a["paper"] = paper
    return a


@router.post("/attempts/{attempt_id}/save")
def save_draft(attempt_id: str, body: SaveIn) -> dict:
    """草稿保存。前端每 15 秒或每次作答变化时调用，防止刷新丢答案。"""
    if not repo.get_attempt(engine, attempt_id):
        raise HTTPException(status_code=404, detail="作答记录不存在")
    repo.save_answers(engine, attempt_id, body.answers, body.scratch)
    return {"ok": True, "saved": len(body.answers)}


@router.post("/attempts/{attempt_id}/submit")
def submit(attempt_id: str, body: SubmitIn) -> dict:
    try:
        report = repo.submit_attempt(engine, attempt_id, body.answers,
                                     body.scratch, body.remaining_sec)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"attempt_id": attempt_id, "report": report}


@router.get("/wrong-stats")
def wrong_stats(limit: int = 12) -> dict:
    return {"items": repo.wrong_stats(engine, limit)}
