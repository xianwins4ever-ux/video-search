# -*- coding: utf-8 -*-
"""探测3：抖音搜索页实际渲染成什么样 —— 截图 + DOM 元素清点"""
import sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
KW = sys.argv[1] if len(sys.argv) > 1 else "deepseek"
PROFILE = r"E:\Claude\2026-11-02_视频情报检索工具\_dy_profile"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False, user_agent=UA,
        locale="zh-CN", viewport={"width": 1440, "height": 900},
        args=["--disable-blink-features=AutomationControlled"],
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto(f"https://www.douyin.com/search/{KW}", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(10000)
    pg.screenshot(path=r"E:\Claude\2026-11-02_视频情报检索工具\_dy_search.png")
    # 清点 li / 链接 / 登录弹窗
    info = pg.evaluate("""() => {
        const r = {};
        r.li_count = document.querySelectorAll('li').length;
        r.a_douyin = [...document.querySelectorAll('a[href*="/video/"]')].length;
        r.text_len = document.body.innerText.length;
        r.has_login_dialog = !!document.querySelector('[data-e2e="login-dialog"], .login-dialog, [class*="login"]');
        r.title = document.title;
        r.body_snippet = document.body.innerText.slice(0, 200);
        return r;
    }""")
    print(info)
    ctx.close()
