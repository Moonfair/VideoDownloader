#!/usr/bin/env python3
"""Local same-origin bridge for the static video download workbench."""

from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
import tempfile
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from weibo_browser_resolver import BrowserResolutionError, resolve_weibo_media


WEB_DIR = SCRIPT_DIR.parent / "web"
MAX_REQUEST_BYTES = 64 * 1024
PAGES_ORIGIN = "https://moonfair.github.io"


def allowed_origin(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlparse(value)
    if value == PAGES_ORIGIN:
        return value
    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}:
        return value
    return None


def build_arguments(
    task: dict[str, object],
    output_dir: Path,
    *,
    resolve_only: bool,
    weibo_media_urls: list[str] | None = None,
) -> tuple[str, list[str]]:
    value = task.get("input")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("缺少视频链接或编号")
    platform = task.get("platform", "auto")
    if platform not in {"auto", "weibo", "bilibili"}:
        raise ValueError("不支持的视频平台")
    if platform == "auto":
        host = (urlparse(value).hostname or "").lower()
        platform = "weibo" if "weibo" in host or host.endswith(".sinaimg.cn") else "bilibili"
    timeout = task.get("timeout", 30)
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
        raise ValueError("timeout 必须在 1 到 600 秒之间")

    if platform == "weibo":
        host = (urlparse(value).hostname or "").lower()
        if host.endswith(".weibocdn.com") or host.endswith(".sinaimg.cn"):
            media_urls = [value]
        elif weibo_media_urls:
            media_urls = weibo_media_urls
        else:
            raise ValueError("微博分享页需要由本地下载服务的浏览器解析器处理")
        arguments = []
        for media_url in media_urls:
            arguments.extend(("--media-url", media_url))
    else:
        arguments = [value]
        page = task.get("page")
        all_pages = task.get("allPages", False)
        if page is not None:
            if not isinstance(page, int) or isinstance(page, bool) or page < 1:
                raise ValueError("page 必须为正整数")
            arguments.extend(("--page", str(page)))
        if all_pages:
            if page is not None:
                raise ValueError("page 和 allPages 不能同时使用")
            arguments.append("--all-pages")
    arguments.extend(("--timeout", str(timeout)))
    if resolve_only:
        arguments.append("--resolve-only")
    else:
        arguments.extend(("--output-dir", str(output_dir)))
    return str(platform), arguments


def run_downloader(platform: str, arguments: list[str], timeout: float) -> dict[str, object]:
    name = "weibo_media_downloader.py" if platform == "weibo" else "bilibili_video_downloader.py"
    result = subprocess.run(
        [sys.executable, "-S", str(SCRIPT_DIR / name), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=max(300, timeout * 20),
        check=False,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(result.stderr.strip() or "下载器未返回有效 JSON") from exc
    if not isinstance(payload, dict) or not payload.get("ok"):
        raise ValueError(str(payload.get("error") or "下载失败"))
    return payload


def prepare_archive(paths: list[Path], directory: Path) -> tuple[Path, str]:
    if len(paths) == 1:
        return paths[0], paths[0].name
    archive = directory / "video-downloads.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as output:
        for path in paths:
            output.write(path, path.name)
    return archive, archive.name


class Handler(SimpleHTTPRequestHandler):
    server_version = "VideoDownloader/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def _cors(self) -> None:
        origin = allowed_origin(self.headers.get("Origin"))
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition")

    def _json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/status":
            self._json({"ok": True, "service": "video-downloader", "version": 1})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path not in {"/api/resolve", "/api/download"}:
            self._json({"ok": False, "error": "接口不存在"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("请求体大小无效")
            task = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(task, dict):
                raise ValueError("任务必须为 JSON 对象")
            timeout = float(task.get("timeout", 30))
            with tempfile.TemporaryDirectory(prefix="video-downloader-") as temp:
                directory = Path(temp)
                weibo_media_urls = None
                input_value = task.get("input")
                platform_hint = task.get("platform", "auto")
                if isinstance(input_value, str):
                    host = (urlparse(input_value).hostname or "").lower()
                    is_weibo_page = (
                        platform_hint == "weibo" or "weibo" in host
                    ) and not (host.endswith(".weibocdn.com") or host.endswith(".sinaimg.cn"))
                    if is_weibo_page:
                        weibo_media_urls = resolve_weibo_media(input_value, timeout)
                platform, arguments = build_arguments(
                    task,
                    directory,
                    resolve_only=self.path.endswith("resolve"),
                    weibo_media_urls=weibo_media_urls,
                )
                payload = run_downloader(platform, arguments, timeout)
                if self.path.endswith("resolve"):
                    self._json(payload)
                    return
                downloads = payload.get("downloads")
                if not isinstance(downloads, list) or not downloads:
                    raise ValueError("下载器没有生成文件")
                paths = [Path(item["path"]) for item in downloads if isinstance(item, dict) and isinstance(item.get("path"), str)]
                if not paths or any(not path.is_file() or directory not in path.parents for path in paths):
                    raise ValueError("下载文件校验失败")
                target, filename = prepare_archive(paths, directory)
                self.send_response(HTTPStatus.OK)
                self._cors()
                self.send_header("Content-Type", mimetypes.guess_type(filename)[0] or "application/octet-stream")
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename)}")
                self.send_header("Content-Length", str(target.stat().st_size))
                self.end_headers()
                with target.open("rb") as source:
                    while chunk := source.read(1024 * 1024):
                        self.wfile.write(chunk)
        except (ValueError, BrowserResolutionError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
            self._json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (BrokenPipeError, ConnectionResetError):
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动视频下载操作台本地服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    if not WEB_DIR.is_dir():
        parser.error(f"找不到网页目录: {WEB_DIR}")
    url = f"http://{args.host}:{args.port}/"
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"ok": True, "url": url}, ensure_ascii=False), flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
