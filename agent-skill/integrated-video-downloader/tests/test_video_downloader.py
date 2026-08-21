import importlib.util
import json
import sys
import tempfile
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
    @patch.object(MODULE.subprocess, "run")
    def test_forwards_arguments_and_exit_code(self, run):
        run.return_value.returncode = 7
        result = MODULE.main(["--platform", "weibo", "https://weibo.com/example", "--resolve-only"])
        command = run.call_args.args[0]
        self.assertEqual(result, 7)
        self.assertEqual(command[:2], [sys.executable, "-S"])
        self.assertTrue(command[2].endswith("weibo_media_downloader.py"))
        self.assertEqual(command[3:], ["https://weibo.com/example", "--resolve-only"])


class TaskFileTests(unittest.TestCase):
    def write_task(self, task):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "task.json"
        path.write_text(json.dumps(task), encoding="utf-8")
        return directory, path

    def test_builds_bilibili_download_arguments(self):
        directory, path = self.write_task({
            "schema": MODULE.TASK_SCHEMA,
            "input": "BV1xx411c7mD",
            "platform": "bilibili",
            "action": "download",
            "outputDir": "videos",
            "timeout": 45,
            "page": 2,
        })
        self.addCleanup(directory.cleanup)
        platform, arguments = MODULE.load_task(path)
        self.assertEqual(platform, "bilibili")
        self.assertEqual(arguments, ["BV1xx411c7mD", "--output-dir", "videos", "--timeout", "45", "--page", "2"])

    def test_rejects_unknown_schema(self):
        directory, path = self.write_task({"schema": "unknown", "input": "BV1xx411c7mD"})
        self.addCleanup(directory.cleanup)
        with self.assertRaisesRegex(ValueError, "schema"):
            MODULE.load_task(path)

    def test_rejects_platform_specific_arguments(self):
        directory, path = self.write_task({
            "schema": MODULE.TASK_SCHEMA,
            "input": "https://weibo.com/example",
            "platform": "weibo",
            "page": 2,
        })
        self.addCleanup(directory.cleanup)
        with self.assertRaisesRegex(ValueError, "仅适用于 Bilibili"):
            MODULE.load_task(path)


if __name__ == "__main__":
    unittest.main()
