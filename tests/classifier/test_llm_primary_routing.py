from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from runtime.agent.config import AgentConfig, CallParams
from runtime.classifier.models import Candidate, CandidateRanking, TranscriptFeatures
from runtime.classifier.pipeline import _should_use_llm, classify_transcript


def _make_features(**overrides) -> TranscriptFeatures:
    defaults = {
        "transcript": "测试转写文本内容",
        "char_count": 100,
        "speaker_count": 2,
        "keyword_hits": {"会议": 3, "讨论": 2},
        "head_snippet": "开头内容",
        "tail_snippet": "结尾内容",
        "key_windows": [],
    }
    defaults.update(overrides)
    return TranscriptFeatures(**defaults)


def _make_ranking() -> CandidateRanking:
    return CandidateRanking(
        templates=[
            Candidate(name="product-analysis.md", score=10.0, matched_keywords=["产品"]),
            Candidate(name="general-meeting.md", score=5.0, matched_keywords=["会议"]),
        ],
        industries=[
            Candidate(name="marketing-industry.md", score=5.0, matched_keywords=["营销"]),
        ],
    )


def _make_reasoning_config() -> AgentConfig:
    return AgentConfig(
        api_key_value="sk-test",
        model="test-reasoning-model",
        base_url="https://llm.test",
        call_params=CallParams(
            thinking="disabled",
            max_tokens=1000,
            temperature=0.1,
        ),
    )


def _make_llm_response(template="product-analysis.md", confidence=0.88,
                        scene_labels=None, intent_labels=None, industry=None):
    if scene_labels is None:
        scene_labels = ["技术讨论"]
    if intent_labels is None:
        intent_labels = ["问题诊断"]
    return {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "recommended_template": template,
                    "industry_suggestion": industry,
                    "confidence": confidence,
                    "reason": "测试理由",
                    "scene_labels": scene_labels,
                    "intent_labels": intent_labels,
                }),
            },
        }],
    }


