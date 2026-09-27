# -*- coding: utf-8 -*-
"""WeasyPrint 在 Windows 上的最小可行性验证：中文能不能正常出 PDF。"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).resolve().parent.parent / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("STEP 1: import WeasyPrint")
try:
    from weasyprint import HTML  # noqa: E402

    print("  OK import")
except Exception as e:
    print(f"  FAIL import: {type(e).__name__}: {e}")
    sys.exit(1)

print("STEP 2: 探测系统中文字体")
font_dir = Path("C:/Windows/Fonts")
for name in ["simsun.ttc", "msyh.ttc", "simhei.ttf", "simkai.ttf"]:
    p = font_dir / name
    flag = "OK  " if p.exists() else "MISS"
    size = p.stat().st_size if p.exists() else 0
    print(f"  {flag} {name} size={size}")

print("STEP 3: 渲染宋体中文 + 分数线 + 表格生成 A4 PDF")
html = """
<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  @page { size: A4; margin: 18mm 15mm; }
  body { font-family: SimSun, serif; font-size: 12pt; line-height: 1.8; }
  h1 { font-family: SimHei, sans-serif; font-size: 18pt; text-align: center; }
  table { border-collapse: collapse; width: 100%; }
  td, th { border: 1px solid #333; padding: 6px; text-align: left; }
  .frac { display:inline-block; vertical-align:middle; text-align:center; font-size:10pt; }
  .frac .num { border-bottom:1px solid #000; padding:0 4px; display:block; }
  .frac .den { padding:0 4px; display:block; }
</style></head><body>
  <h1>广州市小升初数学模拟试卷（排版验证）</h1>
  <p>一、填空题（每空 2 分，共 20 分）</p>
  <p>1. 把 0.48 化成最简分数是 <span class="frac"><span class="num">12</span><span class="den">25</span></span>。</p>
  <p>2. 一个数由 3 个亿、20 个万、6 个千和 7 个一组成，这个数写作（　　）。</p>
  <p>3. 分数应用题：已知单位"1"的 <span class="frac"><span class="num">2</span><span class="den">3</span></span> 是 60，求单位"1"。</p>
  <table><tr><th>题型</th><th>题量</th><th>分值</th></tr>
    <tr><td>填空题</td><td>10</td><td>20</td></tr>
    <tr><td>解决问题</td><td>4</td><td>20</td></tr></table>
  <p>说明：若能看清宋体中文、黑体标题、分数线和表格边框，则排版链路可用。</p>
</body></html>
"""
out = OUT_DIR / "probe_weasyprint.pdf"
try:
    HTML(string=html).write_pdf(target=out.as_posix())
    size = out.stat().st_size
    print(f"  OK pdf={out} size={size} bytes")
    if size < 5000:
        print("  WARN pdf 过小，可能未嵌入字体")
        sys.exit(3)
    print("  PASS WeasyPrint 在 Windows 可用，中文字体正常")
except Exception as e:
    print(f"  FAIL render: {type(e).__name__}: {e}")
    sys.exit(2)
