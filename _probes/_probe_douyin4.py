# -*- coding: utf-8 -*-
"""探测4：先串首页拿 cookie，再进搜索页；加强反检测"""
import sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
KW = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
PROFILE = r"E:\Claude\2026-11-02_视频情报检索工具\_dy_profile"

hits = []


def on_response(resp):
    u = resp.url
    if "search" in u and resp.status == 200 and "json" in (resp.headers.get("content-type") or ""):
        try:
            j = resp.json()
        except Exception:
            return
        arr = j.get("data") if isinstance(j, dict) else None
        if isinstance(arr, list) and arr:
            hits.append((u.split("?")[0], len(arr), j))


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, user_agent=UA,
        locale="zh-CN", viewport={"width": 1440, "height": 900},
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--no-first-run", "--no-default-browser-check",
        ],
    )
    ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = window.chrome || {runtime: {}};
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN','zh']});
    """)
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.on("response", on_response)

    print("1) 打开首页…")
    pg.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(6000)
    print("   首页 title:", pg.title(), "| len:", len(pg.inner_text("body")))

    print("2) 进搜索页…")
    pg.goto(f"https://www.douyin.com/search/{KW}", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(12000)
    print("   title:", pg.title(), "| textlen:", len(pg.inner_text("body")))
    pg.screenshot(path=r"E:\Claude\2026-11-02_视频情报检索工具\_dy_search2.png")
    ctx.close()

print(f"\n=== 捕获 {len(hits)} 个列表 JSON ===")
for u, n, j in hits[:3]:
    print(f"[{u}] 条数={n}")
    for item in j["data"][:6]:
        aw = item.get("aweme_info") or item
        if isinstance(aw, dict):
            print("  -", (aw.get("desc") or "")[:50], "|", (aw.get("author") or {}).get("nickname", ""))
