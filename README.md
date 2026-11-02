# vsearch —— 跨平台视频情报检索

给 agent 用的「去视频网站找深度内容」工具：B站 / YouTube / 抖音 搜索 → 元信息 → 转文案 → 总结。

## 为什么做这个

网页关键词搜索 + 扒文字，对**新工具、新项目、实操踩坑**这类内容效果差——这些东西往往
只在视频里有人讲，而且讲得比网页深。这个工具补上这一层。

## 快速开始

```powershell
D:\tools\vsearch\vsearch.cmd doctor                    # 环境自检
D:\tools\vsearch\vsearch.cmd all "deepseek harness" --limit 10
D:\tools\vsearch\vsearch.cmd grab "<视频链接>" --outdir "<目录>"
```

## 平台能力（2026-11-02 实测）

| 能力 | B站 | YouTube | 抖音 |
|---|---|---|---|
| 搜索 | ✅ 免登录 | ✅ 免登录（需代理） | ❌ 需登录 |
| 元信息 | ✅ 免登录 | ✅ 免登录 | ⚠️ 随搜索 |
| 字幕直取 | ⚠️ 需登录 | ⚠️ 需登录+代理 | ❌ |
| 下载→ASR | ✅ 免登录 | ❌ 需登录+代理 | ✅ 浏览器嗅探 |

## 一次登录，多处复用

`vsearch login bili` 会写三份 cookie：

- `~/.video-research/cookies/bili.json` → vsearch 自己的 API
- `~/.video-research/cookies/bili.txt` → v2t / yt-dlp（Netscape 格式）
- `~/.cache/polylens-bilibili/cookie` → polylens MCP（Cookie header 格式）

这样避开了 `yt-dlp --cookies-from-browser` 在浏览器开着时读不到数据库的坑。

## 已知问题与实测数据

- **B站并发限流**：`all` 模式并发请求时 B站返回 `code:0` 但结果为空。
  已内置 3 次退避重试修复。
- **YouTube 风控**：`Sign in to confirm you're not a bot` 是 IP+指纹双重风控，
  换 player_client 全无效，Invidious/Piped 镜像也基本死了。唯一解是登录导出 cookie。
- **抖音搜索**：headless/headed 都返回「验证码中间页」，必须扫码登录。
  但**视频转文案完全可用**（v2t 浏览器嗅探，实测 25.4MB 抓取成功）。
- **ASR 幻觉**：Qwen3-ASR 在无人声段落会把一句话重复几十遍（实测一次刷 90 遍）。
  `grab` 已内置 `fold_repeats` 自动折叠，并把清理后过短的段落标 `⚠️ 疑似幻听`。
- **ASR 速度**：本机 GPU 约 0.6x 实时（9分钟视频≈5分钟）。
- **专有名词必错**："[DSH]" 被听成 "Hynix"/"Hunnes"/"Honey's"，引用前需校正。

## 文件结构

```
vsearch.py                     # 主程序（约 900 行，零第三方依赖，playwright 可选）
_probes/                       # 开发期探测脚本（保留作证据）
_screenshots/                  # 探测截图
文案输出/ 抖音测试/             # 实测产物
```

安装位置：`D:\tools\vsearch\`（唯一真相源）
Skill 文档：`C:\Users\xianw\.agents\skills\video-research\SKILL.md`

## 依赖

- Python 3.13+
- `playwright`（抖音通道，可选）
- `D:\tools\v2t\`（转文案，已存在）
- 代理（YouTube 必需，从 Windows 系统代理自动探测）
