from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from runtime.agent.config import AgentConfig, CallParams
from runtime.classifier.assets import load_template_manifest
from runtime.classifier.llm import _parse_llm_response, _strip_code_fences, refine_with_llm
from runtime.classifier.models import Candidate, CandidateRanking, TranscriptFeatures
from runtime.classifier.pipeline import classify_transcript


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


class TestStripCodeFences(unittest.TestCase):
    def test_strips_json_fences(self):
        raw = "```json\n{\"key\": \"value\"}\n```"
        self.assertEqual(_strip_code_fences(raw), '{"key": "value"}')

    def test_strips_plain_fences(self):
        raw = "```\n{\"key\": \"value\"}\n```"
        self.assertEqual(_strip_code_fences(raw), '{"key": "value"}')

    def test_passes_through_plain_json(self):
        raw = '{"key": "value"}'
        self.assertEqual(_strip_code_fences(raw), '{"key": "value"}')

    def test_strips_with_extra_whitespace(self):
        raw = "``` json \n{\"a\": 1}\n ```"
        self.assertEqual(_strip_code_fences(raw), '{"a": 1}')


class TestParseLlmResponse(unittest.TestCase):
    def setUp(self):
        self.ranking = _make_ranking()

    def test_valid_response(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "industry_suggestion": None,
            "confidence": 0.85,
            "reason": "产品讨论场景",
            "scene_labels": ["技术讨论"],
            "intent_labels": ["问题诊断"],
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertEqual(result["recommended_template"], "product-analysis.md")
        self.assertIsNone(result["industry_suggestion"])
        self.assertEqual(result["confidence"], 0.85)

    def test_invalid_template_returns_none(self):
        raw = json.dumps({
            "recommended_template": "nonexistent-template.md",
            "confidence": 0.9,
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNone(result)

    def test_invalid_industry_set_to_none(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "industry_suggestion": "fake-industry.md",
            "confidence": 0.8,
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertIsNone(result["industry_suggestion"])

    def test_valid_industry_preserved(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "industry_suggestion": "marketing-industry.md",
            "confidence": 0.8,
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertEqual(result["industry_suggestion"], "marketing-industry.md")

    def test_confidence_clamped_high(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "confidence": 2.5,
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], 1.0)

    def test_confidence_clamped_low(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "confidence": -0.5,
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], 0.0)

    def test_malformed_json_returns_none(self):
        result = _parse_llm_response("not json at all", self.ranking)
        self.assertIsNone(result)

    def test_missing_template_returns_none(self):
        raw = json.dumps({"confidence": 0.9})
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNone(result)

    def test_non_dict_returns_none(self):
        result = _parse_llm_response("[1, 2, 3]", self.ranking)
        self.assertIsNone(result)

    def test_scene_labels_not_list_handled(self):
        raw = json.dumps({
            "recommended_template": "product-analysis.md",
            "confidence": 0.8,
            "scene_labels": "not a list",
        })
        result = _parse_llm_response(raw, self.ranking)
        self.assertIsNotNone(result)
        self.assertEqual(result["scene_labels"], [])


class TestRefineWithLlm(unittest.TestCase):
    def test_successful_refinement(self):
        ranking = _make_ranking()
        features = _make_features()
        config = _make_reasoning_config()

        llm_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "recommended_template": "product-analysis.md",
                        "industry_suggestion": None,
                        "confidence": 0.9,
                        "reason": "产品讨论",
                        "scene_labels": ["技术讨论"],
                        "intent_labels": ["问题诊断"],
                    }),
                },
            }],
        }

        with patch("runtime.classifier.llm.call_litellm", return_value=llm_response) as mock_call:
            result = refine_with_llm(
                features, ranking,
                reasoning_config=config,
                scene_classifier_prompt="test prompt",
                rules_confidence=0.3,
                rules_template="general-meeting.md",
            )

        self.assertIsNotNone(result)
        self.assertEqual(result["recommended_template"], "product-analysis.md")
        self.assertEqual(result["confidence"], 0.9)
        mock_call.assert_called_once()
        self.assertEqual(mock_call.call_args.kwargs["model"], "test-reasoning-model")
        self.assertEqual(mock_call.call_args.kwargs["temperature"], 0.1)
        self.assertEqual(mock_call.call_args.kwargs["max_tokens"], 1000)
        self.assertEqual(mock_call.call_args.kwargs["thinking"], "disabled")

    def test_api_failure_returns_none(self):
        ranking = _make_ranking()
        features = _make_features()
        config = _make_reasoning_config()

        with patch("runtime.classifier.llm.call_litellm", side_effect=RuntimeError("API error")):
            result = refine_with_llm(
                features, ranking,
                reasoning_config=config,
                scene_classifier_prompt="test prompt",
                rules_confidence=0.3,
                rules_template="general-meeting.md",
            )

        self.assertIsNone(result)

    def test_invalid_response_returns_none(self):
        ranking = _make_ranking()
        features = _make_features()
        config = _make_reasoning_config()

        llm_response = {
            "choices": [{"message": {"content": "not valid json"}}],
        }

        with patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            result = refine_with_llm(
                features, ranking,
                reasoning_config=config,
                scene_classifier_prompt="test prompt",
                rules_confidence=0.3,
                rules_template="general-meeting.md",
            )

        self.assertIsNone(result)


class TestTwoStagePipeline(unittest.TestCase):
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
        self.assertIsNone(result.recommended_industry_prompt)

    def test_low_confidence_triggers_llm(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "recommended_template": "product-analysis.md",
                        "industry_suggestion": None,
                        "confidence": 0.88,
                        "reason": "产品讨论",
                        "scene_labels": ["技术讨论"],
                        "intent_labels": ["问题诊断"],
                    }),
                },
            }],
        }

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
        self.assertIsNotNone(result.recommended_industry_prompt)
        self.assertTrue(result.recommended_industry_prompt.endswith(".md"))

    def test_llm_failure_falls_back_to_rules(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()

        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", side_effect=RuntimeError("API error")):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                reasoning_config=config,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "rules_llm_fallback")

    def test_rules_only_never_calls_llm(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()

        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm") as mock_llm:
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                rules_only=True,
                reasoning_config=config,
            )
        mock_llm.assert_not_called()
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")

    def test_no_reasoning_config_stays_rules(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()

        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking):
            result = classify_transcript("低置信度内容")
        self.assertEqual(result.feature_summary["classifier_stage"], "rules")

    def test_industry_prompt_populated_from_llm_suggestion(self):
        features = _make_features(keyword_hits={"产品": 1})
        ranking = _make_ranking()
        llm_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "recommended_template": "product-analysis.md",
                        "industry_suggestion": "marketing-industry.md",
                        "confidence": 0.88,
                        "reason": "产品讨论",
                        "scene_labels": ["技术讨论"],
                        "intent_labels": ["问题诊断"],
                    }),
                },
            }],
        }

        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "低置信度内容",
                reasoning_config=config,
            )
        self.assertIsNotNone(result.recommended_industry_prompt)
        self.assertEqual(result.recommended_industry_prompt, "marketing-industry.md")
        self.assertEqual(result.feature_summary.get("industry_suggestion"), "marketing-industry.md")


if __name__ == "__main__":
    unittest.main()
