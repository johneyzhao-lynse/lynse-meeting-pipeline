import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.classifier.pipeline import classify_transcript
from runtime.classifier.report import write_classification_report


class ClassifierPipelineTest(unittest.TestCase):
    def test_low_confidence_falls_back_to_general_template(self):
        result = classify_transcript("嗯，先这样，回头再说。", rules_only=True, confidence_threshold=0.95)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.recommended_template, "general-meeting.md")
        self.assertIsNone(result.recommended_industry_prompt)

    def test_report_writes_without_full_transcript(self):
        result = classify_transcript("客户讨论理赔材料和保单审核。", rules_only=True)
        with TemporaryDirectory() as tmp:
            path = write_classification_report(result, Path(tmp), transcript_id="sample")
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("recommended_template", data)
        self.assertNotIn("客户讨论理赔材料和保单审核。", json.dumps(data, ensure_ascii=False))

    def test_product_release_meeting_does_not_fall_back_when_product_candidates_dominate(self):
        transcript = (
            "1.06版本功能评审会议，今天提审，提审服测完后更新。"
            "安卓上架、华为渠道沟通、用户反馈、版本发布计划和风险一起同步。"
        )
        result = classify_transcript(transcript, rules_only=True)
        self.assertFalse(result.fallback_used)
        self.assertIn(result.recommended_template, {"product-analysis.md", "requirements-review.md"})

    def test_classifier_auto_selects_industry_prompt(self):
        result = classify_transcript("客户说已经报案，理赔材料包括病历、发票、保单和审核进度。", rules_only=True)
        self.assertEqual(result.recommended_template, "insurance-claim-communication.md")
        self.assertIsNotNone(result.recommended_industry_prompt)
        self.assertTrue(result.recommended_industry_prompt.endswith(".md"))
        self.assertEqual(result.industry_labels, [])
        self.assertTrue(result.candidate_ranking.industries)
