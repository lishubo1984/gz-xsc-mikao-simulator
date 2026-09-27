"""把本机作答成绩同步到腾讯文档在线台账。

同步语义：**只增不改**。
  每次交卷找到台账里第一处空行追加一行，不重写已有行。
  这样即使云端被家长手动改过（改备注、标重点），也不会被下一次同步冲掉。
  代价是同一份卷子重复交卷会出现多行 —— 但那本来就应该出现多行，
  每次作答都是一条独立记录。

失败处理：同步是交卷的旁路，任何异常都只记进返回值，不向上抛。
"""
from __future__ import annotations

from sqlalchemy import Engine, text

from app.services import repository as repo
from app.services import tcloud
from app.services.knowledge import load_graph, node_index


def _weak_names(report: dict) -> list[str]:
    """把薄弱知识点的 id 换成中文名，台账上给家长看的是名字不是 id。"""
    nodes = node_index(load_graph())
    out = []
    for w in report.get("weak_points", []):
        kid = w.get("id") if isinstance(w, dict) else str(w)
        out.append(nodes.get(kid, {}).get("name", str(kid)))
    return out


def _used_minutes(engine: Engine, attempt_id: str) -> int:
    with engine.connect() as conn:
        row = conn.execute(
            text("""SELECT started_at, submitted_at FROM attempts WHERE id = :aid"""),
            {"aid": attempt_id},
        ).mappings().first()
    if not row or not row["submitted_at"]:
        return 0
    try:
        from datetime import datetime
        s = datetime.strptime(str(row["started_at"]), "%Y-%m-%d %H:%M:%S")
        e = datetime.strptime(str(row["submitted_at"]), "%Y-%m-%d %H:%M:%S")
        return max(0, round((e - s).total_seconds() / 60))
    except (ValueError, TypeError):
        return 0


def _filled_rows(csv_data: str) -> int:
    """从 CSV 头部开始，连续有内容的行数。

    真实踩坑：空表的回读结果不是空串，而是一批只有逗号的空行
    （200 行的空表会返回 200 个 ',,,,,,,,,'）。
    只看 ln.strip() 判断不出"空"——逗号 strip 不掉，会被当成有内容，
    于是第一次同步就写到第 200 行去了。
    所以判空必须"去掉逗号和空白后还剩没剩东西"。
    """
    filled = 0
    for ln in (csv_data or "").splitlines():
        if _row_is_blank(ln):
            # 遇到第一处真空白就停：表是按行追加的，后面不可能再有内容
            break
        filled += 1
    return filled


def _row_is_blank(csv_line: str) -> bool:
    """判断 CSV 的一行是不是"真空白"。

    真实踩坑：空单元格回读出来不是空串，而是一串逗号（',,,,,,,,,'）。
    逗号 strip 不掉，所以 `if not line.strip()` 永远为假 ——
    表头因此从来没被写进去过，第一条数据直接落在第 1 行把表头占了。
    唯一可靠的判空方式是：把逗号和空白全去掉再看还剩什么。
    """
    return not csv_line.replace(",", "").strip()


def _ensure_header(file_id: str, sheet_id: str) -> None:
    """表头只在台账还是空表时写一次，避免每次同步都把表头重刷一遍。"""
    first = tcloud.read_csv(file_id, sheet_id, start_row=0, end_row=0)
    line = first.splitlines()[0] if first.splitlines() else ""
    if not _row_is_blank(line):
        return
    tcloud.push_rows([tcloud.HEADERS], file_id, sheet_id, start_row=0)


def push_attempt(engine: Engine, attempt_id: str,
                 file_id: str = tcloud.DEFAULT_FILE_ID,
                 sheet_id: str = tcloud.DEFAULT_SHEET_ID) -> dict:
    """把一次作答推送到云端台账，并回读校验。"""
    a = repo.get_attempt(engine, attempt_id)
    if not a:
        raise ValueError(f"作答记录不存在：{attempt_id}")
    if not a.get("report"):
        raise ValueError("这份作答还没交卷，没有可同步的成绩")

    import json
    report = json.loads(a["report"])
    paper = repo.get_paper(engine, a["paper_id"])
    used_min = _used_minutes(engine, attempt_id)

    row = tcloud.ledger_row(a, report, paper or {}, _weak_names(report), used_min)

    _ensure_header(file_id, sheet_id)
    # 从第 1 行起读（第 0 行是表头），数出已有多少条数据，
    # 追加位置 = 表头 1 行 + 已有数据行数
    existing = tcloud.read_csv(file_id, sheet_id, start_row=1)
    start_row = 1 + _filled_rows(existing)
    tcloud.push_rows([row], file_id, sheet_id, start_row=start_row)

    # 回读校验：只看接口返回 200 就宣布成功是自欺欺人 ——
    # 写入可能被 WAF 拦、可能落到别的子表、可能因类型不匹配被丢弃。
    after = tcloud.read_csv(file_id, sheet_id, start_row=start_row,
                            end_row=start_row)
    landed = after.strip()
    ok = bool(landed) and str(report.get("got", "")) in landed

    return {
        "ok": ok,
        "file_id": file_id,
        "sheet_id": sheet_id,
        "row": start_row + 1,          # 给用户看的 1-based 行号
        "written": row,
        "readback": landed[:200],
        "url": f"https://docs.qq.com/sheet/{file_id}",
    }


def ledger_summary(file_id: str = tcloud.DEFAULT_FILE_ID,
                   sheet_id: str = tcloud.DEFAULT_SHEET_ID) -> dict:
    """台账现状：行数与前几行，用来确认同步落地。

    行数必须只数"有内容"的行：空表的回读是一大片逗号空行，
    照单全收会报出"共有 200 行"这种假数据，反而让人以为同步出问题了。
    """
    csv_data = tcloud.read_csv(file_id, sheet_id, start_row=0, end_row=200)
    lines = [ln for ln in csv_data.splitlines() if not _row_is_blank(ln)]
    return {
        "file_id": file_id,
        "sheet_id": sheet_id,
        "url": f"https://docs.qq.com/sheet/{file_id}",
        "rows": len(lines),                    # 含表头
        "records": max(0, len(lines) - 1),     # 纯成绩条数
        "head": lines[:6],
        "hash": tcloud.content_hash(lines),
    }