class TestLlmPrimaryRouting(unittest.TestCase):
    def test_llm_primary_calls_llm_even_with_high_rules_confidence(self):
        features = _make_features(keyword_hits={"面试": 5, "候选人": 5, "简历": 5, "薪资": 5})
        ranking = CandidateRanking(
            templates=[
                Candidate(name="technical-interview-summary.md", score=80.0, matched_keywords=["面试"]),
                Candidate(name="product-analysis.md", score=5.0, matched_keywords=[]),
            ],
            industries=[],
        )
        llm_response = _make_llm_response(template="product-analysis.md")
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "面试内容",
                routing_mode="llm_primary",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "llm_primary")
        self.assertEqual(result.routing_mode, "llm_primary")
        self.assertEqual(result.recommended_template, "product-analysis.md")

    def test_llm_primary_falls_back_to_rules_on_api_error(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", side_effect=RuntimeError("API error")):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                routing_mode="llm_primary",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "llm_primary_fallback_to_rules")
        self.assertEqual(result.routing_mode, "llm_primary")

    def test_llm_primary_falls_back_on_low_llm_confidence(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response(confidence=0.1)
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                routing_mode="llm_primary",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "llm_primary_fallback_to_rules")

    def test_llm_primary_falls_back_on_empty_scene_labels(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response(scene_labels=[], intent_labels=[])
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                routing_mode="llm_primary",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "llm_primary_fallback_to_rules")

    def test_llm_primary_no_reasoning_config_returns_rules(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking):
            result = classify_transcript(
                "低置信度内容",
                routing_mode="llm_primary",
                reasoning_config=None,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")
        self.assertEqual(result.routing_mode, "rules")


class TestRulesModeUnchanged(unittest.TestCase):
    def test_high_confidence_stays_rules(self):
        features = _make_features(keyword_hits={"面试": 5, "候选人": 5, "简历": 5, "薪资": 5})
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates") as mock_rank:
            mock_rank.return_value = CandidateRanking(
                templates=[Candidate(name="technical-interview-summary.md", score=80.0, matched_keywords=["面试"])],
                industries=[],
            )
            config = _make_reasoning_config()
            result = classify_transcript(
                "面试内容",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")
        self.assertEqual(result.recommended_template, "technical-interview-summary.md")
        self.assertEqual(result.routing_mode, "rules")

    def test_low_confidence_triggers_llm(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "llm")
        self.assertEqual(result.recommended_template, "product-analysis.md")


class TestShadowMode(unittest.TestCase):
    def test_shadow_mode_populates_comparison(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "测试内容",
                routing_mode="shadow",
                reasoning_config=config,
            )
        self.assertIsNotNone(result.shadow_comparison)
        self.assertIn("rules_result", result.shadow_comparison)
        self.assertIn("llm_result", result.shadow_comparison)
        self.assertIn("agreed_template", result.shadow_comparison)

    def test_shadow_mode_returns_llm_result(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response(template="product-analysis.md")
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "测试内容",
                routing_mode="shadow",
                reasoning_config=config,
            )
        self.assertEqual(result.recommended_template, "product-analysis.md")
        self.assertEqual(result.routing_mode, "shadow")

    def test_shadow_mode_records_disagreement(self):
        features = _make_features(keyword_hits={"面试": 5})
        ranking = CandidateRanking(
            templates=[
                Candidate(name="technical-interview-summary.md", score=80.0, matched_keywords=["面试"]),
                Candidate(name="product-analysis.md", score=5.0, matched_keywords=[]),
            ],
            industries=[],
        )
        llm_response = _make_llm_response(template="product-analysis.md")
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "测试内容",
                routing_mode="shadow",
                reasoning_config=config,
            )
        self.assertFalse(result.shadow_comparison["agreed_template"])
        self.assertEqual(result.shadow_comparison["rules_result"]["recommended_template"],
                         "technical-interview-summary.md")
        self.assertEqual(result.shadow_comparison["llm_result"]["recommended_template"],
                         "product-analysis.md")

    def test_shadow_mode_no_reasoning_config_returns_rules_with_comparison(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking):
            result = classify_transcript(
                "测试内容",
                routing_mode="shadow",
                reasoning_config=None,
            )
        self.assertIsNotNone(result.shadow_comparison)
        self.assertIsNone(result.shadow_comparison["llm_result"])


class TestGrayscaleMode(unittest.TestCase):
    def test_grayscale_deterministic(self):
        transcript = "这是一段确定性测试文本用于灰度路由验证"
        result1 = _should_use_llm(transcript, 50)
        result2 = _should_use_llm(transcript, 50)
        self.assertEqual(result1, result2)

    def test_grayscale_0_always_rules(self):
        self.assertFalse(_should_use_llm("任何文本", 0))

    def test_grayscale_100_always_llm(self):
        self.assertTrue(_should_use_llm("任何文本", 100))

    def test_grayscale_mode_routes_to_llm(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        transcript = "grayscale_test_llm_route"
        llm_response = _make_llm_response()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.pipeline._should_use_llm", return_value=True), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                transcript,
                routing_mode="grayscale",
                reasoning_config=config,
                grayscale_percentage=100,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "grayscale_llm")
        self.assertEqual(result.routing_mode, "grayscale")

    def test_grayscale_mode_routes_to_rules(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.pipeline._should_use_llm", return_value=False):
            config = _make_reasoning_config()
            result = classify_transcript(
                "grayscale_test_rules",
                routing_mode="grayscale",
                reasoning_config=config,
                grayscale_percentage=0,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "grayscale_rules")
        self.assertEqual(result.routing_mode, "grayscale")


class TestRulesOnlyOverride(unittest.TestCase):
    def test_rules_only_overrides_routing_mode(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm") as mock_llm:
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                rules_only=True,
                routing_mode="llm_primary",
                reasoning_config=config,
            )
        mock_llm.assert_not_called()
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")


class TestClassifierStageValues(unittest.TestCase):
    def test_rules_mode_stage_rules(self):
        features = _make_features(keyword_hits={"面试": 5, "候选人": 5})
        ranking = CandidateRanking(
            templates=[Candidate(name="technical-interview-summary.md", score=80.0, matched_keywords=["面试"])],
            industries=[],
        )
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking):
            result = classify_transcript("测试", reasoning_config=_make_reasoning_config())
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")

    def test_rules_mode_stage_llm(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = _make_llm_response()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            result = classify_transcript("测试", reasoning_config=_make_reasoning_config())
        self.assertEqual(result.feature_summary["classifier_stage"], "llm")

    def test_rules_mode_stage_rules_llm_fallback(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", side_effect=RuntimeError("err")):
            result = classify_transcript("测试", reasoning_config=_make_reasoning_config())
        self.assertEqual(result.feature_summary["classifier_stage"], "rules_llm_fallback")


class TestAcceptLlmResult(unittest.TestCase):
    def test_accept_valid_result(self):
        from runtime.classifier.llm import _accept_llm_result
        result = {
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.85,
            "reason": "test",
            "scene_labels": ["技术讨论"],
            "intent_labels": ["问题诊断"],
        }
        self.assertIsNotNone(_accept_llm_result(result))

    def test_reject_none(self):
        from runtime.classifier.llm import _accept_llm_result
        self.assertIsNone(_accept_llm_result(None))

    def test_reject_low_confidence(self):
        from runtime.classifier.llm import _accept_llm_result
        result = {
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.2,
            "reason": "test",
            "scene_labels": ["技术讨论"],
            "intent_labels": ["问题诊断"],
        }
        self.assertIsNone(_accept_llm_result(result))

    def test_reject_empty_labels(self):
        from runtime.classifier.llm import _accept_llm_result
        result = {
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.85,
            "reason": "test",
            "scene_labels": [],
            "intent_labels": [],
        }
        self.assertIsNone(_accept_llm_result(result))

    def test_accept_with_only_scene_labels(self):
        from runtime.classifier.llm import _accept_llm_result
        result = {
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.85,
            "reason": "test",
            "scene_labels": ["技术讨论"],
            "intent_labels": [],
        }
        self.assertIsNotNone(_accept_llm_result(result))

    def test_accept_with_only_intent_labels(self):
        from runtime.classifier.llm import _accept_llm_result
        result = {
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.85,
            "reason": "test",
            "scene_labels": [],
            "intent_labels": ["问题诊断"],
        }
        self.assertIsNotNone(_accept_llm_result(result))


if __name__ == "__main__":
    unittest.main()
