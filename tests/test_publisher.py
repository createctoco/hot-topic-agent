import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.publisher import ToutiaoPublisher


class PublisherTests(unittest.TestCase):
    def make_publisher(self):
        publisher = ToutiaoPublisher(work_dir=".", validate_environment=False)
        publisher._supported_opts = {
            "title",
            "content-file",
            "format",
            "cover-free",
            "cover-keyword",
            "first-publish",
            "declaration",
            "headless",
        }
        return publisher

    def test_extracts_last_json_after_log_lines(self):
        output = 'starting\n{"status":"working"}\n{"success":true,"action":"published"}\n'
        self.assertEqual(
            ToutiaoPublisher._extract_last_json(output),
            {"success": True, "action": "published"},
        )

    def test_extracts_outer_json_instead_of_nested_object(self):
        output = 'log\n{"success":true,"result":{"id":123}}\n'
        self.assertEqual(
            ToutiaoPublisher._extract_last_json(output),
            {"success": True, "result": {"id": 123}},
        )

    def test_login_uses_structured_logged_in_value(self):
        publisher = self.make_publisher()
        with patch.object(
            publisher,
            "_run_toutiao_cmd",
            return_value={"success": True, "data": {"logged_in": True}},
        ):
            self.assertTrue(publisher.check_login())

    def test_zero_exit_without_publish_confirmation_is_failure(self):
        publisher = self.make_publisher()
        fake = {
            "success": True,
            "output": '{"success":true}',
            "data": {"success": True},
        }
        with patch.object(publisher, "_run_toutiao_cmd", return_value=fake):
            result = publisher.publish_article("A valid title", "<p>body</p>")
        self.assertFalse(result["success"])

    def test_confirmed_publish_is_success(self):
        publisher = self.make_publisher()
        fake = {
            "success": True,
            "output": '{"success":true,"action":"published","url":"https://mp.toutiao.com/content"}',
            "data": {
                "success": True,
                "action": "published",
                "url": "https://mp.toutiao.com/content",
            },
        }
        with patch.object(publisher, "_run_toutiao_cmd", return_value=fake):
            result = publisher.publish_article("A valid title", "<p>body</p>")
        self.assertTrue(result["success"])
        self.assertEqual(result["url"], "https://mp.toutiao.com/content")

    def test_uses_free_library_with_keyword_when_no_local_cover_is_configured(self):
        publisher = self.make_publisher()
        publisher._supported_opts.update({"cover-mode", "cover-keyword"})
        fake = {
            "success": True,
            "output": '{"success":true,"action":"published"}',
            "data": {"success": True, "action": "published"},
        }
        with patch.object(publisher, "_run_toutiao_cmd", return_value=fake) as runner:
            result = publisher.publish_article(
                "A valid title", "<p>body</p>", cover_keyword="人工智能"
            )
        args = runner.call_args.args[0]
        self.assertTrue(result["success"])
        self.assertIn("--cover-mode", args)
        self.assertEqual(args[args.index("--cover-mode") + 1], "free")
        self.assertEqual(args[args.index("--cover-keyword") + 1], "人工智能")
        self.assertNotIn("--cover-free", args)

    def test_declares_network_source_and_ai_participation(self):
        publisher = self.make_publisher()
        fake = {
            "success": True,
            "output": '{"success":true,"action":"published"}',
            "data": {"success": True, "action": "published"},
        }
        with patch.object(publisher, "_run_toutiao_cmd", return_value=fake) as runner:
            publisher.publish_article("A valid title", "<p>body</p>")
        args = runner.call_args.args[0]
        self.assertIn("--declaration", args)
        self.assertEqual(args[args.index("--declaration") + 1], "取材网络,引用AI")


if __name__ == "__main__":
    unittest.main()
