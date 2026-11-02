# -*- coding: utf-8 -*-
"""探测6：真实浏览器(msedge)打开 YouTube，嗅探字幕接口 + 元信息"""
import json, sys
from playwright.sync_api import sync_playwright

VID = sys.argv[1] if len(sys.argv) > 1 else "DTu4yvmc0Fc"
PROFILE = r"E:\Claude\2026-11-02_视频情报检索工具\_yt_profile"
PROXY = "http://127.0.0.1:7897"

caps = []


def on_response(resp):
    u = resp.url
    if "timedtext" in u or "api/timedtext" in u:
        caps.append((u, resp.status))


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="msedge", headless=False,
        locale="zh-CN", viewport={"width": 1440, "height": 900},
        proxy={"server": PROXY},
        args=["--disable-blink-features=AutomationControlled"],
    )
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.on("response", on_response)
    try:
        pg.goto(f"https://www.youtube.com/watch?v={VID}", wait_until="domcontentloaded", timeout=60000)
    except Exception as e:
        print("goto warn:", type(e).__name__)
    pg.wait_for_timeout(9000)
    print("title:", pg.title())
    print("textlen:", len(pg.inner_text("body")))
    print("body前300:", repr(pg.inner_text("body")[:300]))
    # 从页面 ytInitialPlayerResponse 里直接取字幕轨
    try:
        info = pg.evaluate("""() => {
            const pr = window.ytInitialPlayerResponse;
            if (!pr) return {err: 'no ytInitialPlayerResponse'};
            const vd = pr.videoDetails || {};
            const tracks = (((pr.captions||{}).playerCaptionsTracklistRenderer||{}).captionTracks||[])
                .map(t => ({lang: t.languageCode, name: t.name && t.name.simpleText, url: t.baseUrl}));
            return {title: vd.title, author: vd.author, seconds: vd.lengthSeconds,
                    views: vd.viewCount, desc: (vd.shortDescription||'').slice(0,120), tracks};
        }""")
        print("\n=== ytInitialPlayerResponse ===")
        print(json.dumps(info, ensure_ascii=False)[:1200])
    except Exception as e:
        print("evaluate fail:", e)
    print("\n=== timedtext 响应 ===", len(caps))
    for u, s in caps[:3]:
        print("  ", s, u[:120])
    pg.screenshot(path=r"E:\Claude\2026-11-02_视频情报检索工具\_yt_check.png")
    ctx.close()
