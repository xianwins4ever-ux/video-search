# -*- coding: utf-8 -*-
"""CDP 实验 v3：原生 Edge + CDP，先关登录弹窗，再搜索。

为什么这条路最可能成：
- 浏览器是 subprocess 原生启动的，没有 Playwright 的自动化指纹
- Playwright 只通过 CDP 连上去发指令，不改浏览器特征
- MediaCrawler 就是用这套思路过的风控
"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

KW = sys.argv[1] if len(sys.argv) > 1 else "deepseek harness"
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
PROFILE = r"C:\Users\xianw\.video-research\profiles\douyin"
PORT = 9333
OUT = Path(r"E:\Claude\2026-11-02_视频情报检索工具\_cdp_result.json")

captured, nil_types = [], []


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def port_open(p):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", p)) == 0


def parse(txt):
    out = []
    for line in txt.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            j = json.loads(line)
        except Exception:
            continue
        ni = j.get("search_nil_info") or {}
        if ni.get("search_nil_type"):
            nil_types.append(ni["search_nil_type"])
        arr = j.get("data")
        if isinstance(arr, list):
            for it in arr:
                aw = it.get("aweme_info") or it
                if isinstance(aw, dict) and aw.get("aweme_id"):
                    st = aw.get("statistics") or {}
                    out.append({
                        "id": aw.get("aweme_id"),
                        "title": (aw.get("desc") or "")[:80],
                        "author": (aw.get("author") or {}).get("nickname"),
                        "digg": st.get("digg_count"),
                        "url": f"https://www.douyin.com/video/{aw.get('aweme_id')}",
                    })
    return out


def on_response(r):
    u = r.url
    if r.status != 200 or "search" not in u.lower():
        return
    if "general/search/stream" not in u and "search/item" not in u:
        return
    try:
        got = parse(r.text())
    except Exception:
        return
    if got:
        captured.extend(got)
        log(f"★ 捕获 {len(got)} 条（累计 {len(captured)}）")


edge = next((str(p) for p in map(Path, EDGE_CANDIDATES) if p.exists()), None)
if not edge:
    log("找不到 msedge.exe")
    sys.exit(1)

proc = subprocess.Popen(
    [edge, f"--remote-debugging-port={PORT}", f"--user-data-dir={PROFILE}",
     "--no-first-run", "--no-default-browser-check"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

for i in range(40):
    time.sleep(1)
    if port_open(PORT):
        log(f"CDP 端口就绪（{i+1}s）")
        break
else:
    log("端口未就绪")
    proc.terminate()
    sys.exit(1)

try:
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        ctx = br.contexts[0] if br.contexts else br.new_context()
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.on("response", on_response)

        log(f"登录态: {bool({c['name'] for c in ctx.cookies('https://www.douyin.com')} & {'sessionid','sessionid_ss'})}")

        log("打开首页…")
        pg.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=60000)
        for _ in range(10):
            pg.wait_for_timeout(2000)
            try:
                if "Loading" not in pg.title() and len(pg.inner_text("body")) > 100:
                    break
            except Exception:
                continue

        # 关掉登录弹窗（它就是刚才挡住搜索框的元凶）
        log("尝试关闭登录弹窗…")
        for sel in ["[id^='login-full-panel']", ".login-mask", "[class*='login-panel']"]:
            try:
                for el in pg.query_selector_all(sel):
                    box = el.bounding_box()
                    if box:
                        el.evaluate("e => e.remove()")
                        log(f"  已移除 {sel}")
            except Exception:
                pass
        try:
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(800)
        except Exception:
            pass

        # 直接跳搜索页（CDP 下指纹干净，值得一试）
        log(f"跳转搜索页: {KW}")
        pg.goto(f"https://www.douyin.com/search/{KW}",
                wait_until="domcontentloaded", timeout=60000)
        for i in range(12):
            pg.wait_for_timeout(3000)
            try:
                bl = len(pg.inner_text("body"))
            except Exception:
                bl = -1
            log(f"  [{i+1}/12] 捕获={len(captured)} bodylen={bl} title={pg.title()[:30]}")
            if len(captured) >= 5:
                break

        log(f"nil_types={set(nil_types)}")
        if captured:
            log(f"\n=== ✓ 成功 {len(captured)} 条 ===")
            seen = set()
            uniq = []
            for c in captured:
                if c["id"] in seen:
                    continue
                seen.add(c["id"])
                uniq.append(c)
                log(f"  {c['title']} | {c['author']} | 赞{c['digg']}")
            OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=2), encoding="utf-8")
            log(f"已存 {OUT}")
        else:
            log("\n✗ 无数据")
            try:
                log(f"body前200={pg.inner_text('body')[:200]!r}")
            except Exception:
                pass

        br.close()
except Exception as e:
    log(f"失败: {type(e).__name__}: {str(e)[:300]}")
finally:
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    log("已关闭")
