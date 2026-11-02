#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""deploy.py -- 把仓库里的 vsearch.py 装到 D:\\tools\\vsearch\\

先做语法检查再复制，复制后跑 doctor 验证。
"""
import ast
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).parent / "vsearch.py"
DST_DIR = Path(r"D:\tools\vsearch")
DST = DST_DIR / "vsearch.py"


def main() -> int:
    if not SRC.exists():
        print(f"[x] 找不到 {SRC}")
        return 1

    src_text = SRC.read_text(encoding="utf-8")
    try:
        ast.parse(src_text)
    except SyntaxError as e:
        print(f"[x] 语法检查失败，中止部署：{e}")
        return 1

    DST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, DST)
    print(f"[+] 已部署到 {DST}  ({len(src_text)} 字符)")

    print("\n验证：")
    r = subprocess.run([sys.executable, str(DST), "doctor"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print(r.stdout or r.stderr)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
