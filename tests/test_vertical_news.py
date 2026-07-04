import unittest

from modules.hot_search import _parse_rss
from modules.keyword_filter import filter_items


RSS = b'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>AI agents improve export customer service - Example News</title>
    <link>https://example.com/ai-export</link>
    <description><![CDATA[<b>Useful</b> source summary]]></description>
    <source>Example News</source>
    <pubDate>Sat, 04 Jul 2026 08:00:00 GMT</pubDate>
  </item>
</channel></rss>'''


class VerticalNewsTests(unittest.TestCase):
    def test_rss_parser_sets_category_hint_and_cleans_fields(self):
        items = _parse_rss(RSS, "Google新闻", "AI")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "AI agents improve export customer service")
        self.assertEqual(items[0]["summary"], "Useful source summary")
        self.assertEqual(items[0]["hint_category"], "AI")

    def test_vertical_hint_does_not_bypass_exclusion_policy(self):
        result = filter_items([
            {"title": "AI足球比赛奖金曝光", "hint_category": "AI"},
            {"title": "大模型帮助外贸客服提效", "hint_category": "AI"},
        ])
        self.assertEqual([item["title"] for item in result["AI"]], ["大模型帮助外贸客服提效"])

    def test_vertical_hint_keeps_relevant_business_story(self):
        result = filter_items([
            {"title": "海外仓运营成本出现新变化", "hint_category": "跨境电商"},
        ])
        self.assertEqual(len(result["跨境电商"]), 1)

    def test_vertical_hint_cannot_force_an_unrelated_story_into_a_category(self):
        result = filter_items([
            {"title": "某企业发布年度品牌计划", "hint_category": "AI"},
        ])
        self.assertEqual(len(result["AI"]), 0)

    def test_customs_enforcement_story_is_not_foreign_trade_news(self):
        result = filter_items([
            {"title": "海关查获旅客藏匿活体龟", "hint_category": "外贸"},
        ])
        self.assertEqual(len(result["外贸"]), 0)


if __name__ == "__main__":
    unittest.main()
