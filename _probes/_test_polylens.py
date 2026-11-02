# -*- coding: utf-8 -*-
"""测试 polylens-bilibili-mcp 是否能启动并响应 tools/list"""
import json, subprocess, sys, time

CMD = [r"C:\Users\xianw\AppData\Local\Python\pythoncore-3.14-64\Scripts\uvx.exe",
       "--from", "polylens-bilibili-mcp", "polylens-bilibili-mcp"]

proc = subprocess.Popen(CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, encoding="utf-8",
                        bufsize=1)

def send(obj):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()

def recv(timeout=30):
    import threading
    result = {}
    def _r():
        result["line"] = proc.stdout.readline()
    t = threading.Thread(target=_r, daemon=True)
    t.start()
    t.join(timeout)
    return result.get("line", "")

# initialize
send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2024-11-05",
                 "capabilities": {},
                 "clientInfo": {"name": "test", "version": "1.0"}}})
line = recv(40)
print("=== initialize ===")
print(line[:600] if line else "!! 无响应")

send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
line = recv(30)
print("\n=== tools/list ===")
if line:
    try:
        d = json.loads(line)
        tools = d.get("result", {}).get("tools", [])
        print(f"工具数: {len(tools)}")
        for t in tools:
            print("  -", t.get("name"))
    except Exception as e:
        print("解析失败:", e, line[:400])
else:
    print("!! 无响应")

proc.terminate()
try:
    err = proc.stderr.read()[:500]
    if err:
        print("\n=== stderr ===")
        print(err)
except Exception:
    pass
