#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""vsearch —— 视频情报检索：跨平台搜索 → 元信息 → 转文案 → 供 agent 总结。

设计原则
--------
1. **搜索层免登录**：B站走 wbi 签名、YouTube 走 yt-dlp ytsearch，都不需要账号。
2. **登录态只用于字幕**：B站 AI 字幕、YouTube 字幕需要登录态；用持久化 profile
   让用户手动登录一次，之后长期复用，不碰系统浏览器、不读 cookie 数据库。
3. **不逆向签名**：抖音搜索需要 a_bogus + 登录，本工具通过持久化 profile 走真浏览器。
4. **转文案复用 v2t**：D:\\tools\\v2t（字幕优先，本地 ASR 兜底），不重复造轮子。

子命令
------
    vsearch bili  <关键词> [--limit N] [--sort play|new] [--json]
    vsearch yt    <关键词> [--limit N] [--json]
    vsearch dy    <关键词> [--limit N] [--json]
    vsearch all   <关键词> [--limit N] [--json]        # 三平台并发
    vsearch info  <url|bvid> [--json]
    vsearch grab  <url> [--outdir DIR] [--model large-v3]   # 转文案（调 v2t）
    vsearch login <bili|yt|dy>                          # 打开浏览器手动登录一次
    vsearch doctor                                      # 环境自检
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

# ---------------------------------------------------------------- 路径与常量

HOME = Path.home()
CFG_DIR = HOME / ".video-research"
PROF_DIR = CFG_DIR / "profiles"
CACHE_DIR = CFG_DIR / "cache"
for _d in (CFG_DIR, PROF_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

V2T_DIR = Path(r"D:\tools\v2t")
V2T_CMD = V2T_DIR / "v2t.cmd"
V2T_PYLIB = V2T_DIR / "pylib"
FFMPEG_DIR = Path(r"D:\hyperframes-tools\ffmpeg")

UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")

# B站 wbi 混淆表
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


# ---------------------------------------------------------------- 配置

def load_config() -> dict:
    """读取 ~/.video-research/config.json，缺省自动探测系统代理。"""
    cfg_path = CFG_DIR / "config.json"
    cfg = {"proxy": None, "ytdlp_proxy": None, "v2t_model": "large-v3"}
    if cfg_path.exists():
        try:
            cfg.update(json.loads(cfg_path.read_text(encoding="utf-8")))
        except Exception:
            pass
    if not cfg.get("proxy"):
        cfg["proxy"] = detect_system_proxy()
    if not cfg.get("ytdlp_proxy"):
        cfg["ytdlp_proxy"] = cfg.get("proxy")
    return cfg


def detect_system_proxy() -> str | None:
    """从 Windows 注册表读系统代理：127.0.0.1:7897 -> http://127.0.0.1:7897"""
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled = winreg.QueryValueEx(k, "ProxyEnable")[0]
        if not enabled:
            return None
        server = winreg.QueryValueEx(k, "ProxyServer")[0]
        if not server:
            return None
        if "=" in server:  # 形如 http=127.0.0.1:7897;https=...
            for part in server.split(";"):
                if part.startswith("http="):
                    server = part.split("=", 1)[1]
                    break
        return server if "://" in server else f"http://{server}"
    except Exception:
        return None


# ---------------------------------------------------------------- HTTP 工具

def make_opener(referer: str = "https://www.bilibili.com/") -> urllib.request.OpenerDirector:
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA_DESKTOP), ("Referer", referer)]
    return op


