# -*- coding: utf-8 -*-
"""更新 ~/.dsh/AGENTS.md 第 9 节（视频情报检索），补入 v2t 与平台边界的最新结论。"""
from pathlib import Path

p = Path.home() / ".dsh" / "AGENTS.md"
lines = p.read_text(encoding="utf-8").splitlines(keepends=True)

# 找第 9 节的起止：从 "## 9. 视频情报检索" 到下一个 "## " 或文件末尾
start = None
for i, ln in enumerate(lines):
    if ln.startswith("## 9. 视频情报检索"):
        start = i
        break

if start is None:
    raise SystemExit("未找到第 9 节")

end = len(lines)
for j in range(start + 1, len(lines)):
    if lines[j].startswith("## "):
        end = j
        break

new_section = """## 9. 视频情报检索（要查资料/找项目时先读）
详细说明见 `~/.agents/skills/video-research/SKILL.md`；v2t 交接见 `D:\\tools\\v2t\\交接说明.md`。要点：
1. **两个工具，分工明确**：
   - `D:\\tools\\vsearch\\vsearch.cmd` 负责**找**（跨平台搜索 → 元信息），源码 `E:\\Claude\\2026-11-02_视频情报检索工具\\`
   - `D:\\tools\\v2t\\v2t.cmd` 负责**看**（链接 → 带时间戳文案），两者均 git 管理
2. **B站是主力通道（2026-11-03 打通）**：执行 `v2t login` 扫码一次（有效期 **180 天**）后，
   B站视频**直取官方 AI 字幕**，1.3 秒出稿、零识别误差。不登录会退回 ASR，
   术语必错（agent→「A进」、DSH→「Hynix」）。**做任何 B站相关任务前先 `v2t status`。**
3. **YouTube 别再折腾**：多数中文视频**真的没字幕**（不是权限问题，实测 5 个全无）。
   间歇性 IP 风控换 player_client / 镜像均无效。提升准确率只能给 ASR 加热词表。
4. **抖音搜索是平台封闭**：登录后接口仍返回 `search_nil_type: verify_check`，
   CDP 连原生浏览器也过不了（MediaCrawler 自 2024-06 同样失败）。
   单视频转文案仍可用。**不要再尝试逆向搜索。**
5. **ASR 有幻觉**：Qwen3-ASR 在无人声段会循环重复（实测一次 90 遍）。`vsearch grab` 有折叠逻辑，
   v2t 本身没有。专有名词必错，引用前回视频核对。
6. **定位**：视频用于「发现 + 实操细节 + 时效性」，权威事实仍以官方文档/源码为准，两边交叉验证。
"""

lines[start:end] = [new_section]
p.write_text("".join(lines), encoding="utf-8")
print("已更新第 9 节")
