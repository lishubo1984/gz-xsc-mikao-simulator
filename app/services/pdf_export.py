"""HTML → A4 PDF。

为什么用 Playwright 而不是 WeasyPrint：
  WeasyPrint 在本机装不上（需要 GTK3 原生库，Windows 无官方 wheel），
  早期试了三次都卡在依赖上。按事先跟用户约定好的降级路径改用
  Playwright 驱动本机 Edge/Chromium —— 它跟真实浏览器同一套渲染引擎，
  网页上是什么样、打印出来就是什么样，不会出现"网页对、PDF 乱"。

为什么用 async API 而不是 sync API：
  playwright-python 的 sync API 内部靠 greenlet 实现，跨线程复用同一个
  实例会炸；FastAPI 的 async 路由跑在事件循环里，用 async_playwright
  常驻一个 browser 既安全又不用每次导出都冷启动（冷启动约 1.5 秒）。

为什么要 --no-proxy-server：
  本机环境变量里设了 HTTP_PROXY=127.0.0.1:15585，Chromium 会照着走，
  连 about:blank 都要过一遍代理，偶发卡死。
"""
from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import async_playwright

# 依次尝试：本机装的是 Edge 就用 Edge，其次 Chrome，最后回退到 Playwright 自带内核
_CHANNELS: tuple[str | None, ...] = ("msedge", "chrome", None)

_pw: Any = None
_browser: Any = None
_lock = asyncio.Lock()

_MARGIN = {"top": "14mm", "bottom": "16mm", "left": "14mm", "right": "14mm"}

# header/footer 模板里必须自己写 font-size 且留够 margin，
# 否则 Chromium 默认 0 边距会把页码裁掉 —— 这是 Playwright 的经典坑。
_FOOTER_TPL = """
<div style="width:100%;font-size:8px;color:#666;padding:0 14mm;
            display:flex;justify-content:space-between;">
  <span>{tag}</span>
  <span>第 <span class="pageNumber"></span> 页 / 共 <span class="totalPages"></span> 页</span>
</div>
"""
_HEADER_TPL = """
<div style="width:100%;font-size:8px;color:#666;padding:0 14mm;
            display:flex;justify-content:space-between;">
  <span>{tag}</span><span>{right}</span>
</div>
"""


async def _get_browser():
    global _pw, _browser
    async with _lock:
        if _browser is None:
            _pw = await async_playwright().start()
            last_err: Exception | None = None
            for ch in _CHANNELS:
                try:
                    if ch:
                        _browser = await _pw.chromium.launch(
                            channel=ch, args=["--no-proxy-server"])
                    else:
                        _browser = await _pw.chromium.launch(
                            args=["--no-proxy-server"])
                    break
                except Exception as e:  # noqa: BLE001 - 逐个渠道试，最后一个才抛出
                    last_err = e
            if _browser is None:
                raise RuntimeError(
                    "找不到可用的 Chromium 内核（已试 msedge / chrome / 内置）。"
                    f"最后的错误：{last_err}")
    return _browser


async def render_pdf(html: str, *, tag: str = "", right: str = "") -> bytes:
    """把一段完整 HTML（CSS 必须已内联）渲染成 A4 PDF。

    走 set_content 而不是 goto 本机地址，是有意的：goto 会让服务在处理
    自己发出的请求时再起一个请求，单 worker 下容易把自己绕死；而且
    set_content 不依赖服务端口，导出逻辑可以脱离 Web 单独跑（脚本里也用得上）。
    """
    browser = await _get_browser()
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="load")
        # 必须切到 print 媒体：页面里 @media print 的排版规则（隐藏按钮、
        # 大题不跨页、留白高度）只有在这一步之后才生效。
        await page.emulate_media(media="print")
        return await page.pdf(
            format="A4",
            print_background=True,
            margin=_MARGIN,
            display_header_footer=True,
            header_template=_HEADER_TPL.format(tag=tag, right=right),
            footer_template=_FOOTER_TPL.format(tag=tag),
        )
    finally:
        await page.close()


async def shutdown() -> None:
    """关闭常驻浏览器。FastAPI 的 shutdown 钩子里调用，否则进程退出会有残留。"""
    global _pw, _browser
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _pw is not None:
        await _pw.stop()
        _pw = None
