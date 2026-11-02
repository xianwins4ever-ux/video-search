# -*- coding: utf-8 -*-
"""探测5：首页→搜索框输入→回车（模拟真人路径）"""
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
        args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
    )
    ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                        "window.chrome=window.chrome||{runtime:{}};")
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.on("response", on_response)

    pg.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(6000)
    print("首页 ok, title:", pg.title())

    # 找搜索框
    cands = ["input[data-e2e='searchbar-input']", "input[placeholder*='搜索']", "#douyin-header input", "input"]
    ok = False
    for sel in cands:
        try:
            el = pg.query_selector(sel)
            if el and el.is_visible():
                print("命中搜索框选择器:", sel)
                el.click()
                pg.wait_for_timeout(600)
                el.type(KW, delay=120)
                pg.wait_for_timeout(600)
                pg.keyboard.press("Enter")
                ok = True
                break
        except Exception as e:
            print("  ", sel, "失败:", type(e).__name__)
    if not ok:
        print("!! 没找到搜索框，列出所有 input：")
        for i, el in enumerate(pg.query_selector_all("input")):
            print("   ", i, el.get_attribute("placeholder"), el.get_attribute("data-e2e"))

    pg.wait_for_timeout(12000)
    print("结果页 title:", pg.title(), "| URL:", pg.url)
    print("textlen:", len(pg.inner_text("body")))
    pg.screenshot(path=r"E:\Claude\2026-11-02_视频情报检索工具\_dy_search3.png", full_page=False)
    ctx.close()

print(f"\n=== 捕获 {len(hits)} 个列表 JSON ===")
for u, n, j in hits[:3]:
    print(f"[{u}] 条数={n}")
    for item in j["data"][:8]:
        aw = item.get("aweme_info") or item
        if isinstance(aw, dict):
            print("  -", (aw.get("desc") or "")[:50], "|", (aw.get("author") or {}).get("nickname", ""),
                  "| id=", aw.get("aweme_id"))
