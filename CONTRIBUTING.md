# 贡献指南

## 开发环境

```bash
git clone https://github.com/xianwins4ever-ux/video-search.git
cd video-search
pip install yt-dlp

# 可选：抖音通道
pip install playwright && playwright install msedge

# 自检
python vsearch.py doctor
```

## 铁律

### 1. 不要硬编码本机路径

路径都走自动探测：

```python
CFG_DIR = Path(os.environ.get("VSEARCH_HOME") or (HOME / ".video-research"))
V2T_DIR = _detect_v2t_dir()      # 环境变量 > 同级目录 > 常见位置
FFMPEG_DIR = _detect_ffmpeg_dir() # 环境变量 > PATH > 常见位置
```

找不到依赖时**要优雅降级并提示**，不要直接崩：

```python
if V2T_CMD is None or not V2T_CMD.exists():
    raise SystemExit("找不到 v2t……搜索功能不受影响，只有 grab 需要它")
```

### 2. 不要提交这些东西

| 路径 | 原因 |
|---|---|
| `_probes/` `_screenshots/` | 开发期探测脚本，含大量一次性代码 |
| `B站字幕测试/` 等 | 测试产物 |
| `*_profile/` | 浏览器 profile，体积大且含登录态 |
| `cookies/` | **登录凭证，泄露等于账号被盗** |

### 3. 平台失败要留证据

这个项目的价值一半在于**记录了哪些路走不通**。改平台解析逻辑时：

- 在 README「平台能力」表里更新实测日期
- 如果某个方向已经验证失败，把**失败证据**（接口返回原文）写进注释
- 不要删除「已知不可行」的记录 —— 那是防重复投入的护栏

比如抖音搜索，代码里明确写了：

```python
if "验证码" in title or body_len < 50:
    raise RuntimeError(
        "抖音返回「验证码中间页」——自动化被识别。\n"
        "  对策：① …\n"
        "        ② …"
    )
```

这不是偷懒，是让后来者知道**这里已经试过了**。

### 4. 提交信息用中文

```
✅ 修复 v2t 改造后的 cookie 路径分裂
   v2t 改用 ~/.v2t/cookies 后，vsearch 仍只读旧路径，
   导致 subs 命令直接失效。

❌ update
```

## 提 PR 之前

```bash
python -c "import ast;ast.parse(open('vsearch.py',encoding='utf-8').read())"
python vsearch.py doctor
python vsearch.py bili "test" --limit 2
git status --short    # 确认没有敏感文件
```

PR 描述的「怎么验证的」要写具体命令和输出。

## 与 v2t 的关系

本项目**不实现**下载和转文字，调用 v2t 的 CLI。改这部分时注意：

- 保持解耦：v2t 不存在时，搜索功能必须仍然可用
- cookie 共享方向是单向的（本项目的 login 写入 v2t 的目录，反之不做）
- B站登录优先调用 v2t 的 `bili_auth.login()`，避免两份实现分叉
