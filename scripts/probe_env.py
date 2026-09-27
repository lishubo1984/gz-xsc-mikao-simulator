# -*- coding: utf-8 -*-
"""一次性探测本机 PDF 导出链路的所有可行路径。"""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

print("=== A. GTK 运行时（WeasyPrint 的硬依赖）===")
gtk_dll = "libgobject-2.0-0.dll"
candidates = [
    r"C:\Windows\System32",
    r"C:\Program Files\GTK3-Runtime Win64\bin",
    r"C:\Program Files\GIMP 2\bin",
    r"C:\Program Files\Inkscape\bin",
    r"C:\msys64\mingw64\bin",
    r"C:\Users\li.shubo\.workbuddy\binaries\PortableGit\versions\1.2.0\mingw64\bin",
    r"C:\ProgramData\chocolatey\lib\gtk-runtime\tools\gtk-nsis-pack\bin",
]
found_gtk = False
for d in candidates:
    p = Path(d) / gtk_dll
    if p.exists():
        print(f"  FOUND  {p}")
        found_gtk = True
if not found_gtk:
    print(f"  MISS   {gtk_dll} 在所有候选路径均未找到 -> WeasyPrint 需额外安装 GTK runtime")

print("=== B. 本机浏览器（Playwright 可走系统通道，免下载内核）===")
browsers = {
    "Edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "Chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "Chromium": r"C:\Users\li.shubo\AppData\Local\Chromium\Application\chrome.exe",
}
usable = []
for name, path in browsers.items():
    if Path(path).exists():
        print(f"  FOUND  {name}: {path}")
        usable.append(name)
if not usable:
    print("  MISS   未发现任何 Chromium 系浏览器")

print("=== C. Playwright 是否已安装 ===")
try:
    import playwright  # noqa: F401

    print("  OK     playwright 已安装")
except ImportError:
    print("  MISS   playwright 未安装")

print("=== D. CairoSVG / reportlab 可用性 ===")
for mod in ("cairosvg", "reportlab"):
    try:
        __import__(mod)
        print(f"  OK     {mod} 可 import")
    except Exception as e:
        print(f"  MISS   {mod}: {type(e).__name__}: {str(e)[:80]}")

print("=== E. 磁盘剩余空间（C 盘 / D 盘）===")
try:
    import shutil

    for drive in ("C:\\", "D:\\"):
        t, u, f = shutil.disk_usage(drive)
        print(f"  {drive}  free={f / 1024**3:.1f} GB  total={t / 1024**3:.1f} GB")
except Exception as e:
    print(f"  FAIL disk: {e}")
