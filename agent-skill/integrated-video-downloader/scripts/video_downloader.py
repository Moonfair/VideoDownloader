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


BILIBILI_HOSTS = {"bilibili.com", "www.bilibili.com", "m.bilibili.com", "b23.tv"}
WEIBO_HOSTS = {"weibo.com", "www.weibo.com", "m.weibo.cn", "weibo.cn", "www.weibo.cn"}
TASK_SCHEMA = "integrated-video-downloader.task.v1"


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


def load_task(path: Path) -> tuple[str, list[str]]:
    """Load a static-workbench task and convert its allowed fields to CLI arguments."""
    try:
        task = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取任务文件: {exc}") from exc
    if not isinstance(task, dict) or task.get("schema") != TASK_SCHEMA:
        raise ValueError(f"任务文件 schema 必须为 {TASK_SCHEMA}")

    value = task.get("input")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("任务文件缺少有效的 input")
    platform = task.get("platform", "auto")
    if platform not in {"auto", "weibo", "bilibili"}:
        raise ValueError("任务文件 platform 仅支持 auto、weibo 或 bilibili")
    if platform == "auto":
        platform = detect_platform([value])

    action = task.get("action", "resolve")
    if action not in {"resolve", "download"}:
        raise ValueError("任务文件 action 仅支持 resolve 或 download")

    arguments = [value]
    if action == "resolve":
        arguments.append("--resolve-only")
    else:
        output_dir = task.get("outputDir", "videos")
        if not isinstance(output_dir, str) or not output_dir.strip():
            raise ValueError("任务文件 outputDir 必须为非空字符串")
        arguments.extend(("--output-dir", output_dir))

    timeout = task.get("timeout", 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
        raise ValueError("任务文件 timeout 必须在 1 到 600 秒之间")
    arguments.extend(("--timeout", str(timeout)))

    page = task.get("page")
    all_pages = task.get("allPages", False)
    if page is not None or all_pages:
        if platform != "bilibili":
            raise ValueError("page 和 allPages 仅适用于 Bilibili")
        if all_pages is not False and all_pages is not True:
            raise ValueError("任务文件 allPages 必须为布尔值")
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            raise ValueError("任务文件 page 必须为正整数")
        if page is not None and all_pages:
            raise ValueError("page 和 allPages 不能同时使用")
        if all_pages:
            arguments.append("--all-pages")
        elif page is not None:
            arguments.extend(("--page", str(page)))
    return platform, arguments


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="自动识别并调用内置的微博或 Bilibili 公共视频下载器",
        add_help=False,
    )
    parser.add_argument("--platform", choices=("auto", "weibo", "bilibili"), default="auto")
    parser.add_argument("--task-file", type=Path, help="读取静态操作台导出的任务 JSON")
    parser.add_argument("-h", "--help", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    options, remaining = parser.parse_known_args(argv)
    if options.help:
        parser.print_help()
        print("\n其余参数将原样传给对应平台下载器。")
        return 0
    if options.task_file:
        if remaining:
            parser.error("--task-file 不能与其它下载参数同时使用")
        try:
            platform, remaining = load_task(options.task_file)
        except ValueError as exc:
            parser.error(str(exc))
        return subprocess.run(build_command(platform, remaining), check=False).returncode
    try:
        platform = options.platform if options.platform != "auto" else detect_platform(remaining)
    except ValueError as exc:
        parser.error(str(exc))
    return subprocess.run(build_command(platform, remaining), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
