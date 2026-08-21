import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "weibo_browser_resolver.py"
SPEC = importlib.util.spec_from_file_location("weibo_browser_resolver", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class WeiboBrowserResolverTests(unittest.TestCase):
    def test_accepts_public_weibo_https_url(self):
        value = "https://weibo.com/3505975850/ReejX8VHe"
        self.assertEqual(MODULE.validate_weibo_page_url(value), value)

    def test_rejects_insecure_or_untrusted_page(self):
        for value in ("http://weibo.com/123/post", "https://example.com/post"):
            with self.subTest(value=value), self.assertRaises(MODULE.BrowserResolutionError):
                MODULE.validate_weibo_page_url(value)

    def test_finds_installed_chromium(self):
        self.assertTrue(MODULE.find_chromium().is_file())


if __name__ == "__main__":
    unittest.main()
