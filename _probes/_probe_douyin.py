# -*- coding: utf-8 -*-
"""探测：抖音搜索页能否通过浏览器嗅探拿到视频列表（只读，不下载）"""
import json, sys, time
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
KW = sys.argv[1] if len(sys.argv) > 1 else "deepseek"

hits = []


def on_response(resp):
    u = resp.url
    if "search" in u and resp.status == 200:
        ct = (resp.headers.get("content-type") or "")
        if "json" in ct:
            try:
                j = resp.json()
            except Exception:
                return
            n = 0
            for key in ("data", "aweme_list"):
                arr = j.get(key) if isinstance(j, dict) else None
                if isinstance(arr, list):
                    n = max(n, len(arr))
            if n:
                hits.append((u.split("?")[0], n, j))


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge", headless=True)
    ctx = b.new_context(user_agent=UA, locale="zh-CN", viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.on("response", on_response)
    try:
        pg.goto(f"https://www.douyin.com/search/{KW}", wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        print("goto warn:", type(e).__name__)
    pg.wait_for_timeout(9000)
    # 页面文本兜底
    txt = ""
    try:
        txt = pg.inner_text("body")[:400]
    except Exception:
        pass
    print("最终URL:", pg.url)
    print("页面文本前400:", repr(txt[:400]))
    b.close()

print(f"\n=== 捕获到 {len(hits)} 个带列表的 JSON ===")
for u, n, j in hits[:3]:
    print(f"\n[{u}] 条数={n}")
    d = j.get("data") or j.get("aweme_list") or []
    for item in d[:5]:
        aw = item.get("aweme_info") or item
        if not isinstance(aw, dict):
            continue
        desc = (aw.get("desc") or "")[:45]
        au = (aw.get("author") or {}).get("nickname", "")
        st = aw.get("statistics") or {}
        print(f"  - {desc} | {au} | 赞{st.get('digg_count')} | id={aw.get('aweme_id')}")
