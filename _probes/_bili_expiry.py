# -*- coding: utf-8 -*-
"""验证 B站登录有效期：SESSDATA 内嵌时间戳 vs cookie expires，服务端认哪个？"""
import sys
import time
import urllib.request

sys.path.insert(0, r"D:\tools\vsearch")
from vsearch import Bilibili, http_json

b = Bilibili(None)
b._init()

print("=== 1) 当前登录态 ===")
nav = http_json(b.op, "https://api.bilibili.com/x/web-interface/nav")
d = nav.get("data") or {}
print("isLogin:", d.get("isLogin"))
print("uname:", d.get("uname"))
print("mid:", d.get("mid"))

print("\n=== 2) 请求时服务端是否下发新 cookie（续期）===")
req = urllib.request.Request(
    "https://api.bilibili.com/x/web-interface/nav",
    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
with b.op.open(req) as r:
    found = False
    for k, v in r.headers.items():
        if k.lower() == "set-cookie":
            found = True
            print("  Set-Cookie:", v[:150])
    if not found:
        print("  （无 Set-Cookie，服务端未主动续期）")

print("\n=== 3) 用旧 SESSDATA 直连（模拟 cookie 过期后仍用旧值）===")
# 直接从 json 读，绕过 jar 的过期判断
import json
from pathlib import Path
p = Path.home() / ".video-research" / "cookies" / "bili.json"
raw = json.load(open(p, encoding="utf-8"))
sess = next((c["value"] for c in raw if c["name"] == "SESSDATA"), "")
if sess:
    req2 = urllib.request.Request(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={"User-Agent": "Mozilla/5.0",
                 "Referer": "https://www.bilibili.com/",
                 "Cookie": f"SESSDATA={sess}"})
    with urllib.request.urlopen(req2, timeout=20) as r:
        j = json.loads(r.read().decode())
        dd = j.get("data") or {}
        print("  仅用 SESSDATA 直接请求:")
        print("    isLogin:", dd.get("isLogin"))
        print("    uname:", dd.get("uname"))

print("\n=== 4) SESSDATA 内嵌时间戳 ===")
import urllib.parse
dec = urllib.parse.unquote(sess)
parts = dec.split(",")
if len(parts) >= 2:
    ts = int(parts[1])
    left = (ts - time.time()) / 86400
    print(f"  内嵌过期: {time.strftime('%Y-%m-%d %H:%M', time.localtime(ts))}")
    print(f"  剩余: {left:.1f} 天")
print(f"  cookie expires 字段: 7.0 天（浏览器侧）")
