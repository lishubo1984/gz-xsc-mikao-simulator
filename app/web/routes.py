"""页面路由。

模板里统一用 math('...') 过滤器渲染 [[a/b]]，
这样网页与 PDF 共用同一份渲染结果，不会出现"网页上对了、打印出来乱了"。
"""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import MODULE_LABELS, SLOT_LABELS, settings
from app.db.session import engine
from app.services import repository as repo
from app.services.knowledge import chain_of, load_graph, node_index
from app.services.math_render import render_math

router = APIRouter()

_tpl_dir = settings.base_dir / "app" / "templates"
templates = Jinja2Templates(directory=str(_tpl_dir))
# 题目文本里含 HTML 实体与自制标记，不做自动转义；内容全部由本项目生成，不含用户输入
templates.env.autoescape = False
templates.env.filters["math"] = render_math

_SECTION_ORDER = ["一、填空题", "二、选择题", "三、判断题", "四、计算题",
                  "五、图形与几何", "六、解决问题", "七、附加题"]


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    papers = repo.list_papers(engine, 12)
    weak = repo.wrong_stats(engine, 8)
    graph = load_graph()
    nodes = node_index(graph)
    weak_named = []
    for w in weak:
        n = nodes.get(w["knowledge_id"], {})
        weak_named.append({
            "knowledge_id": w["knowledge_id"],
            "name": n.get("name", w["knowledge_id"]),
            "module": n.get("module", ""),
            "count": w["cnt"],
            "last_at": w["last_at"],
        })
    chains = graph.get("chains", [])
    # 必须用关键字调用：Starlette 新版把 TemplateResponse 的签名改成了
    # (request=..., name=..., context=...)，旧的 positional 写法会把 context
    # 当成模板名传进去，报 TypeError: unhashable type: 'dict'。
    return templates.TemplateResponse(
        request=request, name="index.html",
        context={
            "app_name": settings.app_name,
            "papers": papers,
            "weak": weak_named,
            "chains": chains,
            "nodes": nodes,
            "module_labels": MODULE_LABELS,
        },
    )


@router.get("/paper/{attempt_id}", response_class=HTMLResponse)
def paper_page(request: Request, attempt_id: str):
    a = repo.get_attempt(engine, attempt_id)
    if not a:
        return HTMLResponse("作答记录不存在", status_code=404)
    paper = repo.get_paper(engine, a["paper_id"])
    items = repo.get_items(engine, a["paper_id"])
    answers = repo.get_answers(engine, attempt_id)
    scratch = repo.get_scratch(engine, attempt_id)

    # 剩余秒数必须在服务端算：前端计时一刷新就归零，等于把考试时间白送。
    remaining_sec = remaining_seconds(a["started_at"], paper["duration_min"])
    for it in items:
        # 多空题在答案框里提示用「；」分隔，与 answers 的存储格式保持一致
        it["multiblank"] = "；" in str(it["answer"] or "")

    # 段里的题目列表刻意不叫 items：Jinja2 的 {{ x.y }} 是先查属性再查键，
    # 而 dict 天生自带 .items() 方法，叫 {{ sec.items }} 会拿到那个方法本身，
    # 报 TypeError: 'builtin_function_or_method' object is not iterable。
    sections: dict[str, dict] = {}
    for it in items:
        sec = sections.setdefault(it["section_title"], {
            "title": it["section_title"],
            "instruction": it.get("section_instruction") or "",
            "qitems": [],
            "score": 0,
        })
        sec["qitems"].append(it)
        sec["score"] += int(it["score"])

    ordered = sorted(sections.values(),
                     key=lambda s: _SECTION_ORDER.index(s["title"])
                     if s["title"] in _SECTION_ORDER else 99)

    return templates.TemplateResponse(
        request=request, name="paper.html",
        context={
            "attempt_id": attempt_id,
            "paper": paper,
            "sections": ordered,
            "answers": answers,
            "answers_json": json.dumps({str(k): v for k, v in answers.items()}, ensure_ascii=False),
            "scratch": scratch,
            "scratch_json": json.dumps({str(k): v for k, v in scratch.items()}, ensure_ascii=False),
            "duration_min": paper["duration_min"] if paper else 100,
            "total_score": paper["total_score"] if paper else 100,
            "remaining_sec": remaining_sec,
            "submitted": bool(a.get("submitted_at")),
            "slot_labels": SLOT_LABELS,
            # 题数是派生量，在路由层算好再传：模板里写 sum(attribute='qitems') 是
            # 把列表相加（0 + list），必然 TypeError。
            "total_questions": len(items),
            "app_name": settings.app_name,
        },
    )


