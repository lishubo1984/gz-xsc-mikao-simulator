"""全局配置。"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GZXSC_", extra="ignore")

    app_name: str = "广州小升初密考模拟系统"
    base_dir: Path = BASE_DIR
    data_dir: Path = BASE_DIR / "data"
    export_dir: Path = BASE_DIR / "exports"
    db_path: Path = BASE_DIR / "data" / "exam.db"
    graph_yaml: Path = BASE_DIR / "data" / "knowledge_graph.yaml"

    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = True

    # 腾讯文档同步（留空则不同步，仅本地库）
    tencent_docs_cookie: str = ""
    question_sheet_id: str = ""
    result_sheet_id: str = ""


settings = Settings()

# 题型中文名，供 UI 与导出复用
SLOT_LABELS: dict[str, str] = {
    "fill": "填空题",
    "choice": "选择题",
    "judge": "判断题",
    "calc": "计算题",
    "geometry": "图形与几何",
    "solve": "解决问题",
    "extra": "附加题",
}

MODULE_LABELS: dict[str, str] = {
    "number_algebra": "数与代数",
    "fraction_percent": "分数与百分数应用",
    "travel": "行程问题",
    "geometry": "空间与图形",
    "ratio_proportion": "比和比例",
    "misc_comprehensive": "其他综合应用",
}
