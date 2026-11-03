# video-search

> 在 B站 / YouTube / 抖音上搜视频，把结果整理成结构化数据，再交给 [v2t](https://github.com/xianwins4ever-ux/video-to-text) 转成文字稿。
>
> **定位：只负责「找」，不负责「看」。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

---

## 为什么需要它

网页搜索给的是文章，但很多深度内容只在视频里：

- 新工具刚发布，文字资料还没跟上，B站/YouTube 上已经有人实测了
- 踩坑细节、真实体验，只有博主会讲
- 官方文档说一套，视频里博主实测是另一套

但直接搜视频网站有个问题：**你得一个个站点打开、搜索、筛选、记录**。
这个工具把这一步自动化。

## 它不做的事

**不下载视频，不转文字。** 那是 [v2t](https://github.com/xianwins4ever-ux/video-to-text) 的职责。

两个项目是互补的：

```
video-search  找到候选视频（本仓库）
     ↓  挑 2-3 个靠谱的
v2t           下载 / 抓字幕 → 带时间戳的文字稿
     ↓
你 / AI       阅读、总结、引用
```

---

## 安装

```bash
git clone https://github.com/xianwins4ever-ux/video-search.git
cd video-search

pip install yt-dlp

# 可选：抖音支持
pip install playwright && playwright install msedge
```

**如果要转文案**，另需安装 v2t，并放到同级目录（或用 `V2T_HOME` 环境变量指定）：

```
parent/
├── video-search/     ← 本项目
└── v2t/              ← 转文案
```

自检：

```bash
python vsearch.py doctor
```

---

## 快速开始

```bash
# 三平台并发搜索
python vsearch.py all "deepseek harness 对比" --limit 10

# 单平台
python vsearch.py bili "AI 音效生成" --sort click --limit 20
python vsearch.py yt "deepseek benchmark"
python vsearch.py dy "deepseek"

# 看视频元信息（简介、时长、播放量）
python vsearch.py info BV1xxxxxxx

# 转文案（调用 v2t）
python vsearch.py grab "https://www.bilibili.com/video/BVxxxxxxx"

# 直取 B站字幕（需登录，秒级）
python vsearch.py subs BV1xxxxxxx

# 登录一次，长期复用
python vsearch.py login bili
```

`--json` 输出结构化数据，方便管道处理。

---

## 平台能力（2026-11-03 实测）

**这张表是真实跑出来的，不是「理论上支持」。**

| 平台 | 搜索 | 元信息 | 字幕 | 转文案 |
|---|---|---|---|---|
| **B站** | ✅ 免登录 | ✅ | ⚠️ 需登录 | ✅ 秒级 |
| **YouTube** | ✅ 免登录（需代理） | ✅ | ⚠️ 看视频 | ⚠️ 多数无字幕 |
| **抖音** | ❌ 平台封闭 | ⚠️ | ❌ | ✅ 单条可用 |

### B站：推荐主力

搜索免登录，走自实现的 wbi 签名，不依赖任何 SDK。

**登录后能直取官方 AI 字幕**（播放器菜单里带 `(A)` 的那种），
这是 B站用自家模型生成的，零识别误差、秒级完成。登录一次约 180 天有效。

### YouTube：能搜，但字幕要看视频

**多数中文搬运视频真的没有字幕** —— 不是权限问题，是上传者没传、平台也没生成。
实测 5 个中文 AI 频道视频全部返回 `has no automatic captions`。
这类只能靠本地 ASR，术语准确率会明显下降。

另有一个独立问题：偶发 `Sign in to confirm you're not a bot`（IP 级风控），
换 `player_client`、Invidious/Piped 镜像都无效。

### 抖音：搜索是平台封闭，不是没做

登录后接口仍返回：

```json
"data": [],
"search_nil_info": {"search_nil_type": "verify_check"}
```

试过的方法全部失败：

- `headless` / `headed` 浏览器 → 「验证码中间页」
- **CDP 连接原生浏览器**（MediaCrawler 的核心手法）→ 页面被重定向回首页
- 6 种 `player_client` 全部失败

佐证：开源项目 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler)（69k★）
自 2024-06-07 起同样是「关键字搜索返回空数组」。

**结论：除非用付费 API（如 TikHub），否则拿不到抖音搜索结果。**
单条视频链接转文案仍然可用。

---

## 命令一览

| 命令 | 作用 |
|---|---|
| `all <kw>` | 三平台并发搜索 |
| `bili <kw>` | B站搜索（`--sort totalrank/click/pubdate`） |
| `yt <kw>` | YouTube 搜索 |
| `dy <kw>` | 抖音搜索（需登录，大概率失败） |
| `info <url\|bvid>` | 视频元信息 |
| `grab <url>` | 转文案（调用 v2t） |
| `subs <bvid>` | 直取 B站字幕 |
| `login <bili\|yt\|dy>` | 登录一次，长期复用 |
| `doctor` | 环境自检 |

## 环境变量

| 变量 | 作用 | 默认 |
|---|---|---|
| `VSEARCH_HOME` | 配置与登录态目录 | `~/.video-research` |
| `V2T_HOME` | v2t 项目位置 | 自动探测同级目录 |
| `V2T_FFMPEG_DIR` | ffmpeg 目录 | 从 PATH 查找 |

---

## 设计说明

### 为什么搜索层免登录

B站的 wbi 签名算法是公开的（JS 里能读到），自行实现即可，
不需要账号就能搜索。这样降低了使用门槛，也避免账号风险。

**只有字幕接口要求登录**（返回 `need_login_subtitle: True`），
所以登录态只在字幕和转文案时才需要。

### cookie 与 v2t 共享

`login bili` 直接把 cookie 写到 v2t 的目录（`~/.v2t/cookies/bili.json`），
**一次扫码两边都能用**。同时也会修正 SESSDATA 的内嵌过期时间戳
（浏览器显示 7 天，服务端认 180 天）。

### 限流与重试

B站对并发请求会返回空结果（`code: 0` 但 `result: []`），这是**静默限流**。
已内置 3 次退避重试。偶发仍可能返回 0 条，重跑一次即可。

---

## 故障排查

| 现象 | 处理 |
|---|---|
| B站搜索返回 0 条 | 偶发限流，重跑一次 |
| `subs` 说没有字幕轨 | 未登录，`python vsearch.py login bili` |
| YouTube 报 not a bot | IP 风控，换网络/代理 |
| 抖音「验证码中间页」 | 平台封闭，已知无解 |
| `找不到 v2t` | 克隆到同级目录，或设 `V2T_HOME` |

---

## 已知限制

- **抖音搜索**：平台封闭，不再尝试（见上文）
- **YouTube 无字幕视频**：只能 ASR，术语可能出错
- **B站限流**：偶发空结果，重试可解决

## 许可证

[MIT](LICENSE) © 2026 xianwins4ever-ux

## 免责声明

仅供个人学习研究。请遵守各平台服务条款，不要用于大规模爬取。
