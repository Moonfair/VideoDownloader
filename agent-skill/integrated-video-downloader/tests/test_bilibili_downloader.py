import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "bilibili_video_downloader.py"
SPEC = importlib.util.spec_from_file_location("bilibili_video_downloader", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class BilibiliDownloaderTests(unittest.TestCase):
    def test_parse_bvid_and_aid(self):
        self.assertEqual(MODULE.parse_identity("https://www.bilibili.com/video/BV1xx411c7mD"), ("bvid", "BV1xx411c7mD"))
        self.assertEqual(MODULE.parse_identity("https://www.bilibili.com/video/av19516333"), ("aid", "19516333"))
        self.assertEqual(MODULE.parse_identity("19516333"), ("aid", "19516333"))

    def test_play_api_uses_avid_for_av_identity(self):
        captured = {}

        def fake_request_json(url, timeout, referer):
            captured["url"] = url
            return {"code": 0, "data": {"quality": 16, "format": "mp4", "durl": [{"url": "https://upos.example.bilivideo.com/a.mp4", "size": 1}]}}

        original = MODULE.request_json
        MODULE.request_json = fake_request_json
        try:
            MODULE.resolve_page(kind="aid", identity="19516333", page={"cid": 1, "page": 1, "part": "P1"}, referer="https://www.bilibili.com/", timeout=1)
        finally:
            MODULE.request_json = original
        self.assertIn("avid=19516333", captured["url"])
        self.assertNotIn("aid=19516333", captured["url"])

    def test_selects_requested_page(self):
        pages = [{"page": 1}, {"page": 2}, {"page": 3}]
        self.assertEqual(
            MODULE.select_pages(pages, url_page=2, requested_page=None, all_pages=False),
            [{"page": 2}],
        )
        self.assertEqual(
            MODULE.select_pages(pages, url_page=None, requested_page=None, all_pages=True),
            pages,
        )

    def test_sanitizes_windows_filename(self):
        self.assertEqual(MODULE.sanitize_filename('a<b>:c"d/e\\f|g?h*', "fallback"), "abcdefgh")

    def test_accepts_bilibili_cdn(self):
        url = "https://upos-sz-mirrorcos.bilivideo.com/video.mp4"
        self.assertEqual(MODULE.normalize_media_url(url), url)

    def test_rejects_untrusted_cdn(self):
        with self.assertRaises(MODULE.DownloaderError):
            MODULE.normalize_media_url("https://example.com/video.mp4")


if __name__ == "__main__":
    unittest.main()
