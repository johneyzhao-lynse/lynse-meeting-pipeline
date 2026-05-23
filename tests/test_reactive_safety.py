import unittest

from runtime.failure_detector import classify_api_failure, classify_generation_failure
from runtime.safety import detect_safety_risks, should_apply_safety_constraints


class ReactiveSafetyTest(unittest.TestCase):
    def test_reactive_mode_does_not_apply_before_failure(self):
        self.assertFalse(should_apply_safety_constraints("reactive", ["political_public_issue"]))

    def test_refusal_like_output_is_retryable(self):
        failure = classify_generation_failure("抱歉，我无法处理或总结这类内容。")
        self.assertTrue(failure.retryable)
        self.assertEqual(failure.reason, "model_refusal")

    def test_valid_markdown_is_not_retryable(self):
        failure = classify_generation_failure("# 会议概览\n\n- 已完成总结。\n\n## 后续行动\n\n- 无")
        self.assertFalse(failure.retryable)

    def test_sensitive_api_failure_is_retryable(self):
        failure = classify_api_failure('DeepSeek API HTTP 400: {"error":{"code":"content_filter","message":"sensitive content"}}')
        self.assertTrue(failure.retryable)
        self.assertEqual(failure.reason, "sensitive_api_failure")

    def test_non_sensitive_api_failure_is_not_retryable(self):
        failure = classify_api_failure('DeepSeek API HTTP 500: {"error":{"code":"server_error","message":"internal error"}}')
        self.assertFalse(failure.retryable)

    def test_platform_review_terms_are_not_sensitive_precheck(self):
        risks = detect_safety_risks("版本提审、应用商店审核、上架、下架风险和平台反馈。")
        self.assertEqual(risks, [])

    def test_defined_sensitive_categories_are_detected(self):
        risks = detect_safety_risks("讨论台湾政治相关内容、中国国家领导人名字、自杀引导和辱骂粗口。")
        self.assertIn("cn_political_sensitive", risks)
        self.assertIn("self_harm_guidance", risks)
        self.assertIn("abusive_or_profane", risks)
