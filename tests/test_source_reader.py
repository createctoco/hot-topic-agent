import unittest
import sys
import types
import json
from unittest.mock import Mock, patch

if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub

from modules.source_reader import fetch_source


class FakeResponse:
    def __init__(self, body: str, content_type: str, status_code: int = 200, headers=None):
        self._body = body.encode("utf-8")
        self.status_code = status_code
        self.headers = {"Content-Type": content_type, **(headers or {})}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=32768):
        yield self._body


class SourceReaderTests(unittest.TestCase):
    @patch("modules.source_reader._is_public_host", return_value=True)
    def test_extracts_article_html(self, _public_host):
        paragraphs = "".join(
            f"<p>第{i}段介绍人工智能工具在企业流程中的实际应用方法，并说明操作边界。</p>"
            for i in range(1, 9)
        )
        session = Mock()
        session.get.return_value = FakeResponse(
            f"<html><nav>导航内容</nav><article><h1>企业人工智能应用</h1>{paragraphs}</article></html>",
            "text/html; charset=utf-8",
        )

        result = fetch_source("https://example.com/article", session=session)

        self.assertEqual(result["status"], "ok")
        self.assertIn("企业人工智能应用", result["text"])
        self.assertNotIn("导航内容", result["text"])

    @patch("modules.source_reader._is_public_host", return_value=True)
    def test_extracts_json_content(self, _public_host):
        body = json.dumps({
            "data": {
                "title": "跨境电商物流观察",
                "content": "跨境卖家需要核对物流时效、清关材料和售后流程。" * 20,
            }
        }, ensure_ascii=False)
        session = Mock()
        session.get.return_value = FakeResponse(body, "application/json; charset=utf-8")

        result = fetch_source("https://api.example.com/article/1", session=session)

        self.assertEqual(result["status"], "ok")
        self.assertIn("跨境电商物流观察", result["text"])
        self.assertIn("清关材料", result["text"])

    @patch("modules.source_reader._is_public_host", return_value=False)
    def test_blocks_non_public_source(self, _public_host):
        session = Mock()

        result = fetch_source("http://127.0.0.1/internal", session=session)

        self.assertEqual(result["status"], "unavailable")
        self.assertIn("non-public", result["error"])
        session.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
