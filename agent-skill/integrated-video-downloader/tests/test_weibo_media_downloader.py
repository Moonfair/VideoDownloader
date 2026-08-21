import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "weibo_media_downloader.py"
SPEC = importlib.util.spec_from_file_location("weibo_media_downloader", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class WeiboMediaDownloaderTests(unittest.TestCase):
    def test_accepts_official_https_cdn(self):
        value = "https://f.video.weibocdn.com/path/video.mp4?media_id=123"
        self.assertEqual(MODULE.validate_media_url(value), value)

    def test_rejects_untrusted_or_insecure_url(self):
        for value in ("https://example.com/video.mp4", "http://f.video.weibocdn.com/video.mp4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.validate_media_url(value)

    def test_builds_stable_media_name(self):
        value = "https://f.video.weibocdn.com/path/video.mp4?media_id=5333916383379507"
        self.assertEqual(MODULE.media_name(value, 1), "5333916383379507.mp4")


if __name__ == "__main__":
    unittest.main()
