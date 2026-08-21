import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "scripts" / "video_downloader.py"
SPEC = importlib.util.spec_from_file_location("video_downloader", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class PlatformDetectionTests(unittest.TestCase):
    def test_detects_weibo_url(self):
        self.assertEqual(MODULE.detect_platform(["https://weibo.com/7299853661/Re4Jq7l0U"]), "weibo")

    def test_detects_bilibili_inputs(self):
        for value in ("https://www.bilibili.com/video/BV1xx411c7mD", "BV1xx411c7mD", "av170001", "170001"):
            with self.subTest(value=value):
                self.assertEqual(MODULE.detect_platform([value]), "bilibili")

    def test_media_url_selects_weibo(self):
        self.assertEqual(MODULE.detect_platform(["--media-url", "https://example.test/video.mp4"]), "weibo")

    def test_unknown_input_requires_explicit_platform(self):
        with self.assertRaises(ValueError):
            MODULE.detect_platform(["not-a-video"])


class DispatcherTests(unittest.TestCase):
    @patch.object(MODULE, "resolve_weibo_media", return_value=["https://f.video.weibocdn.com/video.mp4"])
    @patch.object(MODULE.subprocess, "run")
    def test_resolves_weibo_page_before_forwarding(self, run, resolve):
        run.return_value.returncode = 7
        result = MODULE.main(["--platform", "weibo", "https://weibo.com/example", "--resolve-only"])
        command = run.call_args.args[0]
        self.assertEqual(result, 7)
        resolve.assert_called_once_with("https://weibo.com/example", 30.0)
        self.assertEqual(command[:2], [sys.executable, "-S"])
        self.assertTrue(command[2].endswith("weibo_media_downloader.py"))
        self.assertEqual(command[3:], ["--resolve-only", "--media-url", "https://f.video.weibocdn.com/video.mp4"])


if __name__ == "__main__":
    unittest.main()
