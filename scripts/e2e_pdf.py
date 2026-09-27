# -*- coding: utf-8 -*-
"""PDF 导出端到端验证。

为什么只看 HTTP 200 不够：
  返回 application/pdf 且状态码 200，只能证明"没抛异常"。
  真正的坑是——PDF 只有 1 页且全白（CSS 没内联、@media print 没生效）、
  或者图形不见了、或者文字被裁掉。这些 200 全都看不出来，
  必须真的把 PDF 打开，数页数、抽文本、看图形。
"""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

OK, FAIL = [], []

PAPER_TITLE = "PDF验证卷"


def check(name: str, cond: bool, extra: str = "") -> None:
    (OK if cond else FAIL).append(name)
    print(f"  {'✓' if cond else '✗'} {name}{(' —— ' + extra) if extra else ''}")


async def _gen_paper(client: httpx.AsyncClient) -> str:
    r = await client.post("/api/papers", json={"seed": 20261005, "title": PAPER_TITLE})
    r.raise_for_status()
    return r.json()["paper_id"]


def _pdf_pages(data: bytes) -> int:
    """数 PDF 页数：优先用 pypdf，没装就退回数 /Type /Page 对象。"""
    try:
        import io

        from pypdf import PdfReader
        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa: BLE001
        return len(re.findall(rb"/Type\s*/Page[^s]", data))


def _pdf_text(data: bytes) -> str:
    try:
        import io

        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa: BLE001
        return ""


def _compact(text: str) -> str:
    """去掉所有空白再匹配。

    真实踩坑：pypdf 抽中文时会在每个字之间插一个空格（"填空题" -> "填 空 题"），
    因为 CJK 字形在 PDF 里是逐个独立定位的。直接 in 判断必然假失败。
    断言前先压掉空白，才能反映"PDF 里到底有没有这几个字"。
    """
    return re.sub(r"\s+", "", text)


async def _screenshot(client: httpx.AsyncClient, pid: str) -> tuple[int, int]:
    """把打印预览页整页截图，留档给人眼看排版。

    PDF 的字节流能证明"生成了"，证明不了"好不好看"。留白够不够、图形有没有被
    压扁、分数竖式有没有错位，只能看图。
    """
    from playwright.async_api import async_playwright

    out = ROOT / "exports"
    out.mkdir(exist_ok=True)
    sizes = []
    async with async_playwright() as pw:
        for ch in ("msedge", "chrome", None):
            try:
                b = await (pw.chromium.launch(channel=ch, args=["--no-proxy-server"])
                           if ch else pw.chromium.launch(args=["--no-proxy-server"]))
                break
            except Exception:  # noqa: BLE001
                continue
        else:
            return (0, 0)
        pg = await b.new_page(viewport={"width": 900, "height": 1200},
                              device_scale_factor=1)
        for url, name in ((f"{client.base_url}/papers/{pid}/print", "shot_print_paper.png"),
                          (f"{client.base_url}/answers/{pid}/print", "shot_print_answers.png")):
            await pg.goto(url, wait_until="load", timeout=60000)
            await pg.emulate_media(media="print")
            await pg.screenshot(path=str(out / name), full_page=True)
            sizes.append((out / name).stat().st_size)
        await b.close()
    return (sizes[0], sizes[1])


async def main() -> int:
    from app.main import app  # noqa: PLC0415

    import uvicorn

    # 自己拉一个服务：端口动态挑，避免连到上一轮残留的进程上
    import socket
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
        # 必须用 AsyncClient：本脚本在同一个事件循环里既跑 uvicorn 又发请求，
        # 同步 httpx 会一把把 loop 卡死，服务器根本没机会处理请求，表现为超时。
        # trust_env=False：本机 HTTP_PROXY 会把 127.0.0.1 的请求也送进代理。
        async with httpx.AsyncClient(base_url=base, timeout=300, trust_env=False) as c:
            print("1) 生成试卷")
            pid = await _gen_paper(c)
            check("生成成功", bool(pid), pid)

            print("2) 学生作答卷 PDF")
            r = await c.get(f"/papers/{pid}/pdf")
            check("HTTP 200", r.status_code == 200, str(r.status_code))
            check("Content-Type 是 PDF", "pdf" in r.headers.get("content-type", ""))
            check("有下载文件名", "attachment" in r.headers.get("content-disposition", ""))
            paper_pdf = r.content
            check("非空", len(paper_pdf) > 5000, f"{len(paper_pdf)} 字节")
            np_ = _pdf_pages(paper_pdf)
            check("页数 ≥ 3（A4 单栏大留白，38 题不可能一页装下）", np_ >= 3, f"{np_} 页")
            txt = _pdf_text(paper_pdf)
            ctxt = _compact(txt)
            check("含试卷标题", PAPER_TITLE in ctxt)
            check("含姓名/班级/得分栏", all(k in ctxt for k in ("姓名", "班级", "得分")))
            check("含七大题型标题",
                  all(k in ctxt for k in ("填空题", "选择题", "判断题", "计算题")))
            # 页码里的"页"在 PDF 里会被映射成兼容区字形 ⻚（U+2EDA），两种都要认
            check("含页码", re.search(r"第\s*\d+\s*[页⻚]\s*/\s*共\s*\d+", ctxt) is not None)
            # 作答卷绝不能带答案：答案页的大标题与各题答案不应出现在作答卷。
            # 注意不能简单断言"解题思路"四个字 —— 附加题的卷面说明
            # "写出解题思路可得部分分数"本来就该印在卷子上。
            check("不泄露答案", "答案与解题思路" not in ctxt)
            # 也不该印知识点名：真实卷子上没有这一栏，印了等于白送考点
            check("不泄露知识点名", "最大公因数与最小公倍数" not in ctxt)
            # 分数渲染：[[2/9]] 这类竖式分数在 PDF 里必须有内容而不是空白
            check("分数题有渲染内容", "单位" in ctxt or "最简分数" in ctxt)

            print("3) 答案与思路页 PDF")
            r = await c.get(f"/answers/{pid}/pdf")
            check("HTTP 200", r.status_code == 200, str(r.status_code))
            ans_pdf = r.content
            check("非空", len(ans_pdf) > 5000, f"{len(ans_pdf)} 字节")
            na = _pdf_pages(ans_pdf)
            check("页数 ≥ 2", na >= 2, f"{na} 页")
            atxt = _pdf_text(ans_pdf)
            catxt = _compact(atxt)
            check("含解题思路表头", "解题思路" in catxt)
            check("答案页与作答卷内容不同", catxt != ctxt)
            check("答案页含答案列", "答案" in catxt)

            print("4) 目视留档：把打印版渲染成 PNG")
            shots = await _screenshot(c, pid)
            check("作答卷截图已生成", shots[0] > 20000, f"{shots[0]} 字节")
            check("答案页截图已生成", shots[1] > 20000, f"{shots[1]} 字节")

            out = ROOT / "exports"
            out.mkdir(exist_ok=True)
            (out / "sample_paper_print.pdf").write_bytes(paper_pdf)
            (out / "sample_answers_print.pdf").write_bytes(ans_pdf)
            print(f"\n样品已存：exports/sample_paper_print.pdf、exports/sample_answers_print.pdf")
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
