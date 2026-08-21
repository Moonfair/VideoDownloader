---
name: integrated-video-downloader
description: 解析并下载公开微博或 Bilibili 视频，支持链接、BV/AV 号和多分 P。
---

# 整合视频下载助手

用户要求解析或下载公开微博、Bilibili 视频时使用。只保存用户有权下载的公开内容；不要索取 Cookie、Token、密码或 `SESSDATA`。

## 本地资源

- `scripts/video_downloader.py`：统一入口，自动识别微博与 Bilibili。
- `scripts/bilibili_video_downloader.py`：支持公开链接、BV/AV、短链和多分 P。
- `scripts/weibo_browser_resolver.py`：用隔离的 Edge/Chrome/Chromium 解析公开微博页。
- `scripts/weibo_media_downloader.py`：校验并下载微博官方 CDN 媒体。
- `tests/`：不访问网络的核心逻辑测试。

本 Skill 自包含，只使用 Python 标准库。不要安装依赖，也不要调用其它 Skill。

## 执行流程

1. 先解析用户提供的链接或编号：

```shell
python3 -S "{baseDir}/scripts/video_downloader.py" "<URL, BV, or AV ID>" --resolve-only
```

Windows 使用 `py -3 -S`。检查输出中的视频信息、实际画质和 Bilibili 分 P；多分 P 视频在下载全部内容前先询问用户。

2. 下载用户确认的内容：

```shell
python3 -S "{baseDir}/scripts/video_downloader.py" "<URL, BV, or AV ID>" --output-dir "<directory>"
```

Bilibili 指定分 P 使用 `--page N`，全部分 P 使用 `--all-pages`。

## 微博解析

直接把原始公开微博分享链接交给统一入口。脚本会创建一次性隔离浏览器配置、执行页面 JavaScript、读取非空且去重的 `video.currentSrc`，校验微博官方 HTTPS CDN 后下载，最后关闭浏览器并删除临时配置。

不要让用户手工查找或粘贴 `video.currentSrc`、Agent JSON 或 CDN 地址。脚本不使用用户日常浏览器配置，也不读取 Cookie、LocalStorage、授权头或登录态。系统未安装 Edge、Chrome 或 Chromium时，如实报告自动解析不可用。

## 结果与边界

读取标准输出 JSON。成功时报告 `downloads[].path` 的绝对路径和实际画质；失败时报告 `error`，不要循环重试。不要绕过登录、付费、地区限制、验证码或平台访问控制。临时媒体地址不是长期稳定链接。
