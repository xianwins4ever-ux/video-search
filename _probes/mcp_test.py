# -*- coding: utf-8 -*-
"""经 MCP 协议实测 polylens-bilibili：stderr 重定向避免管道死锁。"""
import json
import subprocess
from pathlib import Path

UVX = r"C:\Users\xianw\AppData\Local\Python\pythoncore-3.14-64\Scripts\uvx.exe"
ERR = Path(__file__).parent / "mcp_stderr.log"

errf = open(ERR, "w", encoding="utf-8")
proc = subprocess.Popen(
    [UVX, "--from", "polylens-bilibili-mcp", "polylens-bilibili-mcp"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errf,
    text=True, encoding="utf-8", bufsize=1)

dec = json.JSONDecoder()
buf = ""


def read_msg():
    global buf
    while True:
        buf = buf.lstrip()
        if buf:
            try:
                obj, end = dec.raw_decode(buf)
                buf = buf[end:]
                return obj
            except json.JSONDecodeError:
                pass
        chunk = proc.stdout.readline()
        if not chunk:
            return None
        buf += chunk


def call(o):
    proc.stdin.write(json.dumps(o) + "\n")
    proc.stdin.flush()
    for _ in range(500):
        m = read_msg()
        if m is None:
            return None
        if isinstance(m, dict) and "jsonrpc" in m:
            return m
    return None


print("1) initialize ...")
r = call({"jsonrpc": "2.0", "id": 1, "method": "initialize",
          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                     "clientInfo": {"name": "probe", "version": "1"}}})
print("   ok:", bool(r and "result" in r))
call({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

print("2) tools/list ...")
r = call({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
tools = ((r or {}).get("result") or {}).get("tools", [])
print("   tools:", len(tools))
for t in tools:
    print("   -", t["name"])

print("3) search_videos ...")
r = call({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
          "params": {"name": "search_videos",
                     "arguments": {"keyword": "deepseek harness", "jq": ".", "page": 1}}})
print("   ", (json.dumps(r, ensure_ascii=False) if r else "no response")[:700])

proc.terminate()
errf.close()
print("\n=== stderr tail ===")
print(ERR.read_text(encoding="utf-8")[-600:])
