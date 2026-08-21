#!/usr/bin/env python3
"""Download public Weibo media URLs obtained from a trusted browser session."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


ALLOWED_HOST_SUFFIXES = (".weibocdn.com", ".sinaimg.cn")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"


def validate_media_url(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not any(host.endswith(suffix) for suffix in ALLOWED_HOST_SUFFIXES):
        raise ValueError("媒体地址必须是微博官方 HTTPS CDN 地址")
    return value


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "-", value).strip(".-")
    return cleaned[:100] or "weibo-video"


def media_name(url: str, index: int) -> str:
    parsed = urlparse(url)
    media_id = parse_qs(parsed.query).get("media_id", [""])[0]
    stem = media_id or Path(parsed.path).stem or f"weibo-video-{index}"
    return f"{safe_name(stem)}.mp4"


def download(url: str, destination: Path, timeout: float) -> int:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Referer": "https://weibo.com/"})
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with urlopen(request, timeout=timeout) as response, partial.open("wb") as output:
            content_type = response.headers.get_content_type()
            if content_type != "video/mp4" and not content_type.startswith("video/"):
                raise ValueError(f"CDN 返回了非视频内容: {content_type}")
            total = 0
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
                total += len(chunk)
        partial.replace(destination)
        return total
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载可信浏览器解析出的微博公开媒体地址")
    parser.add_argument("url", nargs="?", help="微博公开页面链接；页面解析需由 Agent 浏览器完成")
    parser.add_argument("--media-url", action="append", default=[], help="微博 CDN 媒体地址，可重复")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "weibo-videos")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--resolve-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.media_url:
        print(json.dumps({
            "ok": False,
            "error": "微博公开页面需要 Agent 的可信浏览器执行 JavaScript 后读取 video.currentSrc，再通过 --media-url 继续",
            "browser_required": True,
            "url": args.url,
        }, ensure_ascii=False))
        return 1
    try:
        urls = list(dict.fromkeys(validate_media_url(value) for value in args.media_url))
        if args.resolve_only:
            print(json.dumps({"ok": True, "platform": "weibo", "media": urls}, ensure_ascii=False, indent=2))
            return 0
        args.output_dir.mkdir(parents=True, exist_ok=True)
        downloads = []
        for index, url in enumerate(urls, 1):
            path = (args.output_dir / media_name(url, index)).resolve()
            size = download(url, path, args.timeout)
            downloads.append({"url": url, "path": str(path), "bytes": size})
        print(json.dumps({"ok": True, "downloads": downloads}, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
