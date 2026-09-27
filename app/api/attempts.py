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
    # 自动化测试里不想每次都往云端写数据，可置 true 跳过
    skip_sync: bool = False


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

    # 交卷后把成绩推到腾讯文档台账。
    # 刻意不做成"推送失败就交卷失败"：孩子做完了卷子，分数必须保住，
    # 云端只是台账。同步失败只记在返回值里，由前端提示，可稍后手动补推。
    sync = {"ok": False, "skipped": True}
    if not body.skip_sync:
        try:
            from app.services import sync_ledger
            sync = sync_ledger.push_attempt(engine, attempt_id)
        except Exception as exc:  # noqa: BLE001 - 同步是旁路，不能拖垮交卷
            sync = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    return {"attempt_id": attempt_id, "report": report, "tcloud": sync}


@router.post("/attempts/{attempt_id}/sync-ledger")
def sync_ledger_now(attempt_id: str) -> dict:
    """手动补推一次台账（自动同步失败后用）。"""
    if not repo.get_attempt(engine, attempt_id):
        raise HTTPException(status_code=404, detail="作答记录不存在")
    from app.services import sync_ledger
    return sync_ledger.push_attempt(engine, attempt_id)


@router.get("/ledger")
def ledger_status() -> dict:
    """查看云端台账现状（行数 + 前几行），用于确认同步真的落地了。"""
    from app.services import sync_ledger
    try:
        return {"ok": True, **sync_ledger.ledger_summary()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


@router.get("/wrong-stats")
def wrong_stats(limit: int = 12) -> dict:
    return {"items": repo.wrong_stats(engine, limit)}
