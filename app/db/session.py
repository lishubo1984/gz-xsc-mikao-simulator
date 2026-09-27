"""数据库引擎与初始化。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event

from app.core.config import settings


def _ensure_dirs() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.export_dir.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    _ensure_dirs()
    engine = create_engine(
        f"sqlite:///{settings.db_path.as_posix()}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.close()

    return engine


engine = get_engine()


def init_db(schema_path: Path | None = None) -> None:
    """执行建表脚本。schema.sql 是 UTF-8，Windows 下必须显式指定编码。"""
    _ensure_dirs()
    schema_path = schema_path or settings.base_dir / "app" / "db" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(settings.db_path)
    try:
        conn.executescript(sql)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


# 增量列：schema.sql 用 CREATE TABLE IF NOT EXISTS，已存在的表不会被更新，
# 因此新增列必须靠这条幂等迁移补上（ALTER TABLE ADD COLUMN 重复执行会报错，逐个 try）。
_EXTRA_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "paper_items": [
        ("section_instruction", "TEXT"),
    ],
    "attempt_answers": [
        ("scratch", "TEXT"),  # 计算题/应用题的解题过程，网页答题不打草稿就没法学
    ],
}


_EXTRA_INDEXES: list[tuple[str, str, tuple[str, ...]]] = [
    # (索引名, 表名, 参与唯一的列)
    ("ux_attempt_answers", "attempt_answers", ("attempt_id", "item_id")),
]


def _has_unique_index(conn: sqlite3.Connection, table: str, cols: set[str]) -> bool:
    for row in conn.execute(f"PRAGMA index_list({table})"):
        idx_name, is_unique = row[1], row[2]
        if not is_unique:
            continue
        idx_cols = {r[2] for r in conn.execute(f"PRAGMA index_info({idx_name})")}
        if idx_cols == cols:          # 完全一致才算覆盖，避免误判单列唯一索引
            return True
    return False


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in _EXTRA_COLUMNS.items():
        exist = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not exist:
            continue
        for name, decl in cols:
            if name in exist:
                continue
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
            except sqlite3.OperationalError:
                pass

    # 唯一索引：schema.sql 里也写了 CREATE UNIQUE INDEX IF NOT EXISTS，
    # 但老库是在没有这条规则的时候建的，IF NOT EXISTS 管不了已经存在的表。
    for idx_name, table, cols in _EXTRA_INDEXES:
        if _has_unique_index(conn, table, set(cols)):
            continue
        dup = conn.execute(
            f"SELECT COUNT(*) FROM (SELECT {', '.join(cols)} FROM {table} "
            f"GROUP BY {', '.join(cols)} HAVING COUNT(*) > 1)"
        ).fetchone()[0]
        if dup:
            # 有重复行就建不了唯一索引。这里不自动删数据 —— 那是用户的数据，
            # 宁可把情况说清楚，也不悄悄替他做决定。
            print(f"[迁移告警] {table} 有 {dup} 组重复记录，无法创建唯一索引 {idx_name}；"
                  f"请先人工确认这些重复行（按 {', '.join(cols)} 分组）后再重建索引。")
            continue
        conn.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} "
            f"ON {table}({', '.join(cols)})"
        )


def reset_db() -> None:
    """删除库文件重建。仅供开发期使用。"""
    if settings.db_path.exists():
        settings.db_path.unlink()
    for suffix in ("-wal", "-shm"):
        side = settings.db_path.with_name(settings.db_path.name + suffix)
        if side.exists():
            side.unlink()
    init_db()
