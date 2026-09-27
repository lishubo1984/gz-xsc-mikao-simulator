# -*- coding: utf-8 -*-
"""端到端验证：真实 HTTP 打一遍完整流程（生成 → 答题 → 交卷 → 报告 → 答案页）。

最有价值的一条断言是第 4 步：把标准答案原样提交，必须正好得 100 分。
这条断言同时证明了三件事是一致的：
    Web 渲染出的题干 ←→ 数据库存的答案 ←→ 判分器的比对结果
任何一环错位（比如选项文本与答案文本不一致），这里必然炸，而不是等到孩子考试才发现。

服务由本脚本自己拉起 —— 曾经因为依赖"上一次对话手工起的 uvicorn"，
进程在轮次之间被回收，报错却是 httpx.ReadError WinError 10054，
看起来像 /api/papers 有 bug，实际是服务根本没活着。自包含之后这个假故障不会再出现。
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
BASE = ""
TIMEOUT = 60.0

ok_cnt = 0
fail: list[str] = []


def free_port() -> int:
    """动态挑一个空闲端口 —— 写死 8765 时一旦有残留进程，脚本会连到别人的服务上。"""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = int(s.getsockname()[1])
    s.close()
    return p


def wait_health(url: str, timeout: float = 60.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if httpx.get(url + "/api/health", timeout=2.0,
                         trust_env=False).status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def start_server(port: int):
    log = ROOT / "exports" / "uvicorn_e2e.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    f = open(log, "w", encoding="utf-8")
    # Windows 控制台默认 GBK，子进程写中文会直接 UnicodeEncodeError 崩掉，必须显式指定
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1",
           "NO_PROXY": "127.0.0.1,localhost", "no_proxy": "127.0.0.1,localhost"}
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=f, stderr=subprocess.STDOUT,
    )
    if not wait_health(f"http://127.0.0.1:{port}"):
        proc.kill()
        f.close()
        print("服务启动失败，日志：")
        print(log.read_text(encoding="utf-8", errors="replace")[-3000:])
        return None, None
    return proc, f


def check(name: str, cond: bool, extra: str = "") -> None:
    global ok_cnt
    if cond:
        ok_cnt += 1
        print(f"  ✓ {name}")
    else:
        fail.append(f"{name} {extra}")
        print(f"  ✗ {name}  {extra}")


def main() -> int:
    global BASE
    port = free_port()
    BASE = f"http://127.0.0.1:{port}"
    print(f"0) 拉起服务 {BASE}")
    proc, logf = start_server(port)
    if proc is None:
        return 1

    c = httpx.Client(base_url=BASE, timeout=TIMEOUT,
                     # trust_env=False 是必须的：本机环境设了 HTTP_PROXY=127.0.0.1:15585，
                     # httpx 默认会照着走，于是连 127.0.0.1 自己的服务都被送去代理，
                     # 表现为随机 404，重 POST 还会被代理掐断报 WinError 10054。
                     trust_env=False)
    try:
        return _run(c)
    finally:
        c.close()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        if logf:
            logf.close()


def _run(c: httpx.Client) -> int:
    global ok_cnt

    print("1) 首页")
    r = c.get("/")
    check("首页 200", r.status_code == 200, f"status={r.status_code}")
    check("首页含标题", "广州小升初密考模拟系统" in r.text)

    print("2) 生成试卷")
    r = c.post("/api/papers", json={"student": "李同学", "seed": 20260927})
    if r.status_code != 200:
        print("   生成失败：", r.status_code, r.text[:400])
        return 1
    gen = r.json()
    paper_id, attempt_id = gen["paper_id"], gen["attempt_id"]
    check("返回 paper_id", bool(paper_id))
    check("体检通过", gen["check_passed"] is True)
    check("题量 38", gen["question_count"] == 38, f"实际 {gen['question_count']}")
    check("总分 100", gen["total_score"] == 100)
    print(f"   出卷耗时 {gen['elapsed_ms']} ms")

    print("3) 答题页")
    r = c.get(f"/paper/{attempt_id}")
    check("答题页 200", r.status_code == 200, f"status={r.status_code}")
    check("含七大题型标题", all(t in r.text for t in
          ["一、填空题", "二、选择题", "三、判断题", "四、计算题",
           "五、图形与几何", "六、解决问题", "七、附加题"]))
    check("含倒计时元素", 'id="clock"' in r.text)
    check("无未渲染占位符残留", "{{" not in r.text and "}{" not in r.text)

    # 取每题标准答案，用于构造"全对"提交
    r = c.get(f"/api/papers/{paper_id}/answers")
    answers_api = r.json()["items"]
    items = c.get(f"/api/papers/{paper_id}").json()["items"]
    id_by_seq = {it["seq"]: it["id"] for it in items}

    print("4) 全对交卷 → 必须满分")
    payload = {"answers": {}, "scratch": {}, "remaining_sec": 3000}
    for row in answers_api:
        payload["answers"][str(id_by_seq[row["seq"]])] = row["answer"]
    r = c.post(f"/api/attempts/{attempt_id}/submit", json=payload)
    check("提交 200", r.status_code == 200, r.text[:300])
    rep = r.json()["report"]
    check("得分 = 100", rep["got"] == 100, f"实际 {rep['got']} / {rep['total']}")
    check("无错题", len(rep["wrong_details"]) == 0,
          f"错题 {[d['seq'] for d in rep['wrong_details']][:10]}")
    check("无漏答", rep["unanswered"] == 0)

    print("5) 报告页")
    r = c.get(f"/report/{attempt_id}")
    check("报告页 200", r.status_code == 200, f"status={r.status_code}")
    check("显示得分", ">100<" in r.text.replace(" ", "") or "100" in r.text)

    print("6) 答案页")
    r = c.get(f"/answers/{paper_id}")
    check("答案页 200", r.status_code == 200, f"status={r.status_code}")
    check("含解题思路", "解题思路" in r.text)

    print("7) 全错交卷 → 必须 0 分，且错题数 = 38")
    r = c.post("/api/papers", json={"student": "李同学", "seed": 20260928})
    a2 = r.json()["attempt_id"]
    p2 = r.json()["paper_id"]
    answers_api2 = c.get(f"/api/papers/{p2}/answers").json()["items"]
    items2 = c.get(f"/api/papers/{p2}").json()["items"]
    id2 = {it["seq"]: it["id"] for it in items2}
    wrong_ans = {str(id2[row["seq"]]): "故意写错" for row in answers_api2}
    r = c.post(f"/api/attempts/{a2}/submit", json={"answers": wrong_ans, "remaining_sec": 0})
    rep2 = r.json()["report"]
    check("得分 = 0", rep2["got"] == 0, f"实际 {rep2['got']}")
    check("错题数 = 38", len(rep2["wrong_details"]) == 38, f"实际 {len(rep2['wrong_details'])}")
    check("产出薄弱知识点", len(rep2["weak_points"]) > 0)
    if rep2["weak_points"]:
        print("   薄弱点 Top3：", [(w["name"], w["hits"]) for w in rep2["weak_points"][:3]])

    print("8) 半对半错 → 分数须落在中间", )
    r = c.post("/api/papers", json={"student": "李四", "seed": 20260929})
    a3, p3 = r.json()["attempt_id"], r.json()["paper_id"]
    ans3 = c.get(f"/api/papers/{p3}/answers").json()["items"]
    it3 = c.get(f"/api/papers/{p3}").json()["items"]
    id3 = {it["seq"]: it["id"] for it in it3}
    score3 = {it["seq"]: it["score"] for it in it3}
    answers3, expect = {}, 0
    for i, row in enumerate(ans3):
        sid = str(id3[row["seq"]])
        if i % 2 == 0:
            answers3[sid] = row["answer"]
            expect += score3[row["seq"]]
        else:
            answers3[sid] = "9"
    r = c.post(f"/api/attempts/{a3}/submit", json={"answers": answers3, "remaining_sec": 2000})
    rep3 = r.json()["report"]
    check("得分与预期一致", rep3["got"] == expect, f"实得 {rep3['got']} 预期 {expect}")

    print()
    print("=" * 62)
    print(f"通过 {ok_cnt} 项，失败 {len(fail)} 项")
    for f in fail:
        print("  FAIL:", f)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
