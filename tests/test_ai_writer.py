import unittest
import sys
import types
from unittest.mock import patch

if "openai" not in sys.modules:
    openai_stub = types.ModuleType("openai")
    openai_stub.OpenAI = object
    sys.modules["openai"] = openai_stub

from modules.ai_writer import AIWriter
from modules.content_policy import ContentPolicyError


class AIWriterPolicyRetryTests(unittest.TestCase):
    def test_policy_failure_triggers_one_safe_rewrite(self):
        writer = AIWriter.__new__(AIWriter)
        writer._safe_rewrite = lambda **kwargs: "rewritten safe article"

        with patch(
            "modules.ai_writer.validate_article",
            side_effect=[ContentPolicyError("blocked article"), None],
        ) as validator:
            result = writer._enforce_policy_with_rewrite(
                title="人工智能工具的企业应用方法",
                content="unsafe draft",
                hot_title="人工智能工具",
                category="AI",
            )

        self.assertEqual(result, "rewritten safe article")
        self.assertEqual(validator.call_count, 2)


if __name__ == "__main__":
    unittest.main()
