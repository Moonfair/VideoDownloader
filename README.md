# 整合视频下载助手

一个自包含的 Agent Skill，用于解析和下载用户有权保存的公开微博与 Bilibili 视频。仓库不包含 Web 页面或常驻服务，运行时仅依赖 Python 标准库；微博公开页自动使用临时隔离的 Edge、Chrome 或 Chromium 执行页面 JavaScript。

## Skill 目录

完整可分发目录位于 `agent-skill/integrated-video-downloader/`。

| Harness | 安装目录 |
| --- | --- |
| Claude | `~/.claude/skills/` |
| Codex | `~/.codex/skills/` |
| DeepSeek Harness | `~/.agents/skills/` |
| OpenClaw | `~/.agents/skills/` 或 `~/.openclaw/skills/` |

## 直接调用

先解析视频信息：

```powershell
py -3 -S "agent-skill\integrated-video-downloader\scripts\video_downloader.py" "<微博或 Bilibili 链接、BV、AV>" --resolve-only
```

下载到指定目录：

```powershell
py -3 -S "agent-skill\integrated-video-downloader\scripts\video_downloader.py" "<微博或 Bilibili 链接、BV、AV>" --output-dir "<下载目录>"
```

Bilibili 多分 P 使用 `--page N` 或 `--all-pages`。微博解析不会读取用户日常浏览器的 Cookie、LocalStorage 或登录态，也不会绕过登录、付费、地区限制、验证码或平台访问控制。

## 测试

```powershell
$env:PYTHONDONTWRITEBYTECODE = "1"
py -3 -S -m unittest discover -s agent-skill/integrated-video-downloader/tests -p "test_*.py" -v
```

## License

Apache License 2.0。见 `LICENSE` 与 `NOTICE`。
