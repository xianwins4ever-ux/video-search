# -*- coding: utf-8 -*-
"""诊断 B站多词搜索为什么返回 0 条"""
import sys, urllib.parse
sys.path.insert(0, r"D:\tools\vsearch")
from vsearch import Bilibili, http_json

b = Bilibili(None)
for kw in ["deepseek harness", "claude code 对比", "deepseek harness 对比"]:
    url = b._signed("/x/web-interface/wbi/search/type", {
        "search_type": "video", "keyword": kw, "page": "1", "order": "totalrank"})
    print(f"\n=== [{kw}] ===")
    print("URL 片段:", url.split("keyword=")[1][:60])
    res = http_json(b.op, url)
    d = res.get("data") or {}
    print("code:", res.get("code"), "| numResults:", d.get("numResults"),
          "| result 条数:", len(d.get("result") or []))
    for v in (d.get("result") or [])[:3]:
        print("   -", v.get("title", "")[:40])
