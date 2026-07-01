import unittest

from modules.content_policy import ContentPolicyError, validate_article, validate_topic
from modules.keyword_filter import exclude_published_topics, select_topics


class ContentPolicyTests(unittest.TestCase):
    def test_allows_safe_technology_topic(self):
        validate_topic("固态电池量产路线有哪些变化", "科技")

    def test_blocks_politics_and_military_topics(self):
        for title in ("总统讨论新的科技政策", "新型导弹技术公开"):
            with self.subTest(title=title):
                with self.assertRaises(ContentPolicyError):
                    validate_topic(title, "科技")

    def test_blocks_country_denigration(self):
        with self.assertRaises(ContentPolicyError):
            validate_topic("所谓中国崩溃论影响跨境卖家", "跨境电商")

    def test_rejects_short_or_empty_article(self):
        with self.assertRaises(ContentPolicyError):
            validate_article("AI客服如何降低响应时间", "内容很短。", "AI")

    def test_published_topic_is_removed_before_selection(self):
        filtered = {
            "跨境电商": [],
            "外贸": [],
            "AI": [
                {"title": "已发布话题", "category": "AI", "platform": "test"},
                {"title": "新的安全话题", "category": "AI", "platform": "test"},
            ],
            "科技": [],
        }
        eligible = exclude_published_topics(filtered, {"已发布话题"})
        selected = select_topics(eligible, 1)
        self.assertEqual([item["title"] for item in selected], ["新的安全话题"])


if __name__ == "__main__":
    unittest.main()
