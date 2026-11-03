# -*- coding: utf-8 -*-
"""验证：能否用独立 profile 打开 YouTube 登录页（Google 对自动化浏览器有额外风控）"""
import time

from playwright.sync_api import sync_playwright

PROFILE = r"C:\Users\xianw\.video-research\profiles\youtube"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, locale="zh-CN",
        viewport={"width": 1280, "height": 860},
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"],
        proxy={"server": "http://127.0.0.1:7897"},
    )
    ctx.add_init_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        "window.chrome = window.chrome || {runtime:{}};"
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()

    print("1) 打开 YouTube…", flush=True)
    pg.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)
    print(f"   title={pg.title()}", flush=True)

    print("2) 检查现有登录态…", flush=True)
    ck = {c["name"] for c in ctx.cookies()}
    yt_login = ck & {"SID", "SAPISID", "__Secure-1PSID", "LOGIN_INFO", "HSID"}
    print(f"   YouTube 登录 cookie: {sorted(yt_login) or '无'}", flush=True)

    print("3) 直接打开登录页看是否被拦…", flush=True)
    pg.goto("https://accounts.google.com/ServiceLogin?service=youtube",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(4000)
    body = pg.inner_text("body")
    print(f"   title={pg.title()}", flush=True)
    print(f"   body 前300={body[:300]!r}", flush=True)

    blocked = any(k in body for k in ("不安全", "not secure", "无法登录",
                                      "couldn't sign you in", "此浏览器"))
    print(f"   被拦: {blocked}", flush=True)

    time.sleep(3)
    ctx.close()
    print("已关闭", flush=True)
