# -*- coding: utf-8 -*-
"""YouTube 登录页验证 v3：只保留一种 proxy 配置，避免参数冲突"""
import time

from playwright.sync_api import sync_playwright

PROFILE = r"C:\Users\xianw\.video-research\profiles\youtube"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, locale="zh-CN",
        viewport={"width": 1280, "height": 860},
        proxy={"server": "http://127.0.0.1:7897"},
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"],
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()

    print("打开 YouTube…", flush=True)
    ok = False
    for attempt in range(3):
        try:
            pg.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(3000)
            print(f"  ✓ 第{attempt+1}次成功 title={pg.title()}", flush=True)
            ok = True
            break
        except Exception as e:
            print(f"  第{attempt+1}次失败: {type(e).__name__}: {str(e)[:90]}", flush=True)
            time.sleep(3)

    if ok:
        body = pg.inner_text("body")
        print(f"  body前200={body[:200]!r}", flush=True)
        ck = {c["name"] for c in ctx.cookies()}
        print(f"  登录cookie: {sorted(ck & {'SID','SAPISID','__Secure-1PSID','LOGIN_INFO','HSID'}) or '无'}",
              flush=True)

    time.sleep(2)
    ctx.close()
    print("已关闭", flush=True)