def remaining_seconds(started_at: str, duration_min: int) -> int:
    """从作答开始时间反推剩余秒数。已超时返回 0，由前端触发自动交卷。"""
    try:
        start = datetime.strptime(str(started_at), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return duration_min * 60
    elapsed = int((datetime.now() - start).total_seconds())
    return max(0, duration_min * 60 - elapsed)


def minutes_between(started_at: str, ended_at: str | None) -> int:
    try:
        s = datetime.strptime(str(started_at), "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(str(ended_at), "%Y-%m-%d %H:%M:%S") if ended_at else datetime.now()
        return max(0, round((e - s).total_seconds() / 60))
    except (ValueError, TypeError):
        return 0


@router.get("/report/{attempt_id}", response_class=HTMLResponse)
def report_page(request: Request, attempt_id: str):
    a = repo.get_attempt(engine, attempt_id)
    if not a:
        return HTMLResponse("作答记录不存在", status_code=404)
    if not a.get("report"):
        return templates.TemplateResponse(
            request=request, name="not_submitted.html",
            context={"app_name": settings.app_name, "attempt_id": attempt_id},
        )

    report = json.loads(a["report"])
    paper = repo.get_paper(engine, a["paper_id"])
    items = repo.get_items(engine, a["paper_id"])
    item_by_seq = {int(it["seq"]): it for it in items}
    for d in report.get("wrong_details", []):
        # 错题详情里补上题干与正确答案，方便家长直接讲，不用再来回翻
        it = item_by_seq.get(int(d["seq"]))
        if it:
            d["stem"] = it["rendered_stem"]
            d["correct"] = it["answer"]
            d["solution"] = it["rendered_solution"]
            d["module"] = it.get("module")

    graph = load_graph()
    for w in report.get("weak_points", []):
        ch = chain_of(graph, w["id"])
        w["chain"] = ch.get("name") if ch else None
        w["module_label"] = MODULE_LABELS.get(w.get("module", ""), "")

    for m in report.get("module_stat", []):
        m["label"] = MODULE_LABELS.get(m["module"], m["module"])
        m["rate"] = round(m["got"] / m["total"] * 100, 1) if m["total"] else 0.0
    for s in report.get("slot_stat", []):
        s["label"] = SLOT_LABELS.get(s["slot"], s["slot"])
        s["rate"] = round(s["got"] / s["total"] * 100, 1) if s["total"] else 0.0

    return templates.TemplateResponse(
        request=request, name="report.html",
        context={
            "app_name": settings.app_name,
            "attempt_id": attempt_id,
            "attempt": a,
            "paper": paper,
            "report": report,
            "total": report.get("total", 100),
            "got": report.get("got", 0),
            "rate": round(report.get("got", 0) / max(report.get("total", 100), 1) * 100, 1),
            "used_min": minutes_between(a["started_at"], a["submitted_at"]),
        },
    )


@router.get("/answers/{paper_id}", response_class=HTMLResponse)
def answer_page(request: Request, paper_id: str):
    """独立答案页：题目 + 答案 + 解题思路，单独一页便于打印裁剪。"""
    paper = repo.get_paper(engine, paper_id)
    if not paper:
        return HTMLResponse("试卷不存在", status_code=404)
    items = repo.get_items(engine, paper_id)
    return templates.TemplateResponse(
        request=request, name="answers.html",
        context={
            "app_name": settings.app_name,
            "paper": paper,
            "items": items,
            "slot_labels": SLOT_LABELS,
        },
    )
