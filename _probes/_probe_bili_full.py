# -*- coding: utf-8 -*-
"""B站能力全链路验证：搜索 → 详情 → 字幕（免登录 / 带浏览器cookie）"""
import hashlib, json, time, urllib.parse, urllib.request, http.cookiejar, sys

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,
         37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]

cj = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
op.addheaders = [("User-Agent", UA), ("Referer", "https://www.bilibili.com/")]


def api(url, raw=False):
    with op.open(url, timeout=20) as r:
        data = r.read()
        return data if raw else json.loads(data.decode("utf-8"))


print("1) 初始化 cookie + wbi key")
op.open("https://www.bilibili.com/", timeout=20).read()
nav = api("https://api.bilibili.com/x/web-interface/nav")
wbi = nav["data"]["wbi_img"]
img = wbi["img_url"].rsplit("/", 1)[-1].split(".")[0]
sub = wbi["sub_url"].rsplit("/", 1)[-1].split(".")[0]
mixin = "".join([(img + sub)[i] for i in MIXIN])[:32]
print("   nav code:", nav["code"], "| 登录:", nav["data"].get("isLogin"))


def signed(path, params):
    p = dict(params, wts=str(round(time.time())))
    p = dict(sorted(p.items()))
    p = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in p.items()}
    q = urllib.parse.urlencode(p)
    p["w_rid"] = hashlib.md5((q + mixin).encode()).hexdigest()
    return f"https://api.bilibili.com{path}?" + urllib.parse.urlencode(p)


print("\n2) 搜索")
res = api(signed("/x/web-interface/wbi/search/type",
                 {"search_type": "video", "keyword": sys.argv[1] if len(sys.argv) > 1 else "deepseek", "page": "1"}))
print("   search resp:", json.dumps(res, ensure_ascii=False)[:300])
vids = (res.get("data") or {}).get("result") or []
print(f"   命中 {len(vids)} 条")
pick = None
for v in vids[:8]:
    t = v["title"].replace('<em class="keyword">', "").replace("</em>", "")
    print(f"   - {t[:45]} | {v['author']} | 播放{v['play']} | {v['bvid']}")
if vids:
    pick = vids[0]["bvid"]

print("\n3) 详情（含分P/字幕列表）")
vinfo = api(signed("/x/web-interface/wbi/view", {"bvid": pick}))["data"]
print("   标题:", vinfo["title"][:50])
print("   时长:", vinfo["duration"], "秒 | cid:", vinfo["cid"])
print("   简介前80:", vinfo["desc"][:80].replace("\n", " "))

print("\n4) 字幕接口（player/wbi/v2）")
pl = api(signed("/x/player/wbi/v2", {"bvid": pick, "cid": vinfo["cid"]}))
print("   code:", pl["code"])
subs = (pl.get("data") or {}).get("subtitle") or {}
slist = subs.get("subtitles") or []
print("   字幕轨数量:", len(slist), "| 需登录:", subs.get("allow_submit") is not None)
for s in slist:
    print("   -", s.get("lan"), s.get("lan_doc"), "|", s.get("subtitle_url")[:80])

if slist:
    u = slist[0]["subtitle_url"]
    if u.startswith("//"):
        u = "https:" + u
    body = json.loads(api(u, raw=True).decode("utf-8"))
    lines = body.get("body") or []
    print(f"   字幕行数: {len(lines)}")
    for ln in lines[:3]:
        print("     ", round(ln["from"], 1), "s |", ln["content"][:50])
else:
    print("   !! 免登录拿不到字幕（B站AI字幕需登录态）")
