#!/usr/bin/env python3
"""Resolve public Weibo video URLs through an isolated Chromium DevTools session."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class BrowserResolutionError(RuntimeError):
    """A user-facing browser resolution failure."""


def validate_weibo_page_url(value: str) -> str:
    parsed = urlparse(value.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not (
        host == "weibo.com"
        or host.endswith(".weibo.com")
        or host == "weibo.cn"
        or host.endswith(".weibo.cn")
    ):
        raise BrowserResolutionError("仅支持公开的 weibo.com 或 weibo.cn HTTPS 链接")
    return value.strip()


def find_chromium() -> Path:
    candidates: list[str | Path] = []
    if sys.platform == "win32":
        candidates.extend(
            [
                Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)"))
                / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                / "Microsoft/Edge/Application/msedge.exe",
                Path(os.environ.get("PROGRAMFILES", "C:/Program Files"))
                / "Google/Chrome/Application/chrome.exe",
                Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
            ]
        )
    candidates.extend(("msedge", "microsoft-edge", "google-chrome", "chromium", "chromium-browser"))
    for candidate in candidates:
        path = Path(candidate) if isinstance(candidate, Path) else Path(shutil.which(candidate) or "")
        if path.is_file():
            return path
    raise BrowserResolutionError("未找到 Edge、Chrome 或 Chromium，无法自动解析微博公开页面")


class DevToolsSocket:
    def __init__(self, url: str, timeout: float):
        parsed = urlparse(url)
        if parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise BrowserResolutionError("浏览器调试地址无效")
        self.socket = socket.create_connection((parsed.hostname, parsed.port or 80), timeout=timeout)
        self.socket.settimeout(timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port or 80}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode("ascii")
        self.socket.sendall(request)
        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = self.socket.recv(4096)
            if not chunk:
                raise BrowserResolutionError("浏览器调试连接提前关闭")
            response.extend(chunk)
            if len(response) > 64 * 1024:
                raise BrowserResolutionError("浏览器调试握手响应过大")
        header, self.buffer = bytes(response).split(b"\r\n\r\n", 1)
        if not header.startswith(b"HTTP/1.1 101"):
            raise BrowserResolutionError("浏览器拒绝调试连接")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if expected.lower() not in header.lower():
            raise BrowserResolutionError("浏览器调试握手校验失败")
        self.next_id = 1

    def _read_exact(self, size: int) -> bytes:
        output = bytearray()
        if self.buffer:
            taken = self.buffer[:size]
            output.extend(taken)
            self.buffer = self.buffer[len(taken):]
        while len(output) < size:
            chunk = self.socket.recv(size - len(output))
            if not chunk:
                raise BrowserResolutionError("浏览器调试连接已关闭")
            output.extend(chunk)
        return bytes(output)

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        mask = secrets.token_bytes(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.socket.sendall(bytes(header) + masked)

    def send_json(self, payload: dict[str, Any]) -> None:
        self._send_frame(0x1, json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    def receive_json(self) -> dict[str, Any]:
        message = bytearray()
        started = False
        while True:
            first, second = self._read_exact(2)
            final = bool(first & 0x80)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            if second & 0x80:
                mask = self._read_exact(4)
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(self._read_exact(length)))
            else:
                payload = self._read_exact(length)
            if opcode == 0x8:
                raise BrowserResolutionError("浏览器调试连接已关闭")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x1:
                message = bytearray(payload)
                started = True
            elif opcode == 0x0 and started:
                message.extend(payload)
            else:
                continue
            if final:
                return json.loads(message.decode("utf-8"))

    def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        call_id = self.next_id
        self.next_id += 1
        self.send_json({"id": call_id, "method": method, "params": params or {}})
        while True:
            response = self.receive_json()
            if response.get("id") == call_id:
                if "error" in response:
                    raise BrowserResolutionError(str(response["error"].get("message") or "浏览器命令失败"))
                return response.get("result") or {}

    def close(self) -> None:
        try:
            self._send_frame(0x8, b"")
        except OSError:
            pass
        self.socket.close()


def wait_for_debug_port(profile: Path, process: subprocess.Popen[bytes], timeout: float) -> int:
    port_file = profile / "DevToolsActivePort"
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise BrowserResolutionError("浏览器启动失败")
        try:
            first_line = port_file.read_text(encoding="utf-8").splitlines()[0]
            return int(first_line)
        except (OSError, ValueError, IndexError):
            time.sleep(0.1)
    raise BrowserResolutionError("等待浏览器启动超时")


def get_page_socket(port: int, timeout: float) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/json/list", timeout=1) as response:
                targets = json.load(response)
            for target in targets:
                if target.get("type") == "page" and isinstance(target.get("webSocketDebuggerUrl"), str):
                    return target["webSocketDebuggerUrl"]
        except (OSError, ValueError):
            time.sleep(0.1)
    raise BrowserResolutionError("无法取得浏览器页面调试地址")


def resolve_weibo_media(value: str, timeout: float = 30.0) -> list[str]:
    url = validate_weibo_page_url(value)
    browser = find_chromium()
    profile = Path(tempfile.mkdtemp(prefix="video-downloader-browser-"))
    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    process = subprocess.Popen(
        [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-sync",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-port=0",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    client: DevToolsSocket | None = None
    try:
        port = wait_for_debug_port(profile, process, min(timeout, 10))
        client = DevToolsSocket(get_page_socket(port, min(timeout, 10)), timeout=max(timeout, 10))
        client.call("Page.enable")
        client.call("Runtime.enable")
        client.call("Page.navigate", {"url": url})
        deadline = time.monotonic() + max(timeout, 15)
        expression = "JSON.stringify([...new Set([...document.querySelectorAll('video')].map(v=>v.currentSrc||v.src).filter(Boolean))])"
        while time.monotonic() < deadline:
            result = client.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            raw = result.get("result", {}).get("value", "[]")
            try:
                urls = json.loads(raw)
            except (TypeError, json.JSONDecodeError):
                urls = []
            if isinstance(urls, list) and all(isinstance(item, str) for item in urls) and urls:
                return list(dict.fromkeys(urls))
            time.sleep(0.5)
        raise BrowserResolutionError("公开页面已加载，但未发现可下载的视频媒体地址")
    finally:
        if client:
            try:
                client.call("Browser.close")
            except (OSError, BrowserResolutionError, socket.timeout):
                pass
            client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        for _ in range(20):
            try:
                shutil.rmtree(profile)
                break
            except OSError:
                time.sleep(0.1)


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="通过隔离浏览器解析公开微博视频地址")
    parser.add_argument("url")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args(argv)
    try:
        print(json.dumps({"ok": True, "media": resolve_weibo_media(args.url, args.timeout)}, ensure_ascii=False, indent=2))
        return 0
    except BrowserResolutionError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
