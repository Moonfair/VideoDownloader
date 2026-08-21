#!/usr/bin/env python3
"""Dispatch public video downloads to the bundled Weibo or Bilibili downloader."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from weibo_browser_resolver import BrowserResolutionError, resolve_weibo_media


BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}
WEIBO_HOSTS = {"weibo.com", "www.weibo.com", "m.weibo.cn", "weibo.cn", "www.weibo.cn"}
def _host(value: str) -> str:
    candidate = value if "://" in value else f"https://{value}"
    return (urlparse(candidate).hostname or "").lower()


def detect_platform(arguments: list[str]) -> str:
    """Detect a supported platform from arguments intended for the child script."""
    lowered = [value.lower() for value in arguments]
    if "--media-url" in lowered:
        return "weibo"

    for value in arguments:
        host = _host(value)
        if host in WEIBO_HOSTS or host.endswith(".weibo.com") or host.endswith(".weibo.cn"):
            return "weibo"
        if host in BILIBILI_HOSTS or host.endswith(".bilibili.com"):
            return "bilibili"

    positional = [value for value in arguments if not value.startswith("-")]
    if any(re.fullmatch(r"(?i)(?:BV[0-9A-Za-z]{10}|av\d+|\d+)", value) for value in positional):
        return "bilibili"
    raise ValueError("无法识别视频平台；请提供微博/Bilibili 链接，或使用 --platform 指定平台")


def build_command(platform: str, arguments: list[str]) -> list[str]:
    script_name = "weibo_media_downloader.py" if platform == "weibo" else "bilibili_video_downloader.py"
    script = Path(__file__).with_name(script_name)
    return [sys.executable, "-S", str(script), *arguments]


def resolve_weibo_arguments(arguments: list[str]) -> list[str]:
    """Replace a public Weibo page with validated media URLs from isolated Chromium."""
    if "--media-url" in arguments:
        return arguments
    page_index = next(
        (
            index
            for index, value in enumerate(arguments)
            if _host(value) in WEIBO_HOSTS
            or _host(value).endswith(".weibo.com")
            or _host(value).endswith(".weibo.cn")
        ),
        None,
    )
    if page_index is None:
        return arguments
    timeout = 30.0
    for index, value in enumerate(arguments):
        if value == "--timeout" and index + 1 < len(arguments):
            timeout = float(arguments[index + 1])
        elif value.startswith("--timeout="):
            timeout = float(value.partition("=")[2])
    media_urls = resolve_weibo_media(arguments[page_index], timeout)
    resolved = [value for index, value in enumerate(arguments) if index != page_index]
    for media_url in media_urls:
        resolved.extend(("--media-url", media_url))
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="自动识别并调用内置的微博或 Bilibili 公共视频下载器",
        add_help=False,
    )
    parser.add_argument("--platform", choices=("auto", "weibo", "bilibili"), default="auto")
    parser.add_argument("-h", "--help", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    options, remaining = parser.parse_known_args(argv)
    if options.help:
        parser.print_help()
        print("\n其余参数将原样传给对应平台下载器。")
        return 0
    try:
        platform = options.platform if options.platform != "auto" else detect_platform(remaining)
    except ValueError as exc:
        parser.error(str(exc))
    if platform == "weibo":
        try:
            remaining = resolve_weibo_arguments(remaining)
        except (BrowserResolutionError, ValueError) as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
    return subprocess.run(build_command(platform, remaining), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
