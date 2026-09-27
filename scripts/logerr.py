# -*- coding: utf-8 -*-
"""把 uvicorn 日志里的异常金字塔压平成两行看看的东西 —— 项目文件帧 + 错误类型。

服务器上一个 500 会在日志里铺两百行 traceback，绝大部分是 site-packages 的套娃，
真正有用的是「本项目文件哪一行的哪个函数」和「最后那个 Error」。
用法：python scripts/logerr.py [日志文件]  默认 exports/uvicorn_e2e.log
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_FRAME = re.compile(r'File "([^"]+)", line (\d+), in (\w+)\n(?:    (.*)\n)?')
_ERR = re.compile(r'^(\w+(?:\.\w+)*Error|\w+Exception): (.*)$', re.M)


def main() -> int:
    log = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "exports" / "uvicorn_e2e.log"
    text = io.open(log, encoding="utf-8", errors="replace").read()
    if not text.strip():
        print("日志为空，服务端可能从未收到请求")
        return 0

    print("== 错误类型 ==")
    seen = set()
    for m in _ERR.finditer(text):
        line = m.group(0)[:300]
        if line not in seen:
            seen.add(line)
            print(" -", line)

    print("\n== 本项目调用链（按出现顺序）==")
    for m in _FRAME.finditer(text):
        f = m.group(1)
        if "\\科创比赛项目\\" in f or "/科创比赛项目/" in f:
            rel = f.split("科创比赛项目")[-1].lstrip("\\/")
            print(f" {rel}:{m.group(2)}  {m.group(3)}")
            body = (m.group(4) or "").strip()[:160]
            if body:
                print(f"     {body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
