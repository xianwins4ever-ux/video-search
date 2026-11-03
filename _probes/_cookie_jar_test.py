# -*- coding: utf-8 -*-
"""验证隐患：cookie 的 expires 字段过期后，CookieJar 是否还会发送？

如果会丢弃，那 7 天后即使 JSON 文件还在、服务端也认 180 天，
我们的程序自己先把 cookie 扔了 —— 这是个真 bug。
"""
import http.cookiejar
import json
import time
from pathlib import Path

COOKIE_DIR = Path.home() / ".video-research" / "cookies"
raw = json.load(open(COOKIE_DIR / "bili.json", encoding="utf-8"))
sess = next(c["value"] for c in raw if c["name"] == "SESSDATA")


def test(expires_offset_days: float, label: str) -> None:
    """构造一个指定过期时间的 cookie，看 jar 是否发送。"""
    exp = int(time.time()) + int(expires_offset_days * 86400)
    cj = http.cookiejar.CookieJar()
    cj.set_cookie(http.cookiejar.Cookie(
        version=0, name="SESSDATA", value=sess,
        port=None, port_specified=False,
        domain=".bilibili.com", domain_specified=True,
        domain_initial_dot=True,
        path="/", path_specified=True,
        secure=False, expires=exp,
        discard=False, comment=None, comment_url=None, rest={}))

    req = __import__("urllib.request").request.Request(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={"User-Agent": "Mozilla/5.0"})
    # 让 jar 处理
    cj.add_cookie_header(req)
    sent = req.get_header("Cookie") or ""
    has = "SESSDATA" in sent
    print(f"  {label:<28} expires={time.strftime('%Y-%m-%d', time.localtime(exp))} "
          f"-> 发送: {'✓ 是' if has else '✗ 否'}")
    return has


print("=== CookieJar 对过期 cookie 的处理 ===")
test(+7, "7天后过期")
test(+180, "180天后过期")
test(-1, "已过期1天")
test(-30, "已过期30天")
