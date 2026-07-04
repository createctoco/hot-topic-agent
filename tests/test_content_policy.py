import unittest

from modules.content_policy import (
    ContentPolicyError,
    sanitize_article_content,
    validate_article,
    validate_generated_title,
    validate_topic,
)
from modules.keyword_filter import exclude_published_topics, select_topics


class ContentPolicyTests(unittest.TestCase):
    def test_allows_safe_ai_topic(self):
        validate_topic("大语言模型如何改进外贸客服", "AI")

    def test_rejects_removed_technology_category(self):
        with self.assertRaises(ContentPolicyError):
            validate_topic("固态电池量产路线有哪些变化", "科技")

    def test_blocks_politics_and_military_topics(self):
        for title in ("总统讨论新的AI政策", "新型导弹技术公开"):
            with self.subTest(title=title):
                with self.assertRaises(ContentPolicyError):
                    validate_topic(title, "AI")

    def test_blocks_country_denigration(self):
        with self.assertRaises(ContentPolicyError):
            validate_topic("所谓中国崩溃论影响跨境卖家", "跨境电商")

    def test_blocks_hype_and_fictional_hooks(self):
        for title in ("AI行业惊现新内幕", "硅谷叶文洁出现了"):
            with self.subTest(title=title):
                with self.assertRaises(ContentPolicyError):
                    validate_topic(title, "AI")

    def test_entertainment_event_does_not_enter_technology(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("霉霉婚礼禁用手机"))

    def test_sports_prize_is_not_foreign_trade(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("佛得角队收获1100万美元赛事奖金"))

    def test_generic_consumer_technology_is_not_selected(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("苹果发布新款折叠屏手机"))

    def test_ai_entertainment_is_not_selected(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("AI配音漫剧成为热门作品"))

    def test_airpods_does_not_match_ai_abbreviation(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("摄像头AirPods Pro项目暂停"))
        self.assertEqual(match_category("AI芯片推动大模型推理降本"), "AI")

    def test_unverified_exposure_topic_is_not_selected(self):
        from modules.keyword_filter import match_category

        self.assertIsNone(match_category("曝某公司将全面禁用Claude"))

    def test_valid_business_topics_are_selected(self):
        from modules.keyword_filter import match_category

        self.assertEqual(match_category("人民币汇率波动影响外贸出口报价"), "外贸")
        self.assertEqual(match_category("DeepSeek发布新一代大模型"), "AI")
        self.assertEqual(match_category("亚马逊跨境卖家调整海外仓"), "跨境电商")

    def test_rejects_short_or_empty_article(self):
        with self.assertRaises(ContentPolicyError):
            validate_article("AI客服如何降低响应时间", "内容很短。", "AI")

    def test_large_language_model_is_not_ai_meta_commentary(self):
        paragraphs = [
            f"第{i}部分分析大语言模型在外贸客服中的应用方法。第{i}项环节需要核对输入内容。企业还应保留第{i}项人工复核流程。"
            for i in range(30)
        ]
        validate_article("大语言模型改善外贸客服", "\n".join(paragraphs), "AI")

    def test_sanitizer_removes_blocked_and_unsourced_passages(self):
        content = "\n".join([
            "AI客服可以先处理常见产品问题，再交给人工复核。",
            "政府将推动相关企业在2027年增长超过30%。",
            "外贸团队应记录客户问题并持续更新知识库。",
        ])
        sanitized = sanitize_article_content(content)
        self.assertIn("AI客服", sanitized)
        self.assertIn("外贸团队", sanitized)
        self.assertNotIn("政府", sanitized)
        self.assertNotIn("2027年", sanitized)

    def test_rejects_unsupported_report_claims(self):
        paragraphs = [f"第{i}部分说明一个完整且不同的业务流程，并给出可执行检查步骤。" for i in range(25)]
        content = "\n".join(paragraphs) + "\n据行业报告，2024年相关企业增长超过30%。"
        with self.assertRaises(ContentPolicyError):
            validate_article("AI客服如何降低响应时间", content, "AI")

    def test_accepts_factual_claims_present_in_source_evidence(self):
        paragraphs = [
            f"第{i}部分说明一个完整且不同的企业业务流程，并解释这一环节的执行方法。第{i}项核对步骤用于识别输入错误和边界条件。第{i}项执行记录用于后续复盘和持续改进。"
            for i in range(30)
        ]
        content = "\n".join(paragraphs) + "\n来源材料显示，2024年相关业务增长超过30%。"
        evidence = "公开来源材料显示，2024年相关业务增长超过30%。"
        validate_article("AI客服如何降低响应时间", content, "AI", evidence)

    def test_rejects_unsupported_numeric_ranges(self):
        paragraphs = [f"第{i}部分说明企业未来3至5年的技术规划和通用方法。" for i in range(25)]
        with self.assertRaises(ContentPolicyError):
            validate_article("人工智能应用方法", "\n".join(paragraphs), "AI")

    def test_generated_title_cannot_invent_a_percentage(self):
        with self.assertRaises(ContentPolicyError):
            validate_generated_title(
                "中端模型涨价，用户成本增加20%",
                "AI",
                "中端模型发布变相涨价版本",
            )

    def test_generated_title_can_retain_a_sourced_percentage(self):
        validate_generated_title(
            "中端模型涨价20%",
            "AI",
            "中端模型价格上涨20%",
        )

    def test_published_topic_is_removed_before_selection(self):
        filtered = {
            "跨境电商": [],
            "外贸": [],
            "AI": [
                {"title": "已发布话题", "category": "AI", "platform": "test"},
                {"title": "新的安全话题", "category": "AI", "platform": "test"},
            ],
        }
        eligible = exclude_published_topics(filtered, {"已发布话题"})
        selected = select_topics(eligible, 1)
        self.assertEqual([item["title"] for item in selected], ["新的安全话题"])


if __name__ == "__main__":
    unittest.main()