def http_json(op, url: str, timeout: int = 20):
    with op.open(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def http_text(op, url: str, timeout: int = 20) -> str:
    with op.open(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ---------------------------------------------------------------- 登录态与 cookie

COOKIE_DIR = CFG_DIR / "cookies"
COOKIE_DIR.mkdir(parents=True, exist_ok=True)

SITE_META = {
    "bili": {"url": "https://www.bilibili.com/", "profile": PROF_DIR / "bilibili",
             "domain_hint": "bilibili.com",
             "login_cookies": ("SESSDATA", "bili_jct")},
    "yt": {"url": "https://www.youtube.com/", "profile": PROF_DIR / "youtube",
           "domain_hint": "youtube.com",
           "login_cookies": ("SID", "SAPISID", "__Secure-1PSID", "LOGIN_INFO")},
    "dy": {"url": "https://www.douyin.com/", "profile": PROF_DIR / "douyin",
           "domain_hint": "douyin.com",
           "login_cookies": ("sessionid", "sid_tt", "sessionid_ss", "passport_csrf_token")},
}


def to_netscape(cookies: list[dict], path: Path) -> None:
    """把 playwright cookies 转成 yt-dlp / v2t 可用的 cookies.txt。"""
    lines = ["# Netscape HTTP Cookie File", "# generated by vsearch", ""]
    for c in cookies:
        dom = c.get("domain", "")
        flag = "TRUE" if dom.startswith(".") else "FALSE"
        expires = int(c.get("expires") or 0)
        if expires <= 0:
            expires = int(time.time()) + 86400 * 365
        lines.append("\t".join([
            dom, flag, c.get("path", "/"),
            "TRUE" if c.get("secure") else "FALSE",
            str(expires), c.get("name", ""), c.get("value", ""),
        ]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def to_polylens_cookie(cookies: list[dict]) -> Path:
    """写 polylens-bilibili-mcp 的 cookie 文件（纯 Cookie header 文本）。

    polylens 读 ~/.cache/polylens-bilibili/cookie，内容是 'SESSDATA=x; bili_jct=y'。
    共用这一份，用户只需在浏览器里登录一次，两边都能用。
    """
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    d = cache / "polylens-bilibili"
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except Exception:
        pass
    pairs = [f"{c['name']}={c['value']}" for c in cookies
             if c.get("name") and c.get("domain", "").endswith("bilibili.com")]
    p = d / "cookie"
    p.write_text("; ".join(pairs), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    return p


def load_cookie_jar(site: str) -> http.cookiejar.CookieJar | None:
    """从本地 cookies.json 构造 cookiejar，供 B站 API 用。"""
    p = COOKIE_DIR / f"{site}.json"
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    cj = http.cookiejar.CookieJar()
    for c in raw:
        cj.set_cookie(http.cookiejar.Cookie(
            version=0, name=c.get("name", ""), value=c.get("value", ""),
            port=None, port_specified=False,
            domain=c.get("domain", ""), domain_specified=bool(c.get("domain")),
            domain_initial_dot=str(c.get("domain", "")).startswith("."),
            path=c.get("path", "/"), path_specified=True,
            secure=bool(c.get("secure")), expires=int(c.get("expires") or 0) or None,
            discard=False, comment=None, comment_url=None, rest={},
        ))
    return cj


# ---------------------------------------------------------------- Bilibili

class Bilibili:
    """B站搜索/详情/字幕。搜索免登录，字幕需登录态。"""

    def __init__(self, proxy: str | None = None):
        self.op = make_opener()
        jar = load_cookie_jar("bili")
        if jar is not None:
            # 用已登录 cookie 重建 opener
            self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
            self.op.addheaders = [("User-Agent", UA_DESKTOP),
                                  ("Referer", "https://www.bilibili.com/")]
        self.proxy = proxy
        self._mixin_key: str | None = None

    def _init(self):
        if self._mixin_key:
            return
        try:
            self.op.open("https://www.bilibili.com/", timeout=20).read()
        except Exception:
            pass
        nav = http_json(self.op, "https://api.bilibili.com/x/web-interface/nav")
        wbi = (nav.get("data") or {}).get("wbi_img") or {}
        img = (wbi.get("img_url") or "").rsplit("/", 1)[-1].split(".")[0]
        sub = (wbi.get("sub_url") or "").rsplit("/", 1)[-1].split(".")[0]
        if not img or not sub:
            raise RuntimeError("B站 wbi key 获取失败（接口异常或网络不通）")
        raw = img + sub
        self._mixin_key = "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        self._logged_in = bool((nav.get("data") or {}).get("isLogin"))

    def _signed(self, path: str, params: dict) -> str:
        self._init()
        p = dict(params, wts=str(round(time.time())))
        p = dict(sorted(p.items()))
        p = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in p.items()}
        q = urllib.parse.urlencode(p)
        p["w_rid"] = hashlib.md5((q + self._mixin_key).encode()).hexdigest()
        return f"https://api.bilibili.com{path}?" + urllib.parse.urlencode(p)

    @staticmethod
    def _clean(s: str) -> str:
        return re.sub(r"<[^>]+>", "", s or "").replace("&quot;", '"').replace("&amp;", "&")

    def search(self, keyword: str, limit: int = 20, sort: str = "totalrank",
               retries: int = 3) -> list[dict]:
        """sort: totalrank(综合) / click(播放) / pubdate(最新)

        B站对并发/高频请求会返回空 result（code 仍为 0），必须退避重试；
        否则三平台并发时 B站会静默返回 0 条。
        """
        out: list[dict] = []
        page = 1
        empty_streak = 0

        def fetch(p: int) -> list[dict]:
            url = self._signed("/x/web-interface/wbi/search/type", {
                "search_type": "video", "keyword": keyword,
                "page": str(p), "order": sort,
            })
            for attempt in range(retries):
                try:
                    res = http_json(self.op, url)
                except Exception as e:
                    if attempt == retries - 1:
                        raise RuntimeError(f"B站搜索失败: {e}") from e
                    time.sleep(1.2 * (attempt + 1))
                    continue
                items = (res.get("data") or {}).get("result") or []
                if items:
                    return items
                time.sleep(1.5 * (attempt + 1))   # 空结果多半是限流
                url = self._signed("/x/web-interface/wbi/search/type", {
                    "search_type": "video", "keyword": keyword,
                    "page": str(p), "order": sort,
                })
            return []

        while len(out) < limit and page <= 10:
            items = fetch(page)
            if not items:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                page += 1
                continue
            empty_streak = 0
            for v in items:
                out.append({
                    "platform": "bilibili",
                    "id": v.get("bvid"),
                    "title": self._clean(v.get("title")),
                    "author": v.get("author"),
                    "play": v.get("play"),
                    "danmaku": v.get("video_review"),
                    "duration": v.get("duration"),
                    "pubdate": v.get("pubdate"),
                    "url": f"https://www.bilibili.com/video/{v.get('bvid')}",
                    "desc": self._clean(v.get("description"))[:160],
                })
            page += 1
        return out[:limit]

    def info(self, bvid: str) -> dict:
        d = http_json(self.op, self._signed("/x/web-interface/wbi/view", {"bvid": bvid}))["data"]
        return {
            "platform": "bilibili", "id": bvid, "title": self._clean(d.get("title")),
            "author": (d.get("owner") or {}).get("name"),
            "duration": d.get("duration"), "pubdate": d.get("pubdate"),
            "desc": self._clean(d.get("desc"))[:300],
            "play": (d.get("stat") or {}).get("view"),
            "like": (d.get("stat") or {}).get("like"),
            "cid": d.get("cid"), "pages": len(d.get("pages") or []),
            "url": f"https://www.bilibili.com/video/{bvid}",
        }

    def subtitles(self, bvid: str) -> dict:
        """返回 {requires_login, tracks:[{lan,lan_doc,url}]}"""
        info = http_json(self.op, self._signed("/x/web-interface/wbi/view", {"bvid": bvid}))["data"]
        cid = info.get("cid")
        pl = http_json(self.op, self._signed("/x/player/wbi/v2", {"bvid": bvid, "cid": cid}))
        subs = ((pl.get("data") or {}).get("subtitle") or {})
        tracks = subs.get("subtitles") or []
        return {
            "requires_login": len(tracks) == 0,
            "tracks": [{"lan": t.get("lan"), "lan_doc": t.get("lan_doc"),
                        "url": ("https:" + t["subtitle_url"]) if t.get("subtitle_url", "").startswith("//")
                        else t.get("subtitle_url")}
                       for t in tracks],
        }

    def subtitle_text(self, url: str) -> list[dict]:
        body = json.loads(http_text(self.op, url))
        return [{"from": ln.get("from"), "to": ln.get("to"), "content": ln.get("content")}
                for ln in (body.get("body") or [])]


# ---------------------------------------------------------------- YouTube

class YouTube:
    """YouTube 搜索/详情。搜索用 yt-dlp ytsearch（免登录），字幕需登录态。"""

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    def _ytdlp(self, args: list[str], timeout: int = 90) -> str:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(V2T_PYLIB)
        env["PYTHONIOENCODING"] = "utf-8"
        cmd = [sys.executable, "-m", "yt_dlp", *args]
        if self.proxy:
            cmd += ["--proxy", self.proxy]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env=env, encoding="utf-8", errors="replace")
        if r.returncode != 0 and not r.stdout.strip():
            raise RuntimeError(f"yt-dlp 失败: {(r.stderr or '')[-400:]}")
        return r.stdout

    def search(self, keyword: str, limit: int = 20) -> list[dict]:
        txt = self._ytdlp([f"ytsearch{limit}:{keyword}", "--flat-playlist",
                           "--dump-json", "--skip-download", "--no-warnings"])
        out = []
        for line in txt.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            d = json.loads(line)
            vid = d.get("id")
            out.append({
                "platform": "youtube", "id": vid,
                "title": d.get("title"),
                "author": d.get("channel") or d.get("uploader"),
                "play": d.get("view_count"),
                "duration": d.get("duration"),
                "pubdate": d.get("timestamp"),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "desc": (d.get("description") or "")[:160],
            })
        return out[:limit]

    def info(self, vid: str) -> dict:
        txt = self._ytdlp([f"https://www.youtube.com/watch?v={vid}", "--dump-json",
                           "--skip-download", "--no-warnings"])
        d = json.loads(txt.splitlines()[0])
        return {
            "platform": "youtube", "id": vid, "title": d.get("title"),
            "author": d.get("channel") or d.get("uploader"),
            "duration": d.get("duration"), "pubdate": d.get("timestamp"),
            "desc": (d.get("description") or "")[:300],
            "play": d.get("view_count"), "like": d.get("like_count"),
            "url": f"https://www.youtube.com/watch?v={vid}",
        }


# ---------------------------------------------------------------- 抖音

class Douyin:
    """抖音：搜索需要登录态 + 真浏览器（a_bogus 签名由浏览器自己算）。

    没有登录态时给出明确降级提示，不静默失败。
    """

    PROFILE = PROF_DIR / "douyin"

    def __init__(self, proxy: str | None = None):
        self.proxy = proxy

    def _has_login(self) -> bool:
        # 持久化 profile 里有 Cookie 文件即认为尝试过登录
        return (self.PROFILE / "Default").exists() or self.PROFILE.exists()

    def search(self, keyword: str, limit: int = 20, headed: bool = False) -> list[dict]:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise RuntimeError("未安装 playwright：pip install playwright && playwright install msedge")

        captured: list[dict] = []

        def on_response(resp):
            u = resp.url
            if resp.status != 200 or "json" not in (resp.headers.get("content-type") or ""):
                return
            if "search" not in u and "aweme" not in u:
                return
            try:
                j = resp.json()
            except Exception:
                return
            arr = j.get("data") if isinstance(j, dict) else None
            if not isinstance(arr, list):
                return
            for item in arr:
                aw = item.get("aweme_info") or item
                if not isinstance(aw, dict) or not aw.get("aweme_id"):
                    continue
                desc = (aw.get("desc") or "").strip()
                if not desc:
                    continue
                captured.append({
                    "platform": "douyin", "id": aw.get("aweme_id"),
                    "title": desc[:80],
                    "author": (aw.get("author") or {}).get("nickname"),
                    "play": ((aw.get("statistics") or {}).get("play_count")),
                    "like": ((aw.get("statistics") or {}).get("digg_count")),
                    "duration": ((aw.get("video") or {}).get("duration")),
                    "pubdate": aw.get("create_time"),
                    "url": f"https://www.douyin.com/video/{aw.get('aweme_id')}",
                    "desc": desc[:160],
                })

        with sync_playwright() as p:
            kwargs = dict(user_data_dir=str(self.PROFILE), channel="msedge",
                          headless=not headed, locale="zh-CN",
                          viewport={"width": 1440, "height": 900},
                          args=["--disable-blink-features=AutomationControlled",
                                "--no-first-run", "--no-default-browser-check"])
            if self.proxy:
                kwargs["proxy"] = {"server": self.proxy}
            ctx = p.chromium.launch_persistent_context(**kwargs)
            try:
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                pg.on("response", on_response)
                pg.goto("https://www.douyin.com/", wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(5000)
                pg.goto(f"https://www.douyin.com/search/{urllib.parse.quote(keyword)}",
                        wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(10000)
                title = pg.title()
                body_len = len(pg.inner_text("body"))
                if "验证码" in title or body_len < 50:
                    raise RuntimeError(
                        "抖音返回「验证码中间页」——自动化被识别。\n"
                        "  对策：① 运行 `vsearch login douyin` 在弹出的浏览器里扫码登录；\n"
                        "        ② 或直接在抖音 App 里搜到视频，把分享链接交给 `vsearch grab <url>`。"
                    )
            finally:
                ctx.close()
        return captured[:limit]


# ---------------------------------------------------------------- 转写后处理

def fold_repeats(text: str, min_unit: int = 4, min_reps: int = 3) -> tuple[str, int]:
    """折叠 ASR 幻觉式重复：'It's done well. It's done well. …' -> 一次。

    Qwen/Whisper 在纯音乐或无清晰人声段落会陷入重复循环，一次能刷几十遍。
    返回 (清理后文本, 折叠掉的字数)。
    """
    if not text:
        return text, 0
    orig_len = len(text)
    # 反复折叠，直到稳定（处理嵌套重复）
    for _ in range(6):
        # 匹配「某个至少 min_unit 字的片段」连续出现 min_reps 次以上
        pat = re.compile(r"(.{%d,}?)\1{%d,}" % (min_unit, min_reps - 1), re.S)
        new = pat.sub(lambda m: m.group(1), text)
        if new == text:
            break
        text = new
    return text, orig_len - len(text)


def clean_transcript_files(outdir: Path) -> dict:
    """清理 v2t 产出的 md/txt/srt 中的重复幻觉，原地改写并返回统计。"""
    stats = {"files": [], "removed_chars": 0, "flagged_paras": 0}
    if not outdir.exists():
        return stats
    for f in list(outdir.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        # 按 "## [mm:ss]" 段落切分，保留表头
        parts = re.split(r"(?m)^(## \[\d{2}:\d{2}(?::\d{2})?\])$", raw)
        rebuilt = [parts[0]] if parts else []
        removed = 0
        flagged = 0
        i = 1
        while i < len(parts) - 1:
            header, body = parts[i], parts[i + 1]
            fixed, cut = fold_repeats(body)
            removed += cut
            if cut > 0:
                flagged += 1
                # 清理后过于单薄的段落标注出来，别让 agent 当有效内容引用
                if len(fixed.strip()) < 20:
                    fixed = fixed.rstrip() + "\n\n> ⚠️ 本段疑似 ASR 幻听（重复内容已折叠），内容不可信\n"
            rebuilt.append(header)
            rebuilt.append(fixed)
            i += 2
        if removed:
            f.write_text("".join(rebuilt), encoding="utf-8")
            stats["files"].append(f.name)
            stats["removed_chars"] += removed
            stats["flagged_paras"] += flagged
    # txt / srt 同步处理
    for f in list(outdir.glob("*.txt")) + list(outdir.glob("*.srt")):
        raw = f.read_text(encoding="utf-8")
        fixed, cut = fold_repeats(raw)
        if cut:
            f.write_text(fixed, encoding="utf-8")
            stats["removed_chars"] += cut
    return stats


# ---------------------------------------------------------------- 统一入口

def detect_platform(url_or_id: str) -> tuple[str, str]:
    s = url_or_id.strip()
    m = re.search(r"(BV[0-9A-Za-z]{10})", s)
    if m:
        return "bilibili", m.group(1)
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([0-9A-Za-z_-]{11})", s)
    if m:
        return "youtube", m.group(1)
    m = re.search(r"douyin\.com/video/(\d+)", s)
    if m:
        return "douyin", m.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", s):
        return "youtube", s
    raise ValueError(f"无法识别平台: {url_or_id}")


def fmt_duration(dur) -> str:
    """B站给 '9:10' 或 '1:02:03'，YouTube 给秒数。统一成 mm:ss / h:mm:ss。"""
    if dur is None or dur == "":
        return "?"
    if isinstance(dur, str):
        return dur if ":" in dur else (f"{int(dur)//60}:{int(dur)%60:02d}" if dur.isdigit() else dur)
    try:
        d = int(dur)
    except (TypeError, ValueError):
        return str(dur)
    if d >= 3600:
        return f"{d//3600}:{(d%3600)//60:02d}:{d%60:02d}"
    return f"{d//60}:{d%60:02d}"


def cmd_search(args, cfg):
    kw = args.keyword
    limit = args.limit
    tasks = {}

    if args.platform in ("bili", "all"):
        b = Bilibili(cfg.get("proxy"))
        tasks["bilibili"] = lambda: b.search(kw, limit, sort=args.sort)

    if args.platform in ("yt", "all"):
        y = YouTube(cfg.get("ytdlp_proxy"))
        tasks["youtube"] = lambda: y.search(kw, limit)

    if args.platform in ("dy", "all"):
        d = Douyin(cfg.get("proxy"))
        tasks["douyin"] = lambda: d.search(kw, limit, headed=args.headed)

    results: dict[str, list] = {}
    errors: dict[str, str] = {}

    if len(tasks) == 1:
        name = next(iter(tasks))
        try:
            results[name] = tasks[name]()
        except Exception as e:
            errors[name] = str(e)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(tasks)) as ex:
            futs = {ex.submit(fn): name for name, fn in tasks.items()}
            for fut in concurrent.futures.as_completed(futs):
                name = futs[fut]
                try:
                    results[name] = fut.result()
                except Exception as e:
                    errors[name] = str(e)

    payload = {"keyword": kw, "results": results, "errors": errors}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for plat, items in results.items():
            print(f"\n【{plat}】{len(items)} 条")
            for i, v in enumerate(items, 1):
                dur_s = fmt_duration(v.get("duration"))
                print(f"  {i:2d}. {v['title'][:52]}")
                print(f"      {v.get('author','?')} | 播放{v.get('play','?')} | {dur_s} | {v['url']}")
        for plat, err in errors.items():
            print(f"\n【{plat}】失败：{err}")
    return 0 if results else 1


def cmd_info(args, cfg):
    plat, vid = detect_platform(args.target)
    if plat == "bilibili":
        d = Bilibili(cfg.get("proxy")).info(vid)
    elif plat == "youtube":
        d = YouTube(cfg.get("ytdlp_proxy")).info(vid)
    else:
        raise SystemExit("抖音暂不支持纯 API 取元信息，请直接 grab")
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        print(f"标题: {d['title']}\n作者: {d['author']}\n时长: {d['duration']}s\n"
              f"播放: {d.get('play')}  点赞: {d.get('like')}\nURL: {d['url']}\n\n简介:\n{d['desc']}")
    return 0


def cmd_grab(args, cfg):
    """调 v2t 转文案。自动带上已保存的 cookie（免去读浏览器数据库）。"""
    if not V2T_CMD.exists():
        raise SystemExit(f"找不到 v2t：{V2T_CMD}")
    cmd = [str(V2T_CMD), args.target]
    if args.outdir:
        cmd += ["--outdir", args.outdir]
    if args.model:
        cmd += ["--model", args.model]
    if args.proxy or cfg.get("proxy"):
        cmd += ["--proxy", args.proxy or cfg["proxy"]]
    if args.headed:
        cmd += ["--headed"]

    # cookie 优先用 vsearch 自己保存的，其次才回落到读浏览器
    if args.cookies_from_browser:
        cmd += ["--cookies-from-browser", args.cookies_from_browser]
    else:
        try:
            plat, _ = detect_platform(args.target)
        except ValueError:
            plat = None
        ck = COOKIE_DIR / f"{plat}.txt" if plat else None
        if ck and ck.exists():
            cmd += ["--cookies", str(ck)]
            print(f"[vsearch] 使用已保存 cookie: {ck}", file=sys.stderr)

    print(f"[vsearch] 调用 v2t: {' '.join(cmd)}", file=sys.stderr)
    rc = subprocess.call(cmd)

    # v2t 完成后自动折叠 ASR 幻觉重复
    if rc == 0:
        outdir = Path(args.outdir) if args.outdir else (Path.cwd() / "视频文案提取")
        st = clean_transcript_files(outdir)
        if st["removed_chars"]:
            print(f"\n[vsearch] 幻觉清理：折叠 {st['removed_chars']} 字符重复，"
                  f"涉及 {st['flagged_paras']} 个段落", file=sys.stderr)
            for n in st["files"]:
                print(f"          已改写 {n}", file=sys.stderr)
        else:
            print("\n[vsearch] 幻觉清理：未检测到重复循环", file=sys.stderr)
    return rc


def cmd_login(args, cfg):
    """打开持久化浏览器让用户手动登录一次，然后导出 cookie 供 v2t / B站API 复用。

    这样绕开了「浏览器开着 -> cookie 数据库被锁 -> yt-dlp --cookies-from-browser 失败」
    的老问题：cookie 由我们自己在登录后快照，存成独立文件。
    """
    plat = args.platform
    meta = SITE_META[plat]
    from playwright.sync_api import sync_playwright

    kwargs = dict(user_data_dir=str(meta["profile"]), channel="msedge",
                  headless=False, locale="zh-CN",
                  viewport={"width": 1440, "height": 900},
                  args=["--disable-blink-features=AutomationControlled",
                        "--no-first-run", "--no-default-browser-check"])
    if cfg.get("proxy"):
        kwargs["proxy"] = {"server": cfg["proxy"]}

    print(f"正在打开 {meta['url']} …")
    print("=" * 62)
    print("请在弹出的浏览器窗口里完成登录（扫码 / 账号密码均可）。")
    print("检测到登录成功会自动保存并关闭，无需手动操作。")
    print("=" * 62)

    found: list[dict] = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(**kwargs)
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            pg.goto(meta["url"], wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"页面加载告警（继续）: {type(e).__name__}")

        deadline = time.time() + args.timeout
        try:
            while time.time() < deadline:
                time.sleep(2.5)
                try:
                    cookies = ctx.cookies()
                except Exception:
                    break
                names = {c.get("name") for c in cookies}
                hit = names & set(meta["login_cookies"])
                if hit:
                    print(f"\n✓ 检测到登录 cookie: {', '.join(sorted(hit))}")
                    found = cookies
                    break
                left = int(deadline - time.time())
                print(f"  等待登录中… 剩余 {left}s", end="\r")
        except KeyboardInterrupt:
            print("\n已中断，尝试保存当前 cookie…")
            try:
                found = ctx.cookies()
            except Exception:
                found = []
        finally:
            try:
                if not found:
                    found = ctx.cookies()
            except Exception:
                pass
            ctx.close()

    wanted = [c for c in found if meta["domain_hint"] in (c.get("domain") or "")]
    if not wanted:
        print("\n✗ 没拿到任何 cookie，登录未完成。请重试。")
        return 1

    (COOKIE_DIR / f"{plat}.json").write_text(
        json.dumps(wanted, ensure_ascii=False, indent=2), encoding="utf-8")
    to_netscape(wanted, COOKIE_DIR / f"{plat}.txt")

    print(f"\n已保存 {len(wanted)} 条 cookie：")
    print(f"  {COOKIE_DIR / f'{plat}.json'}")
    print(f"  {COOKIE_DIR / f'{plat}.txt'}   ← 供 v2t / yt-dlp 使用")

    # B站 cookie 顺带喂给 polylens MCP，避免二次扫码
    if plat == "bili":
        try:
            p = to_polylens_cookie(wanted)
            print(f"  {p}   ← 供 polylens MCP 使用（共用登录态）")
        except Exception as e:
            print(f"  （polylens cookie 写入失败：{e}）")

    # 立即校验
    if plat == "bili":
        b = Bilibili(cfg.get("proxy"))
        b._init()
        print(f"B站登录态校验: isLogin={getattr(b, '_logged_in', False)}")
    elif plat == "yt":
        print("YouTube 校验：运行 `vsearch yt <关键词>` 或 `vsearch grab <yt-url>` 验证")
    return 0


def cmd_subs(args, cfg):
    """直接取 B站字幕文本（需先 login bili）。"""
    plat, vid = detect_platform(args.target)
    if plat != "bilibili":
        raise SystemExit("目前仅 B站支持直取字幕；YouTube 请用 grab（走 yt-dlp 字幕）")
    b = Bilibili(cfg.get("proxy"))
    info = b.subtitles(vid)
    if info["requires_login"] or not info["tracks"]:
        print("没有可用字幕轨。可能原因：视频本身无字幕 / 未登录（先跑 vsearch login bili）")
        return 1
    # 优先中文
    tracks = sorted(info["tracks"],
                    key=lambda t: 0 if (t.get("lan") or "").startswith("zh") else 1)
    t = tracks[0]
    print(f"[字幕轨] {t['lan']} / {t['lan_doc']}", file=sys.stderr)
    lines = b.subtitle_text(t["url"])
    if args.json:
        print(json.dumps(lines, ensure_ascii=False, indent=2))
    else:
        for ln in lines:
            m, s = divmod(int(ln["from"]), 60)
            print(f"[{m:02d}:{s:02d}] {ln['content']}")
    return 0


def cmd_doctor(args, cfg):
    print("=== vsearch 环境自检 ===")
    print(f"配置目录: {CFG_DIR}")
    print(f"代理: {cfg.get('proxy') or '未探测到'}")

    print(f"\n[v2t] {V2T_CMD} -> {'存在' if V2T_CMD.exists() else '缺失'}")
    print(f"[v2t pylib] {V2T_PYLIB} -> {'存在' if V2T_PYLIB.exists() else '缺失'}")

    for name, cls in (("Bilibili", None), ("YouTube", None)):
        pass

    # B站
    try:
        b = Bilibili(cfg.get("proxy"))
        r = b.search("test", 1)
        print(f"[B站搜索] OK（{len(r)} 条）登录态: {getattr(b, '_logged_in', '?')}")
    except Exception as e:
        print(f"[B站搜索] 失败: {e}")

    # YouTube
    try:
        y = YouTube(cfg.get("ytdlp_proxy"))
        r = y.search("test", 1)
        print(f"[YouTube 搜索] OK（{len(r)} 条）")
    except Exception as e:
        print(f"[YouTube 搜索] 失败: {str(e)[:160]}")

    # playwright
    try:
        import playwright  # noqa: F401
        print("[playwright] OK")
    except ImportError:
        print("[playwright] 缺失（抖音需要）")

    prof_dy = PROF_DIR / "douyin"
    print(f"[抖音 profile] {prof_dy} -> {'已初始化' if prof_dy.exists() else '未登录'}")
    return 0


def main():
    ap = argparse.ArgumentParser(prog="vsearch", description="跨平台视频情报检索")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, helptext in (("bili", "B站搜索（免登录）"), ("yt", "YouTube 搜索（免登录）"),
                           ("dy", "抖音搜索（需登录态）"), ("all", "三平台并发搜索")):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument("keyword")
        sp.add_argument("--limit", type=int, default=15)
        sp.add_argument("--json", action="store_true")
        sp.add_argument("--sort", default="totalrank",
                        help="B站排序: totalrank/click/pubdate")
        sp.add_argument("--headed", action="store_true", help="抖音用可见浏览器（过验证码）")
        sp.set_defaults(func=cmd_search, platform=name)

    sp = sub.add_parser("info", help="视频元信息")
    sp.add_argument("target")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_info)

    sp = sub.add_parser("grab", help="转文案（调 v2t）")
    sp.add_argument("target")
    sp.add_argument("--outdir", default=None)
    sp.add_argument("--model", default=None)
    sp.add_argument("--proxy", default=None)
    sp.add_argument("--headed", action="store_true")
    sp.add_argument("--cookies-from-browser", default=None)
    sp.set_defaults(func=cmd_grab)

    sp = sub.add_parser("login", help="登录一次，长期复用")
    sp.add_argument("platform", choices=["bili", "yt", "dy"])
    sp.add_argument("--timeout", type=int, default=180, help="等待登录秒数（默认180）")
    sp.set_defaults(func=cmd_login)

    sp = sub.add_parser("subs", help="直取 B站字幕文本（需先 login bili）")
    sp.add_argument("target")
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_subs)

    sp = sub.add_parser("doctor", help="环境自检")
    sp.set_defaults(func=cmd_doctor)

    args = ap.parse_args()
    cfg = load_config()
    try:
        sys.exit(args.func(args, cfg))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
