# -*- coding: utf-8 -*-
"""腾讯文档台账同步端到端验证。

为什么必须回读：
  推送接口返回 200 只说明"请求被受理了"。真实世界里写入可能被 WAF 拦、
  可能落到别的子表、可能因单元格类型不匹配被静默丢弃。
  只有把云端数据读回来、确认写的内容都在，才能说"同步成功"。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

OK, FAIL = [], []


def check(name: str, cond: bool, extra: str = "") -> None:
    (OK if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name}{(' —— ' + extra) if extra else ''}")


async def main() -> int:
    from app.main import app  # noqa: PLC0415
    from app.services import sync_ledger, tcloud  # noqa: PLC0415

    import socket

    import uvicorn
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()

    cfg = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(cfg)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.1)

    base = f"http://127.0.0.1:{port}"
    try:
        async with httpx.AsyncClient(base_url=base, timeout=300, trust_env=False) as c:
            print("1) 生成试卷（生成时即开考，返回 attempt_id）")
            r = await c.post("/api/papers", json={"seed": 987654, "title": "台账同步验证卷"})
            gen = r.json()
            pid, aid = gen["paper_id"], gen["attempt_id"]
            check("生成成功", bool(pid), pid)
            check("同时拿到作答记录 id", bool(aid), aid)

            print("2) 取卷 → 全部答对 → 交卷")
            r = await c.get(f"/api/papers/{pid}")
            paper = r.json()
            items = paper.get("items") or []
            check("取到题目", len(items) == 38, f"{len(items)} 题")
            answers = {str(it["id"]): it["answer"] for it in items}
            r = await c.post(f"/api/attempts/{aid}/submit",
                             json={"answers": answers, "scratch": {}})
            check("交卷 200", r.status_code == 200, str(r.status_code))
            body = r.json()
            rep = body["report"]
            check("满分 100", rep.get("got") == 100, f"got={rep.get('got')}")
            tc = body.get("tcloud", {})
            check("交卷时自动同步台账", tc.get("ok") is True,
                  f"ok={tc.get('ok')} err={tc.get('error', '')}")

            print("3) 直连回读云端台账（关键一步）")
            after = tcloud.read_csv(start_row=0, end_row=30)
            lines = [ln for ln in after.splitlines() if ln.replace(",", "").strip()]
            check("台账至少有表头 + 1 行数据", len(lines) >= 2, f"{len(lines)} 行")
            check("表头正确", "交卷时间" in lines[0] and "得分率" in lines[0], lines[0][:60])
            check("数据行含本次作答 id", aid in after, aid)
            check("数据行含满分 100", "100" in lines[-1], lines[-1][:80])

            print("4) 追加语义：再推一次应追加新行，不覆盖旧行")
            before_n = len(lines)
            r2 = await c.post(f"/api/attempts/{aid}/sync-ledger")
            check("补推 200", r2.status_code == 200, str(r2.status_code))
            after2 = tcloud.read_csv(start_row=0, end_row=30)
            lines2 = [ln for ln in after2.splitlines() if ln.replace(",", "").strip()]
            check("每次交卷产生一行（重复推送就再多一行）",
                  len(lines2) == before_n + 1, f"{before_n} -> {len(lines2)}")
            check("原数据行未被覆盖", aid in after2)

            print("5) 台账总览接口")
            r = await c.get("/api/ledger")
            led = r.json()
            check("接口 200 且 ok", r.status_code == 200 and led.get("ok"), str(led)[:120])
            print(f"     台账 URL：{led.get('url')}")
            print(f"     当前共 {led.get('rows')} 行（含表头）")

            print("6) 表头只写一次（不重复刷）")
            head_count = sum(1 for ln in lines2 if ln.startswith("交卷时间"))
            check("表头只有一行", head_count == 1, f"{head_count} 行")
    finally:
        server.should_exit = True
        await task

    print("=" * 62)
    print(f"通过 {len(OK)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：", "、".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
