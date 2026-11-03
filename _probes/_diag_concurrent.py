# -*- coding: utf-8 -*-
"""诊断：并发场景下 B站搜索为什么返回 0 条"""
import concurrent.futures
import sys
import time

sys.path.insert(0, r"D:\tools\vsearch")
from vsearch import Bilibili, YouTube, load_config

cfg = load_config()
print("代理:", cfg.get("proxy"))
print()

KW = "deepseek harness 对比"

print("=== A. 单独跑 B站 ===")
t0 = time.time()
b = Bilibili(cfg.get("proxy"))
r = b.search(KW, 3)
print(f"  结果: {len(r)} 条，耗时 {time.time()-t0:.1f}s")

print("\n=== B. 单独跑 YouTube ===")
t0 = time.time()
y = YouTube(cfg.get("ytdlp_proxy"))
try:
    r2 = y.search(KW, 3)
    print(f"  结果: {len(r2)} 条，耗时 {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  失败: {str(e)[:100]}")

print("\n=== C. 并发跑（模拟 all 模式）===")
t0 = time.time()
tasks = {"bilibili": lambda: Bilibili(cfg.get("proxy")).search(KW, 3),
         "youtube": lambda: YouTube(cfg.get("ytdlp_proxy")).search(KW, 3)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
    futs = {ex.submit(fn): name for name, fn in tasks.items()}
    for fut in concurrent.futures.as_completed(futs):
        name = futs[fut]
        try:
            res = fut.result()
            print(f"  {name}: {len(res)} 条")
        except Exception as e:
            print(f"  {name}: 失败 {str(e)[:80]}")
print(f"  总耗时 {time.time()-t0:.1f}s")

print("\n=== D. 并发后隔 5 秒再跑 B站 ===")
time.sleep(5)
t0 = time.time()
r3 = Bilibili(cfg.get("proxy")).search(KW, 3)
print(f"  结果: {len(r3)} 条，耗时 {time.time()-t0:.1f}s")
