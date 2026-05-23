from __future__ import annotations

import hashlib
from pathlib import Path

from runtime.agent.config import AgentConfig

from .assets import get_fallback_template, load_template_manifest
from .llm import _accept_llm_result, refine_with_llm
from .models import CandidateRanking, ClassifierResult
from .rules import extract_features, rank_candidates

PRODUCT_DECISION_TEMPLATES = {"product-analysis.md", "requirements-review.md"}
HIGH_SIGNAL_TEMPLATE_THRESHOLDS = {
    "technical-interview-summary.md": 40,
    "government-project-bidding.md": 40,
    "sales-follow-up.md": 20,
    "channel-meeting.md": 20,
    "marketing-campaign-planning.md": 20,
    "insurance-claim-communication.md": 5,
    "financial-survey-visit.md": 30,
    "commercial-estate-consulting-expert.md": 30,
}

SCENE_CLASSIFIER_PROMPT_PATH = Path(__file__).resolve().parents[2] / "assets" / "prompts" / "classifier" / "scene-classifier.md"


def _load_scene_classifier_prompt() -> str:
    if SCENE_CLASSIFIER_PROMPT_PATH.exists():
        return SCENE_CLASSIFIER_PROMPT_PATH.read_text(encoding="utf-8")
    return ""


def _lookup_template(name: str):
    return next(item for item in load_template_manifest().templates if item.name == name)


def _calculate_confidence(ranking: CandidateRanking) -> float:
    if not ranking.templates:
        return 0.0
    top = ranking.templates[0].score
    second = ranking.templates[1].score if len(ranking.templates) > 1 else 0.0
    top_name = ranking.templates[0].name
    second_name = ranking.templates[1].name if len(ranking.templates) > 1 else None
    if top <= 0:
        return 0.25
    if (
        top_name in PRODUCT_DECISION_TEMPLATES
        and second_name in PRODUCT_DECISION_TEMPLATES
        and top >= 30
    ):
        return 0.82
    high_signal_threshold = HIGH_SIGNAL_TEMPLATE_THRESHOLDS.get(top_name)
    if high_signal_threshold is not None and top >= high_signal_threshold:
        return 0.82
    ratio = top / (top + second + 1.0)
    return min(0.95, max(0.25, ratio))


def _build_rules_result(
    features,
    ranking: CandidateRanking,
    confidence_threshold: float,
) -> ClassifierResult:
    top_template_name = ranking.templates[0].name if ranking.templates else get_fallback_template().name
    confidence = _calculate_confidence(ranking)
    fallback_used = confidence < confidence_threshold
    if fallback_used:
        top_template_name = get_fallback_template().name

    template_meta = _lookup_template(top_template_name)
    evidence_keywords = list(features.keyword_hits.keys())[:5]
    recommended_industry = ranking.industries[0].name if ranking.industries else None
    return ClassifierResult(
        scene_labels=template_meta.scene_labels,
        industry_labels=[],
        intent_labels=template_meta.intent_labels,
        output_shape=template_meta.output_shape,
        recommended_template=top_template_name,
        recommended_industry_prompt=recommended_industry,
        confidence=confidence,
        fallback_used=fallback_used,
        fallback_reason="low_confidence" if fallback_used else None,
        evidence_keywords=evidence_keywords,
        reason_summary="规则层已根据关键词和结构信号完成候选路由。",
        candidate_ranking=ranking,
        feature_summary={
            "char_count": features.char_count,
            "speaker_count": features.speaker_count,
            "keyword_hits": features.keyword_hits,
        },
    )


def _build_llm_result(
    llm_response: dict,
    features,
    ranking: CandidateRanking,
    stage_label: str,
) -> ClassifierResult:
    recommended = llm_response["recommended_template"]
    template_meta = _lookup_template(recommended)
    llm_industry = llm_response.get("industry_suggestion")
    rules_industry = ranking.industries[0].name if ranking.industries else None
    recommended_industry = llm_industry if llm_industry else rules_industry
    llm_scene_labels = llm_response.get("scene_labels")
    from .scene_instructions import get_scene_instruction
    valid_llm_labels = [l for l in (llm_scene_labels or []) if get_scene_instruction(l) is not None]
    effective_scene_labels = valid_llm_labels if valid_llm_labels else template_meta.scene_labels
    return ClassifierResult(
        scene_labels=effective_scene_labels,
        industry_labels=llm_response.get("intent_labels") or [],
        intent_labels=llm_response.get("intent_labels") or template_meta.intent_labels,
        output_shape=template_meta.output_shape,
        recommended_template=recommended,
        recommended_industry_prompt=recommended_industry,
        confidence=llm_response["confidence"],
        fallback_used=False,
        fallback_reason=None,
        evidence_keywords=list(features.keyword_hits.keys())[:5],
        reason_summary=llm_response.get("reason", "LLM 精排完成。"),
        candidate_ranking=ranking,
        feature_summary={
            "char_count": features.char_count,
            "speaker_count": features.speaker_count,
            "keyword_hits": features.keyword_hits,
            "classifier_stage": stage_label,
            "industry_suggestion": llm_response.get("industry_suggestion"),
        },
    )


