#!/usr/bin/env python3
"""Resolve and download public Bilibili videos without account credentials."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
VIEW_API = "https://api.bilibili.com/x/web-interface/view"
PLAYURL_API = "https://api.bilibili.com/x/player/playurl"
MAX_METADATA_BYTES = 5 * 1024 * 1024
MEDIA_HOST_SUFFIXES = ("bilivideo.com", "bilivideo.cn", "akamaized.net")
QUALITY_NAMES = {
    127: "8K",
    126: "杜比视界",
    125: "HDR",
    120: "4K",
    116: "1080P60",
    112: "1080P+",
    80: "1080P",
    74: "720P60",
    64: "720P",
    32: "480P",
    16: "360P",
    6: "240P",
}


class DownloaderError(RuntimeError):
    """A user-facing resolution or download failure."""


def request_bytes(
    url: str,
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    max_bytes: int | None = None,
) -> tuple[bytes, str]:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            if max_bytes is None:
                return response.read(), response.geturl()
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise DownloaderError("Bilibili 响应过大，已停止解析")
            return body, response.geturl()
    except HTTPError as exc:
        raise DownloaderError(f"Bilibili 请求失败：HTTP {exc.code}") from exc
    except URLError as exc:
        raise DownloaderError(f"Bilibili 请求失败：{exc.reason}") from exc


def request_json(url: str, timeout: float, referer: str = "https://www.bilibili.com/") -> dict[str, Any]:
    body, _ = request_bytes(
        url,
        timeout=timeout,
        headers={"Referer": referer},
        max_bytes=MAX_METADATA_BYTES,
    )
    try:
        payload = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise DownloaderError("Bilibili 接口未返回 JSON") from exc
    if not isinstance(payload, dict):
        raise DownloaderError("Bilibili 接口响应格式无效")
    if payload.get("code") != 0:
        message = payload.get("message") or payload.get("msg") or "未知错误"
        raise DownloaderError(f"Bilibili 接口错误：{message}")
    return payload


def validate_bilibili_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    allowed = (
        host == "bilibili.com"
        or host.endswith(".bilibili.com")
        or host == "b23.tv"
        or host.endswith(".b23.tv")
    )
    if parsed.scheme not in {"http", "https"} or not allowed:
        raise DownloaderError("仅支持 bilibili.com 或 b23.tv 的公开链接")
    return value.strip()


def parse_identity(value: str) -> tuple[str, str] | None:
    raw = value.strip()
    if re.fullmatch(r"\d+", raw):
        return "aid", raw
    match = re.search(r"(?i)(BV[0-9A-Za-z]+)", raw)
    if match:
        return "bvid", match.group(1)
    match = re.search(r"(?i)(?:^|/)av(\d+)(?:/|$|\?)", raw)
    if match:
        return "aid", match.group(1)
    return None


def resolve_input(value: str, timeout: float) -> tuple[str, str, str, int | None]:
    identity = parse_identity(value)
    page = None
    referer = "https://www.bilibili.com/"
    if urlsplit(value).scheme:
        validate_bilibili_url(value)
        referer = value
        query_page = parse_qs(urlsplit(value).query).get("p", [None])[0]
        if query_page and str(query_page).isdigit():
            page = int(query_page)
    if identity:
        return identity[0], identity[1], referer, page
    if not urlsplit(value).scheme:
        raise DownloaderError("无法从输入中识别 BV 号或 AV 号")
    _, final_url = request_bytes(
        value,
        timeout=timeout,
        headers={"Referer": "https://www.bilibili.com/"},
        max_bytes=MAX_METADATA_BYTES,
    )
    validate_bilibili_url(final_url)
    identity = parse_identity(final_url)
    if not identity:
        raise DownloaderError("短链接跳转后仍未找到 BV 号或 AV 号")
    query_page = parse_qs(urlsplit(final_url).query).get("p", [None])[0]
    if query_page and str(query_page).isdigit():
        page = int(query_page)
    return identity[0], identity[1], final_url, page


def get_video_info(kind: str, identity: str, timeout: float, referer: str) -> dict[str, Any]:
    payload = request_json(f"{VIEW_API}?{urlencode({kind: identity})}", timeout, referer)
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("pages"), list):
        raise DownloaderError("Bilibili 视频信息不完整")
    return data


def select_pages(
    pages: list[dict[str, Any]],
    *,
    url_page: int | None,
    requested_page: int | None,
    all_pages: bool,
) -> list[dict[str, Any]]:
    if all_pages and requested_page is not None:
        raise DownloaderError("--all-pages 与 --page 不能同时使用")
    if all_pages:
        return pages
    page_number = requested_page or url_page or 1
    if page_number < 1 or page_number > len(pages):
        raise DownloaderError(f"分 P 编号超出范围：共 {len(pages)} P")
    return [pages[page_number - 1]]


def normalize_media_url(value: str) -> str:
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlsplit(value)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise DownloaderError("Bilibili 返回了无效的媒体地址")
    if not any(host == suffix or host.endswith("." + suffix) for suffix in MEDIA_HOST_SUFFIXES):
        raise DownloaderError("媒体地址不属于受支持的 Bilibili CDN")
    return value


def resolve_page(
    *,
    kind: str,
    identity: str,
    page: dict[str, Any],
    referer: str,
    timeout: float,
) -> dict[str, Any]:
    cid = page.get("cid")
    if not isinstance(cid, int):
        raise DownloaderError("分 P 缺少有效 cid")
    play_identity_key = "avid" if kind == "aid" else kind
    params = {
        play_identity_key: identity,
        "cid": str(cid),
        "qn": "127",
        "fnval": "0",
        "fourk": "1",
        "platform": "html5",
        "high_quality": "1",
    }
    payload = request_json(f"{PLAYURL_API}?{urlencode(params)}", timeout, referer)
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("durl"), list) or not data["durl"]:
        raise DownloaderError("Bilibili 未返回可下载的单文件视频流")
    quality = int(data.get("quality", 0))
    streams = []
    for item in data["durl"]:
        if not isinstance(item, dict) or not isinstance(item.get("url"), str):
            continue
        streams.append(
            {
                "url": normalize_media_url(item["url"]),
                "bytes": int(item.get("size", 0)),
            }
        )
    if not streams:
        raise DownloaderError("Bilibili 未返回有效的媒体地址")
    return {
        "page": int(page.get("page", 1)),
        "part": str(page.get("part") or f"P{page.get('page', 1)}"),
        "cid": cid,
        "quality": quality,
        "quality_name": QUALITY_NAMES.get(quality, str(quality)),
        "format": str(data.get("format") or "mp4"),
        "streams": streams,
    }


def sanitize_filename(value: str, fallback: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", value).strip().rstrip(".")
    value = re.sub(r"\s+", " ", value)
    return value[:120] or fallback


def unique_destination(path: Path) -> Path:
    candidate = path
    counter = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem}-{counter}{path.suffix}")
        counter += 1
    return candidate


def stream_suffix(url: str, format_name: str) -> str:
    suffix = Path(urlsplit(url).path).suffix.lower()
    if suffix in {".mp4", ".flv"}:
        return suffix
    return ".flv" if "flv" in format_name.lower() else ".mp4"


def download_stream(
    *,
    stream: dict[str, Any],
    destination: Path,
    referer: str,
    timeout: float,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(destination)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = Request(
        stream["url"],
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Origin": "https://www.bilibili.com",
            "Range": "bytes=0-",
        },
    )
    downloaded = 0
    try:
        with urlopen(request, timeout=timeout) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
        partial.replace(destination)
    except (HTTPError, URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise DownloaderError(f"Bilibili 视频下载失败：{exc}") from exc
    return {"path": str(destination.resolve()), "bytes": downloaded}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="下载公开 Bilibili 视频的最高可用单文件版本")
    parser.add_argument("video", help="Bilibili 视频链接、短链接、BV 号或 AV 号")
    parser.add_argument("--page", type=int, help="指定分 P 编号")
    parser.add_argument("--all-pages", action="store_true", help="下载全部分 P")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "bilibili-videos")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--resolve-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.timeout <= 0:
        print(json.dumps({"ok": False, "error": "timeout 必须大于 0"}, ensure_ascii=False))
        return 2
    try:
        kind, identity, referer, url_page = resolve_input(args.video, args.timeout)
        info = get_video_info(kind, identity, args.timeout, referer)
        all_page_data = info["pages"]
        selected = select_pages(
            all_page_data,
            url_page=url_page,
            requested_page=args.page,
            all_pages=args.all_pages,
        )
        resolved = [
            resolve_page(
                kind=kind,
                identity=identity,
                page=page,
                referer=referer,
                timeout=args.timeout,
            )
            for page in selected
        ]
        result: dict[str, Any] = {
            "ok": True,
            "title": str(info.get("title") or identity),
            "bvid": str(info.get("bvid") or ""),
            "aid": int(info.get("aid", 0)),
            "available_pages": len(all_page_data),
            "pages": resolved,
            "downloads": [],
        }
        if not args.resolve_only:
            title = sanitize_filename(result["title"], identity)
            downloads = []
            for page in resolved:
                part = sanitize_filename(page["part"], f"P{page['page']}")
                for index, stream in enumerate(page["streams"], 1):
                    segment = f"-S{index:02d}" if len(page["streams"]) > 1 else ""
                    suffix = stream_suffix(stream["url"], page["format"])
                    filename = f"{title}-P{page['page']:02d}-{part}{segment}{suffix}"
                    download = download_stream(
                        stream=stream,
                        destination=args.output_dir / filename,
                        referer=referer,
                        timeout=args.timeout,
                    )
                    download.update(
                        {
                            "page": page["page"],
                            "part": page["part"],
                            "quality": page["quality"],
                            "quality_name": page["quality_name"],
                        }
                    )
                    downloads.append(download)
            result["downloads"] = downloads
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except DownloaderError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
