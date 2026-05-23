import unittest

from runtime.classifier.rules import INDUSTRY_IGNORED_SENSITIVE_TERMS, extract_features, rank_candidates


class ClassifierRulesTest(unittest.TestCase):
    def test_insurance_claim_text_ranks_insurance_claim_template(self):
        transcript = "客户说已经报案，理赔材料包括病历、发票、保单和审核进度，需要补充诊断证明。"
        features = extract_features(transcript)
        ranked = rank_candidates(features)
        self.assertEqual(ranked.templates[0].name, "insurance-claim-communication.md")
        self.assertEqual(ranked.industries[0].name, "insurance-industry.md")

    def test_unclear_personal_note_keeps_general_template_candidate(self):
        transcript = "今天想到几个事情，后面再整理，先记一下灵感和待办。"
        features = extract_features(transcript)
        ranked = rank_candidates(features)
        names = [item.name for item in ranked.templates]
        self.assertIn("general-meeting.md", names)

    def test_product_release_review_ranks_product_templates_without_sensitive_industry(self):
        transcript = (
            "1.06版本功能评审会议，今天提审，提审服测完后更新。"
            "安卓上架、华为渠道沟通、用户反馈、版本发布计划和风险一起同步。"
        )
        features = extract_features(transcript)
        ranked = rank_candidates(features)
        top_names = [item.name for item in ranked.templates[:3]]
        self.assertTrue(
            any(name in top_names for name in ["product-analysis.md", "requirements-review.md"]),
            top_names,
        )
        industry_names = [item.name for item in ranked.industries]
        self.assertNotIn("sensitive-content-neutral-summary.md", industry_names)

    def test_industry_sensitive_ignore_list_does_not_include_platform_review_terms(self):
        for term in ["审核", "下架", "上架", "风险", "平台", "政府"]:
            self.assertNotIn(term, INDUSTRY_IGNORED_SENSITIVE_TERMS)

    def test_industry_ranking_ignores_only_real_sensitive_terms(self):
        transcript = "敏感 台湾 独立 领导人 政党 选举 自杀 轻生 粗口 辱骂"
        features = extract_features(transcript)
        ranked = rank_candidates(features)
        self.assertEqual(ranked.industries, [])

    def test_industry_sensitive_ignore_list_includes_defined_sensitive_categories(self):
        for term in ["台湾", "台独", "领导人", "自杀", "轻生", "辱骂", "粗口"]:
            self.assertIn(term, INDUSTRY_IGNORED_SENSITIVE_TERMS)
