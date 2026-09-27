"""腾讯文档（在线表格）同步：把交卷成绩推到云端台账。

设计取舍（为什么是"单向推送 + 哈希回读"而不是"双向同步"）：
  双向同步要处理冲突合并，而这份台账只有本机的作答会产生数据 ——
  孩子做题在本地，云端表格是给家长在手机上看结果的只读台账。
  强行做双向，只会引入"云端被手改后回灌脏数据"的风险。
  所以：SQLite 是唯一权威源，云端是它的投影；推送后再回读比对哈希，
  确认"云端真的落地了"，而不是只看接口返回 200 就当成功。

为什么要外部注入 base_url：
  宿主的凭据网关下发的 apiBase 是 https://www-docs.workbuddy.cn，
  这个域名在本机 DNS 解析不出来（getaddrinfo failed）。
  显式指定 https://docs.qq.com 可绕过。环境变量 TDOC_API_BASE_URL 优先。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# Tencent Docs skill 的调用入口（宿主插件目录）
_SKILL_DIR = Path(os.environ.get(
    "TDOC_SKILL_DIR",
    str(Path.home() / ".workbuddy" / "plugins" / "cache" / "workbuddy-builtin"
        / "tencent-docs-plugin" / "5.6.2-wb.39298511.g37a65c0b.he233403f909a"
        / "skills" / "tencent-docs"),
))

# 台账表格（2026-10-05 创建）
DEFAULT_FILE_ID = os.environ.get("TDOC_LEDGER_FILE_ID", "DUmINmkGyeTH")
DEFAULT_SHEET_ID = os.environ.get("TDOC_LEDGER_SHEET_ID", "BB08J2")

# 表头：一次定好，后续行按这个顺序写
HEADERS = ["交卷时间", "试卷标题", "得分", "满分", "得分率", "用时(分)",
           "错题数", "薄弱知识点Top3", "作答记录ID", "试卷ID"]


class TCloudError(RuntimeError):
    pass


def _python() -> str:
    return os.environ.get("TDOC_PYTHON") or sys.executable


def call(service: str, tool: str, args: dict) -> dict:
    """调一次腾讯文档 MCP 工具，返回 structuredContent。"""
    if not _SKILL_DIR.exists():
        raise TCloudError(f"找不到腾讯文档 skill 目录：{_SKILL_DIR}")

    env = dict(os.environ)
    # 宿主下发的 apiBase 域名解析不了，显式覆盖成个人版正式域名
    env["TDOC_API_BASE_URL"] = os.environ.get("TDOC_API_BASE_URL",
                                              "https://docs.qq.com")
    proc = subprocess.run(
        [_python(), "tencentdocs.py", "--no-proxy", "tdoc_call",
         service, tool, json.dumps(args, ensure_ascii=False)],
        cwd=str(_SKILL_DIR), env=env, capture_output=True, timeout=180,
    )
    out = proc.stdout.decode("utf-8", errors="replace").strip()
    if not out.startswith("{"):
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise TCloudError(f"腾讯文档调用失败（{tool}）：{out or err}")

    payload = json.loads(out)
    if "error" in payload and payload.get("result") is None:
        raise TCloudError(f"腾讯文档返回错误（{tool}）：{payload['error']}")

    result = payload.get("result", {})
    if "structuredContent" in result:
        return result["structuredContent"]
    # 部分工具只回 content[0].text 里包一层 JSON
    for c in result.get("content", []):
        if c.get("type") == "text":
            try:
                return json.loads(c["text"])
            except json.JSONDecodeError:
                return {"text": c["text"]}
    return result


# --------------------------------------------------------------------------
# 台账行
# --------------------------------------------------------------------------
def ledger_row(attempt: dict, report: dict, paper: dict,
               weak_names: list[str], used_min: int) -> list:
    """把一次交卷整理成台账的一行。顺序必须与 HEADERS 一致。"""
    got = report.get("got", 0)
    total = report.get("total", 100) or 100
    return [
        str(attempt.get("submitted_at") or attempt.get("started_at") or ""),
        str(paper.get("title") or ""),
        got,
        total,
        f"{round(got / total * 100, 1)}%",
        used_min,
        len(report.get("wrong_details", [])),
        "、".join(weak_names[:3]),
        str(attempt.get("id") or ""),
        str(paper.get("id") or ""),
    ]


def _csv_cell(v) -> str:
    """CSV 转义：含逗号/引号/换行的字段必须加引号。"""
    s = "" if v is None else str(v)
    if any(ch in s for ch in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


def push_rows(rows: list[list], file_id: str = DEFAULT_FILE_ID,
              sheet_id: str = DEFAULT_SHEET_ID, start_row: int = 1) -> dict:
    """从 start_row 起批量写入（start_row=0 时连表头一起写）。

    用 set_range_value_by_csv 一次提交：逐格调 set_cell_value 写 38 行 × 10 列
    要发 380 次请求，既慢又容易中途失败留半张表。
    """
    csv_data = "\n".join(",".join(_csv_cell(c) for c in r) for r in rows)
    return call("sheet-mcp", "set_range_value_by_csv", {
        "file_id": file_id, "sheet_id": sheet_id,
        "start_row": start_row, "start_col": 0, "csv_data": csv_data,
    })


def read_csv(file_id: str = DEFAULT_FILE_ID, sheet_id: str = DEFAULT_SHEET_ID,
             start_row: int = 0, end_row: int = 200,
             end_col: int = len(HEADERS) - 1) -> str:
    """以 CSV 回读台账，用于校验推送是否真的落地。

    工具名是 get_cell_data（不是 get_cell_ranges —— 后者属于另一个 MCP 服务，
    在 sheet-mcp 里不存在，调用会直接 tool_not_found）。
    """
    r = call("sheet-mcp", "get_cell_data", {
        "file_id": file_id, "sheet_id": sheet_id,
        "start_row": start_row, "end_row": end_row,
        "start_col": 0, "end_col": end_col,
        "return_csv": True,
    })
    return r.get("csv_data", "") if isinstance(r, dict) else ""


def content_hash(rows: list[list]) -> str:
    """对行内容取哈希，用来判断"云端与我算的是不是同一份数据"。"""
    blob = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
