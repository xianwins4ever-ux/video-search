# -*- coding: utf-8 -*-
"""探测7：抖音首页推荐流能否拿到视频链接（搜索被拦，但首页可用）"""
import re, sys
from playwright.sync_api import sync_playwright

PROFILE = r"C:\Users\xianw\.video-research\profiles\douyin"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, locale="zh-CN",
        viewport={"width": 1440, "height": 900},
        args=["--disable-blink-features=AutomationControlled", "--no-first-run"])
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(9000)
    print("title:", pg.title(), "| textlen:", len(pg.inner_text("body")))
    links = pg.eval_on_selector_all(
        'a[href*="/video/"]',
        "els => els.map(e => ({href: e.href, text: (e.innerText||'').slice(0,40)}))")
    print(f"找到 {len(links)} 个视频链接")
    for l in links[:8]:
        print("  ", l["href"], "|", l["text"])
    if not links:
        html = pg.content()
        ids = re.findall(r'/video/(\d{15,})', html)
        print("从 HTML 正则找到 ID:", list(dict.fromkeys(ids))[:5])
    pg.screenshot(path=r"E:\Claude\2026-11-02_视频情报检索工具\_dy_home.png")
    ctx.close()
