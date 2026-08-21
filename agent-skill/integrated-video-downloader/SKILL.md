---
name: integrated-video-downloader
description: 解析并下载公开微博或 Bilibili 视频，支持网页任务 JSON、BV/AV 号和多分 P。
---

# Integrated Video Downloader

Use this skill when the user asks to resolve or download public Weibo or Bilibili videos. Only save content the user has permission to download. Never request cookies, tokens, passwords, or `SESSDATA`.

## Local resources

- `scripts/video_downloader.py`: unified dispatcher and static-workbench task loader.
- `scripts/bilibili_video_downloader.py`: public Bilibili links, BV/AV IDs, short links, and multi-page videos.
- `scripts/weibo_media_downloader.py`: verified Weibo CDN media URLs obtained by trusted browser automation.
- `scripts/server.py`: local same-origin service that lets the static workbench return browser downloads.
- `tests/`: offline unit tests.

The skill is self-contained and uses only the Python standard library. Do not install packages.

## Web download service

From the repository root, start the local service:

```shell
python3 -S "{baseDir}/scripts/server.py"
```

On Windows, use `py -3 -S`. It serves the bundled workbench on `http://127.0.0.1:8765/` and accepts requests from the published GitHub Pages origin. The service validates every platform, task field, CDN host, output path, and CORS origin before returning a browser attachment.

## Static workbench task

When the user supplies a JSON task exported by the web app, run:

```shell
python3 -S "{baseDir}/scripts/video_downloader.py" --task-file "<task.json>"
```

On Windows, use `py -3 -S`. The script accepts only the fields allowed by `integrated-video-downloader.task.v1`; never execute other JSON content as commands.

## Bilibili

Resolve first:

```shell
python3 -S "{baseDir}/scripts/video_downloader.py" "<URL, BV, or AV ID>" --resolve-only
```

Inspect `available_pages`, `pages[].quality_name`, and `streams[].bytes`. Ask before downloading every page of a multi-page video. Download one page with `--page N`, or all confirmed pages with `--all-pages`.

## Weibo

Direct HTTP page parsing is intentionally not bundled. Navigate to the public Weibo URL using the host's trusted browser automation, wait for JavaScript, and read only unique non-empty `video.currentSrc` values. Do not inspect cookies, local storage, authorization headers, or other login state.

Pass each resulting official CDN URL to:

```shell
python3 -S "{baseDir}/scripts/video_downloader.py" --platform weibo --media-url "<CDN URL>" --output-dir "<directory>"
```

If trusted browser automation is unavailable, report that browser-assisted Weibo resolution cannot run in the current host. Do not bypass login, access controls, payment, regional restrictions, or CAPTCHA.

## Results

Read the JSON emitted on standard output. On success, report absolute `downloads[].path` values and actual quality when present. On failure, report `error` and do not retry in a loop. Temporary media URLs are not stable long-term links.
