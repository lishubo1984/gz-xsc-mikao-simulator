# -*- coding: utf-8 -*-
"""真浏览器验证：起服务 → 出卷 → 用 Chromium(Edge) 走一遍页面 → 截图 + 导出 PDF。

为什么不只用 httpx：HTTP 200 只能证明服务端没抛异常，
证明不了页面真的渲染出来了 —— 空白页、CSS 404、JS 报错照样返回 200。
这个脚本打开真实浏览器，同时把三个关键页面导出成 A4 PDF，顺带验证打印链路。

坑记：
  * 本机环境有 HTTP_PROXY=127.0.0.1:15585，Chromium 照 env 走会把本地请求也送去代理，
    页面全部打不开。启动必须加 --no-proxy-server。
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "exports"
OUT.mkdir(parents=True, exist_ok=True)
PY = sys.executable


def free_port() -> int:
    import socket

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = int(s.getsockname()[1])
    s.close()
    return p


def wait_health(url: str, timeout: float = 60.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if httpx.get(url + "/api/health", timeout=2.0, trust_env=False).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def start_server(port: int):
    log = OUT / "uvicorn_web.log"
    f = open(log, "w", encoding="utf-8")
    import os

    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=f, stderr=subprocess.STDOUT,
    )
    if not wait_health(f"http://127.0.0.1:{port}"):
        proc.kill()
        f.close()
        print("服务启动失败：\n", log.read_text(encoding="utf-8", errors="replace")[-3000:])
        return None, None
    return proc, f


def main() -> int:
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    print("服务:", base)
    proc, logf = start_server(port)
    if proc is None:
        return 1

    errs: list[str] = []
    ok = 0

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal ok
        if cond:
            ok += 1
            print("  ✓", name)
        else:
            errs.append(f"{name} {extra}")
            print("  ✗", name, extra)

    try:
        c = httpx.Client(base_url=base, timeout=60.0, trust_env=False)
        r = c.post("/api/papers", json={"student": "真实-browser", "seed": 20260930})
        r.raise_for_status()
        gen = r.json()
        attempt_id, paper_id = gen["attempt_id"], gen["paper_id"]
        print("   出卷 OK:", gen["question_count"], "题")

        with sync_playwright() as p:
            # channel="msedge" 用本机已装的 Edge，不必下载 150MB 内核；装不了再回退默认
            browser = None
            for chan in ("msedge", "chrome", None):
                try:
                    browser = p.chromium.launch(channel=chan, args=["--no-proxy-server"])
                    print(f"   浏览器通道: {chan or '内置'}")
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"   通道 {chan} 不可用: {type(exc).__name__}")
            if browser is None:
                print("没有可用浏览器")
                return 1

            ctx = browser.new_context(viewport={"width": 1280, "height": 1000},
                                      locale="zh-CN",
                                      # 本地服务别走代理，否则每个请求都被 15585 拦一道
                                      proxy=None)
            page = ctx.new_page()

            console_errors: list[str] = []
            # console 的 404 文案里并不带 URL，只过滤 "favicon" 文本会漏掉它，
            # 所以再挂一层 response 监听把非 2xx 的真实路径记下来。
            bad_urls: list[str] = []
            page.on("console", lambda m: console_errors.append(m.text)
                    if m.type == "error" else None)
            page.on("pageerror", lambda e: console_errors.append(f"PAGEERROR {e}"))
            page.on("response", lambda r: bad_urls.append(f"{r.status} {r.url}")
                    if r.status >= 400 else None)

            print("1) 首页")
            page.goto(f"{base}/", wait_until="networkidle")
            check("标题正确", "广州小升初密考模拟系统" in page.title())
            check("页面有内容", page.inner_text("body").strip() != "")
            page.screenshot(path=str(OUT / "shot_index.png"), full_page=True)

            print("2) 答题页")
            page.goto(f"{base}/paper/{attempt_id}", wait_until="networkidle")
            body = page.inner_text("body")
            check("含七大题型", all(t in body for t in
                  ["一、填空题", "二、选择题", "三、判断题", "四、计算题",
                   "五、图形与几何", "六、解决问题", "七、附加题"]))
            blanks = page.locator(".blank, .ans-input").count()
            choices = page.locator(".q-choices").count()
            judges = page.locator(".q-judge").count()
            print(f"   填空控件 {blanks} · 选择题 {choices} · 判断题 {judges}")
            check("有可作答控件", blanks + choices + judges > 30,
                  f"控件总数 {blanks + choices + judges}")
            check("倒计时已启动", "--:--" not in page.inner_text("#clock"),
                  page.inner_text("#clock"))
            page.screenshot(path=str(OUT / "shot_paper.png"), full_page=True)

            print("3) 模拟作答后立即离开（验证作答不丢）")
            page.locator(".ans-input, .blank").first.fill("123")
            page.wait_for_timeout(1000)
            page.reload(wait_until="networkidle")
            check("刷新后答案仍在", page.locator(".ans-input, .blank").first.input_value() == "123",
                  repr(page.locator(".ans-input, .blank").first.input_value()))

            print("4) 交卷 → 报告页")
            answers = c.get(f"/api/papers/{paper_id}/answers").json()["items"]
            items = c.get(f"/api/papers/{paper_id}").json()["items"]
            id_by_seq = {it["seq"]: it["id"] for it in items}
            payload = {"answers": {str(id_by_seq[row["seq"]]): row["answer"] for row in answers},
                       "remaining_sec": 2500}
            sr = c.post(f"/api/attempts/{attempt_id}/submit", json=payload)
            sr.raise_for_status()
            got = sr.json()["report"]["got"]
            check("全对满分", got == 100, f"实得 {got}")

            page.goto(f"{base}/report/{attempt_id}", wait_until="networkidle")
            rbody = page.inner_text("body")
            check("报告页显示得分", "100" in rbody)
            check("报告页含薄弱分析", ("薄弱" in rbody or "全对" in rbody))
            page.screenshot(path=str(OUT / "shot_report.png"), full_page=True)

            print("5) 答案页")
            page.goto(f"{base}/answers/{paper_id}", wait_until="networkidle")
            abody = page.inner_text("body")
            check("含解题思路", "解题思路" in abody)
            page.screenshot(path=str(OUT / "shot_answers.png"), full_page=True)

            print("6) 导出 PDF（A4）")
            page.goto(f"{base}/answers/{paper_id}", wait_until="networkidle")
            page.emulate_media(media="print")
            page.pdf(path=str(OUT / "sample_answers.pdf"), format="A4",
                     print_background=True, margin={"top": "12mm", "bottom": "12mm",
                                                    "left": "10mm", "right": "10mm"})
            size = (OUT / "sample_answers.pdf").stat().st_size
            check("答案页 PDF 生成", size > 20_000, f"{size} 字节")

            real_console = [e for e in console_errors if "favicon" not in e.lower()]
            check("无浏览器控制台报错", not real_console, str(real_console[:3]))
            check("无 4xx/5xx 资源", not bad_urls, str(bad_urls[:5]))

            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        if logf:
            logf.close()

    print()
    print("=" * 62)
    print(f"通过 {ok} 项，失败 {len(errs)} 项")
    for e in errs:
        print("  FAIL:", e)
    if not errs:
        print("截图/样品：", ", ".join(p.name for p in sorted(OUT.glob("shot_*.png"))))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
