import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "server.py"
SPEC = importlib.util.spec_from_file_location("video_server", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ServerTests(unittest.TestCase):
    def test_allows_pages_and_loopback_origins(self):
        self.assertEqual(MODULE.allowed_origin("https://moonfair.github.io"), "https://moonfair.github.io")
        self.assertEqual(MODULE.allowed_origin("http://127.0.0.1:8765"), "http://127.0.0.1:8765")
        self.assertIsNone(MODULE.allowed_origin("https://example.com"))

    def test_builds_bilibili_arguments(self):
        platform, arguments = MODULE.build_arguments({
            "input": "BV1xx411c7mD",
            "platform": "bilibili",
            "timeout": 30,
            "page": 2,
        }, Path("videos"), resolve_only=False)
        self.assertEqual(platform, "bilibili")
        self.assertEqual(arguments, ["BV1xx411c7mD", "--page", "2", "--timeout", "30", "--output-dir", "videos"])

    def test_weibo_requires_official_media_url(self):
        with self.assertRaisesRegex(ValueError, "浏览器解析器"):
            MODULE.build_arguments({
                "input": "https://weibo.com/123/post",
                "platform": "weibo",
            }, Path("videos"), resolve_only=False)

    def test_accepts_browser_resolved_weibo_media(self):
        platform, arguments = MODULE.build_arguments({
            "input": "https://weibo.com/123/post",
            "platform": "weibo",
            "timeout": 30,
        }, Path("videos"), resolve_only=True, weibo_media_urls=["https://f.video.weibocdn.com/video.mp4"])
        self.assertEqual(platform, "weibo")
        self.assertEqual(arguments[:2], ["--media-url", "https://f.video.weibocdn.com/video.mp4"])


if __name__ == "__main__":
    unittest.main()
