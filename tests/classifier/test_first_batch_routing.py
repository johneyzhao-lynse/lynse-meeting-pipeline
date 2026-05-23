import unittest

from runtime.assets import TRANSCRIPT_DIR, read_text
from runtime.classifier.pipeline import classify_transcript
from runtime.classifier.rules import extract_features


class FirstBatchRoutingTest(unittest.TestCase):
    def classify_file(self, filename):
        return classify_transcript(read_text(TRANSCRIPT_DIR / filename), rules_only=True)

    def test_government_design_competition_routes_to_government_template_and_industry(self):
        result = self.classify_file("05-19 政府类：北新泾新朝阳地区城市设计国际征集.txt")
        industry_names = [item.name for item in result.candidate_ranking.industries]

        self.assertEqual(result.recommended_template, "government-project-bidding.md")
        self.assertEqual(industry_names[0], "government-project-industry.md")

    def test_technical_interview_routes_to_interview_template(self):
        result = self.classify_file("技术岗位候选人面试会议纪要.txt")

        self.assertEqual(result.recommended_template, "technical-interview-summary.md")

    def test_web_frontend_interview_routes_to_interview_template(self):
        result = self.classify_file("01月27日 技术岗面试会议纪要：Web前端工程师.txt")

        self.assertEqual(result.recommended_template, "technical-interview-summary.md")

    def test_sales_negotiation_routes_to_sales_follow_up(self):
        result = self.classify_file("04-27 销售：京东DRP收费与AWS合作谈判.txt")

        self.assertEqual(result.recommended_template, "sales-follow-up.md")
        self.assertFalse(result.fallback_used)

    def test_marketing_business_model_routes_to_marketing_template(self):
        result = self.classify_file("05-08 营销：沉浸式剧场商业模式探讨.txt")

        self.assertEqual(result.recommended_template, "marketing-campaign-planning.md")
        self.assertFalse(result.fallback_used)

    def test_exported_title_line_is_not_used_as_classifier_evidence(self):
        features = extract_features("技术岗位候选人面试会议纪要\n[00:00:01] 发言人0:\n你好，介绍一下经历。")

        self.assertNotIn("技术岗位候选人面试会议纪要", features.transcript)
        self.assertNotIn("面试", features.keyword_hits)


if __name__ == "__main__":
    unittest.main()
