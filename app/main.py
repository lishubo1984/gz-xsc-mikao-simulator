"""FastAPI 应用入口。

分层：app/web（页面） → app/api（JSON 接口） → app/services（业务逻辑）。
页面与 PDF 共用同一个 paper_items 数据源，保证屏幕上看到的和打印出来的一致。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.db.session import engine, init_db
from app.services.knowledge import sync_graph


def create_app() -> FastAPI:
    init_db()
    # 知识图谱必须先入库：wrong_book 的外键指向 knowledge_nodes，
    # 少了这一步交卷写错题本会直接被外键拦下。
    sync_graph(engine)

    app = FastAPI(title=settings.app_name, debug=settings.debug)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    from app.api.attempts import router as attempts_router
    from app.api.papers import router as papers_router
    from app.web.routes import router as web_router

    app.include_router(web_router)
    app.include_router(papers_router, prefix="/api")
    app.include_router(attempts_router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True, "app": settings.app_name}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
