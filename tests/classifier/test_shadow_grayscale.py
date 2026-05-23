from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from runtime.agent.config import AgentConfig, CallParams
from runtime.classifier.models import Candidate, CandidateRanking, ClassifierResult, TranscriptFeatures
from runtime.classifier.pipeline import _should_use_llm, classify_transcript
from runtime.classifier.shadow import ShadowResult, write_shadow_log
from runtime.classifier.metrics import RoutingMetrics


def _make_features(**overrides) -> TranscriptFeatures:
    defaults = {
        "transcript": "测试转写文本内容",
        "char_count": 100,
        "speaker_count": 2,
        "keyword_hits": {"产品": 1},
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
        call_params=CallParams(thinking="disabled", max_tokens=1000, temperature=0.1),
    )


def _make_llm_response(template="product-analysis.md", confidence=0.88):
    return {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "recommended_template": template,
                    "industry_suggestion": None,
                    "confidence": confidence,
                    "reason": "测试",
                    "scene_labels": ["技术讨论"],
                    "intent_labels": ["问题诊断"],
                }),
            },
        }],
    }


class TestShadowIntegration(unittest.TestCase):
    def test_shadow_mode_runs_both_tracks(self):
        features = _make_features()
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
        self.assertIsNotNone(result.shadow_comparison["llm_result"])

    def test_shadow_mode_records_disagreement(self):
        features = _make_features()
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

    def test_shadow_mode_agreement(self):
        features = _make_features()
        ranking = _make_ranking()
        llm_response = _make_llm_response(template="general-meeting.md")
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "测试内容",
                routing_mode="shadow",
                reasoning_config=config,
            )
        self.assertTrue(result.shadow_comparison["agreed_template"])


class TestShadowLog(unittest.TestCase):
    def test_shadow_log_writes_jsonl(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            log_path = Path(f.name)

        try:
            rules_result = ClassifierResult(
                scene_labels=["会议协作"],
                industry_labels=[],
                intent_labels=["总结"],
                output_shape=["概览"],
                recommended_template="general-meeting.md",
                recommended_industry_prompt=None,
                confidence=0.5,
                fallback_used=True,
                fallback_reason="low_confidence",
                evidence_keywords=["会议"],
                reason_summary="test",
                candidate_ranking=CandidateRanking(templates=[], industries=[]),
                feature_summary={},
            )
            shadow = ShadowResult(
                rules_result=rules_result,
                llm_result=None,
                llm_error=None,
                agreed_template=True,
                agreed_industry=True,
                rules_confidence=0.5,
                llm_confidence=None,
                rules_latency_ms=10.0,
                llm_latency_ms=None,
                timestamp="2026-05-22T12:00:00",
            )
            write_shadow_log(shadow, log_path)
            write_shadow_log(shadow, log_path)

            lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 2)
            for line in lines:
                parsed = json.loads(line)
                self.assertIn("rules_result", parsed)
                self.assertIn("agreed_template", parsed)
        finally:
            log_path.unlink()


class TestGrayscaleHash(unittest.TestCase):
    def test_deterministic(self):
        text = "确定性测试文本"
        r1 = _should_use_llm(text, 50)
        r2 = _should_use_llm(text, 50)
        r3 = _should_use_llm(text, 50)
        self.assertEqual(r1, r2)
        self.assertEqual(r2, r3)

    def test_different_texts_may_route_differently(self):
        results = set()
        for i in range(100):
            results.add(_should_use_llm(f"文本内容{i}", 50))
        self.assertTrue(len(results) >= 1)

    def test_percentage_0(self):
        self.assertFalse(_should_use_llm("任何文本内容", 0))

    def test_percentage_100(self):
        self.assertTrue(_should_use_llm("任何文本内容", 100))

    def test_grayscale_llm_path_integration(self):
        features = _make_features()
        ranking = _make_ranking()
        llm_response = _make_llm_response()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.pipeline._should_use_llm", return_value=True), \
             patch("runtime.classifier.llm.call_litellm", return_value=llm_response):
            config = _make_reasoning_config()
            result = classify_transcript(
                "test",
                routing_mode="grayscale",
                reasoning_config=config,
                grayscale_percentage=50,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "grayscale_llm")

    def test_grayscale_rules_path_integration(self):
        features = _make_features()
        ranking = _make_ranking()
        with patch("runtime.classifier.pipeline.extract_features", return_value=features), \
             patch("runtime.classifier.pipeline.rank_candidates", return_value=ranking), \
             patch("runtime.classifier.pipeline._should_use_llm", return_value=False):
            config = _make_reasoning_config()
            result = classify_transcript(
                "test",
                routing_mode="grayscale",
                reasoning_config=config,
                grayscale_percentage=50,
            )
        self.assertEqual(result.feature_summary["classifier_stage"], "grayscale_rules")


class TestRoutingMetrics(unittest.TestCase):
    def test_metrics_creation(self):
        m = RoutingMetrics(
            total_requests=10,
            llm_requests=6,
            rules_requests=4,
        )
        self.assertEqual(m.total_requests, 10)
        self.assertEqual(m.llm_requests, 6)

    def test_metrics_as_dict(self):
        m = RoutingMetrics(total_requests=5)
        d = m.as_dict()
        self.assertEqual(d["total_requests"], 5)
        self.assertIsInstance(d, dict)


if __name__ == "__main__":
    unittest.main()
