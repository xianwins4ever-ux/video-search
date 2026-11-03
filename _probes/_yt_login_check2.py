# -*- coding: utf-8 -*-
"""验证 YouTube 登录页（修正代理：Playwright 的 proxy 参数对 https 要显式配）"""
import time

from playwright.sync_api import sync_playwright

PROFILE = r"C:\Users\xianw\.video-research\profiles\youtube"
PROXY = {"server": "http://127.0.0.1:7897"}

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, locale="zh-CN",
        viewport={"width": 1280, "height": 860},
        proxy=PROXY,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check",
              # 有些代理需要显式忽略证书/走系统解析
              "--proxy-server=http://127.0.0.1:7897"],
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()

    for url in ["https://www.youtube.com/", "https://accounts.google.com/"]:
        print(f"\n打开 {url} …", flush=True)
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(3500)
            body = pg.inner_text("body")
            print(f"  ✓ title={pg.title()}", flush=True)
            print(f"  body前150={body[:150]!r}", flush=True)
        except Exception as e:
            print(f"  ✗ {type(e).__name__}: {str(e)[:150]}", flush=True)

    ck = {c["name"] for c in ctx.cookies()}
    print(f"\nYouTube 登录 cookie: {sorted(ck & {'SID','SAPISID','__Secure-1PSID','LOGIN_INFO','HSID'}) or '无'}",
          flush=True)
    time.sleep(2)
    ctx.close()
    print("已关闭", flush=True)
