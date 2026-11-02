# -*- coding: utf-8 -*-
"""探测2：headed + 持久化用户目录（复用登录态）能否拿到抖音搜索列表"""
import json, sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
KW = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
PROFILE = r"E:\Claude\2026-11-02_视频情报检索工具\_dy_profile"

hits = []


def on_response(resp):
    u = resp.url
    if ("search" in u or "aweme" in u) and resp.status == 200:
        if "json" in (resp.headers.get("content-type") or ""):
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
        args=["--disable-blink-features=AutomationControlled"],
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.on("response", on_response)
    try:
        pg.goto(f"https://www.douyin.com/search/{KW}", wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print("goto warn:", type(e).__name__)
    pg.wait_for_timeout(12000)
    body = ""
    try:
        body = pg.inner_text("body")
    except Exception:
        pass
    print("URL:", pg.url)
    print("页面长度:", len(body))
    print("前300字:", repr(body[:300]))
    ctx.close()

print(f"\n=== 捕获 {len(hits)} 个列表 JSON ===")
for u, n, j in hits[:4]:
    print(f"\n[{u}] 条数={n}")
    for item in j["data"][:6]:
        aw = item.get("aweme_info") or item
        if not isinstance(aw, dict):
            continue
        print("  -", (aw.get("desc") or "")[:50], "|", (aw.get("author") or {}).get("nickname", ""),
              "| id=", aw.get("aweme_id"))
