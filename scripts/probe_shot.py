# -*- coding: utf-8 -*-
"""把验证 HTML 渲染成 PNG，用于肉眼确认中文字体与排版（train孩 eye check）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parent.parent / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HTML_PATH = Path(__file__).resolve().parent.parent / "app" / "web" / "templates" / "_print_base.html"
if not HTML_PATH.exists():
    # 复用 probe_pdf 里的同一份 HTML，保证看到的就是 PDF 看到的
    import probe_pdf  # noqa: F401

try:
    from playwright.sync_api import sync_playwright
except ImportError as e:
    print(f"FAIL import playwright: {e}")
    sys.exit(1)

# 直接内联同一份 HTML（与 PDF 验证同源，避免两处漂移）
HTML = open(Path(__file__).resolve().parent / "probe_pdf.py", encoding="utf-8").read()
start = HTML.index('HTML = """') + len('HTML = """')
end = HTML.index('"""', start)
HTML = HTML[start:end]

out = OUT_DIR / "probe_shot.png"
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 794, "height": 1123})  # A4 @96dpi
        page.set_content(HTML, wait_until="load")
        page.emulate_media(media="print")
        page.wait_for_timeout(400)
        page.screenshot(path=str(out), full_page=True)
        browser.close()
    print(f"OK shot={out} size={out.stat().st_size} bytes")
except Exception as e:
    print(f"FAIL screenshot: {type(e).__name__}: {e}")
    sys.exit(2)
