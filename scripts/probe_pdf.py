# -*- coding: utf-8 -*-
"""验证降级路线：Playwright 走本机 Edge/Chrome 通道导出中文 A4 PDF（免下载内核）。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parent.parent / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HTML = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  @page { size: A4; margin: 18mm 15mm; }
  * { box-sizing: border-box; }
  body { font-family: "SimSun", "宋体", serif; font-size: 12pt; line-height: 1.9; margin: 0; }
  h1 { font-family: "SimHei", "黑体", sans-serif; font-size: 17pt; text-align: center; margin: 0 0 6mm; }
  .meta { text-align: center; font-size: 10pt; color: #555; margin-bottom: 6mm; }
  h2 { font-family: "SimHei", sans-serif; font-size: 12.5pt; margin: 5mm 0 2mm; }
  table { border-collapse: collapse; width: 100%; font-size: 10.5pt; }
  td, th { border: 1px solid #444; padding: 4px 6px; text-align: left; }
  .frac { display:inline-block; vertical-align:middle; text-align:center; font-size:9pt; line-height:1.15; }
  .frac .num { border-bottom:1px solid #000; padding:0 3px; display:block; }
  .frac .den { padding:0 3px; display:block; }
  .q { margin: 0 0 3mm; }
  .blank { display:inline-block; border-bottom:1px solid #000; min-width: 22mm; }
  .answer-page { page-break-before: always; }
  svg { max-width: 100%; height: auto; }
</style></head><body>
  <h1>2027 届广州小升初数学模拟试卷（排版验证）</h1>
  <div class="meta">满分 100 分　考试时间 100 分钟</div>

  <h2>一、填空题（每小题 2 分，共 20 分）</h2>
  <div class="q">1. 把 0.48 化成最简分数是 <span class="frac"><span class="num">12</span><span class="den">25</span></span>。</div>
  <div class="q">2. 一个数由 3 个亿、20 个万、6 个千和 7 个一组成，这个数写作<span class="blank"></span>。</div>
  <div class="q">3. 已知单位"1"的 <span class="frac"><span class="num">2</span><span class="den">3</span></span> 是 60，单位"1"是<span class="blank"></span>。</div>

  <h2>二、计算题（能简算的要简算）</h2>
  <div class="q">1. 999 &times; 222 + 333 &times; 334 = <span class="blank"></span></div>
  <div class="q">2. <span class="frac"><span class="num">5</span><span class="den">6</span></span> &divide; <span class="frac"><span class="num">10</span><span class="den">11</span></span> = <span class="blank"></span></div>

  <h2>三、图形与几何</h2>
  <svg viewBox="0 0 240 140" width="240">
    <rect x="20" y="20" width="200" height="100" fill="none" stroke="#000" stroke-width="1"/>
    <line x1="20" y1="120" x2="220" y2="20" stroke="#000" stroke-width="1"/>
    <circle cx="120" cy="70" r="45" fill="none" stroke="#c00" stroke-width="1"/>
    <text x="12" y="134" font-size="11">20cm</text>
    <text x="222" y="26" font-size="11">10cm</text>
  </svg>

  <table>
    <tr><th>题型</th><th>题量</th><th>分值</th></tr>
    <tr><td>填空题</td><td>10</td><td>20</td></tr>
    <tr><td>图形与几何</td><td>2</td><td>10</td></tr>
    <tr><td>解决问题</td><td>4</td><td>20</td></tr>
  </table>

  <div class="answer-page"></div>
  <h1>参考答案与解题思路</h1>
  <div class="q">1. <span class="frac"><span class="num">12</span><span class="den">25</span></span>　思路：0.48 = 48/100，同除以 4 得 12/25。</div>
  <div class="q">3. 90　思路：单位"1"未知，用除法 60 &divide; 2/3 = 90。</div>
</body></html>
"""


def try_channel(name: str, channel: str) -> str | None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f"  FAIL import playwright: {e}")
        return None
    out = OUT_DIR / f"probe_{channel}.pdf"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=channel)
            page = browser.new_page()
            page.set_content(HTML, wait_until="load")
            page.emulate_media(media="print")
            page.pdf(
                path=str(out),
                format="A4",
                print_background=True,
                margin={"top": "18mm", "bottom": "18mm", "left": "15mm", "right": "15mm"},
            )
            browser.close()
        size = out.stat().st_size
        print(f"  OK  {name}: {out.name} size={size} bytes")
        return f"{name}|{size}"
    except Exception as e:
        print(f"  FAIL {name}: {type(e).__name__}: {str(e)[:160]}")
        return None


print("=== Playwright 中文 PDF 导出验证（本机浏览器通道，免下载内核）===")
results = []
r = try_channel("Edge", "msedge")
if r:
    results.append(r)
r = try_channel("Chrome", "chrome")
if r:
    results.append(r)

if results:
    print(f"PASS 可用通道 {len(results)} 个：{', '.join(results)}")
else:
    print("FAIL 无可用浏览器通道")
    sys.exit(1)