def _should_use_llm(transcript: str, percentage: int) -> bool:
    if percentage >= 100:
        return True
    if percentage <= 0:
        return False
    digest = hashlib.md5(transcript[:200].encode()).hexdigest()
    value = int(digest[:8], 16) % 100
    return value < percentage


def _call_llm_classifier(
    features,
    ranking: CandidateRanking,
    reasoning_config: AgentConfig,
    rules_confidence: float,
) -> dict | None:
    scene_prompt = _load_scene_classifier_prompt()
    if not scene_prompt:
        return None
    raw = refine_with_llm(
        features,
        ranking,
        reasoning_config=reasoning_config,
        scene_classifier_prompt=scene_prompt,
        rules_confidence=rules_confidence,
        rules_template=ranking.templates[0].name if ranking.templates else get_fallback_template().name,
    )
    return _accept_llm_result(raw)


def classify_transcript(
    transcript: str,
    *,
    rules_only: bool = False,
    routing_mode: str = "rules",
    confidence_threshold: float = 0.65,
    reasoning_config: AgentConfig | None = None,
    grayscale_percentage: int = 100,
) -> ClassifierResult:
    if rules_only:
        routing_mode = "rules"

    features = extract_features(transcript)
    ranking = rank_candidates(features)
    rules_result = _build_rules_result(features, ranking, confidence_threshold)

    # --- rules mode: preserve existing behavior exactly ---
    if routing_mode == "rules":
        if not rules_only and reasoning_config is not None and rules_result.fallback_used:
            scene_prompt = _load_scene_classifier_prompt()
            if scene_prompt:
                raw = refine_with_llm(
                    features,
                    ranking,
                    reasoning_config=reasoning_config,
                    scene_classifier_prompt=scene_prompt,
                    rules_confidence=rules_result.confidence,
                    rules_template=ranking.templates[0].name if ranking.templates else get_fallback_template().name,
                )
                if raw is not None:
                    return _build_llm_result(raw, features, ranking, "llm")
                rules_result.feature_summary["classifier_stage"] = "rules_llm_fallback"
                return rules_result

        rules_result.feature_summary["classifier_stage"] = "rules"
        return rules_result

    # --- llm_primary mode: always call LLM, fallback to rules on failure ---
    if routing_mode == "llm_primary":
        if reasoning_config is None:
            rules_result.feature_summary["classifier_stage"] = "rules"
            return ClassifierResult(**{**rules_result.__dict__, "routing_mode": "rules"})

        llm_response = _call_llm_classifier(features, ranking, reasoning_config, rules_result.confidence)
        if llm_response is not None:
            result = _build_llm_result(llm_response, features, ranking, "llm_primary")
            result = ClassifierResult(**{**result.__dict__, "routing_mode": "llm_primary"})
            return result

        rules_result.feature_summary["classifier_stage"] = "llm_primary_fallback_to_rules"
        return ClassifierResult(**{**rules_result.__dict__, "routing_mode": "llm_primary"})

    # --- shadow mode: run both, return LLM result, log comparison ---
    if routing_mode == "shadow":
        if reasoning_config is not None:
            llm_response = _call_llm_classifier(features, ranking, reasoning_config, rules_result.confidence)
        else:
            llm_response = None

        shadow_comparison = {
            "rules_result": {
                "recommended_template": rules_result.recommended_template,
                "confidence": rules_result.confidence,
            },
            "llm_result": None,
            "agreed_template": True,
        }

        if llm_response is not None:
            llm_result = _build_llm_result(llm_response, features, ranking, "shadow")
            shadow_comparison["llm_result"] = {
                "recommended_template": llm_result.recommended_template,
                "confidence": llm_result.confidence,
            }
            shadow_comparison["agreed_template"] = (
                llm_result.recommended_template == rules_result.recommended_template
            )
            return ClassifierResult(**{
                **llm_result.__dict__,
                "routing_mode": "shadow",
                "shadow_comparison": shadow_comparison,
            })

        shadow_comparison["llm_result"] = None
        return ClassifierResult(**{
            **rules_result.__dict__,
            "routing_mode": "shadow",
            "shadow_comparison": shadow_comparison,
            "feature_summary": {**rules_result.feature_summary, "classifier_stage": "shadow"},
        })

    # --- grayscale mode: deterministic hash-based routing ---
    if routing_mode == "grayscale":
        if _should_use_llm(transcript, grayscale_percentage):
            if reasoning_config is not None:
                llm_response = _call_llm_classifier(features, ranking, reasoning_config, rules_result.confidence)
                if llm_response is not None:
                    result = _build_llm_result(llm_response, features, ranking, "grayscale_llm")
                    return ClassifierResult(**{**result.__dict__, "routing_mode": "grayscale"})

            rules_result.feature_summary["classifier_stage"] = "grayscale_llm_fallback_to_rules"
            return ClassifierResult(**{**rules_result.__dict__, "routing_mode": "grayscale"})

        rules_result.feature_summary["classifier_stage"] = "grayscale_rules"
        return ClassifierResult(**{**rules_result.__dict__, "routing_mode": "grayscale"})

    # Unknown mode: treat as rules
    rules_result.feature_summary["classifier_stage"] = "rules"
    return rules_result
