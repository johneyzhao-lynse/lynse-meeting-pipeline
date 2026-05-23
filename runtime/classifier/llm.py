from __future__ import annotations

import json
import re

from runtime.agent.config import AgentConfig
from runtime.client import call_litellm

from .assets import load_industry_manifest, load_template_manifest
from .models import CandidateRanking, TranscriptFeatures


SCENE_CLASSIFIER_PROMPT_PATH = "assets/prompts/classifier/scene-classifier.md"

_CODE_FENCE_RE = re.compile(r"```\s*[\w]*\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _build_llm_payload(
    features: TranscriptFeatures,
    ranking: CandidateRanking,
    rules_confidence: float,
    rules_template: str,
    scene_classifier_prompt: str,
) -> list[dict[str, str]]:
    template_manifest = load_template_manifest()
    industry_manifest = load_industry_manifest()

    candidate_templates = []
    for candidate in ranking.templates[:5]:
        meta = next(
            (t for t in template_manifest.templates if t.name == candidate.name),
            None,
        )
        candidate_templates.append({
            "name": candidate.name,
            "display_name": meta.display_name if meta else candidate.name,
            "description": meta.short_description if meta else "",
            "keywords": meta.keywords if meta else [],
            "matched_keywords": candidate.matched_keywords[:5],
            "score": round(candidate.score, 1),
        })

    candidate_industries = []
    for candidate in ranking.industries[:3]:
        meta = next(
            (i for i in industry_manifest.industries if i.name == candidate.name),
            None,
        )
        candidate_industries.append({
            "name": candidate.name,
            "display_name": meta.display_name if meta else candidate.name,
            "keywords": meta.keywords if meta else [],
            "matched_keywords": candidate.matched_keywords[:5],
            "score": round(candidate.score, 1),
        })

    user_payload = json.dumps({
        "rules_recommendation": {
            "template": rules_template,
            "confidence": round(rules_confidence, 4),
        },
        "candidate_templates": candidate_templates,
        "candidate_industries": candidate_industries,
        "transcript_snippets": {
            "head": features.head_snippet,
            "tail": features.tail_snippet,
            "key_windows": features.key_windows,
        },
        "transcript_stats": {
            "char_count": features.char_count,
            "speaker_count": features.speaker_count,
            "top_keywords": dict(list(features.keyword_hits.items())[:15]),
        },
    }, ensure_ascii=False, indent=2)

    return [
        {"role": "system", "content": scene_classifier_prompt},
        {"role": "user", "content": user_payload},
    ]


def _parse_llm_response(
    raw: str,
    ranking: CandidateRanking,
) -> dict | None:
    cleaned = _strip_code_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None

    if not isinstance(parsed, dict):
        return None

    template = parsed.get("recommended_template")
    if not template or not isinstance(template, str):
        return None

    valid_templates = {c.name for c in ranking.templates}
    if template not in valid_templates:
        return None

    industry = parsed.get("industry_suggestion")
    if industry is not None:
        if not isinstance(industry, str):
            industry = None
        else:
            valid_industries = {i.name for i in load_industry_manifest().industries}
            if industry not in valid_industries:
                industry = None

    confidence = parsed.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, float(confidence)))

    return {
        "recommended_template": template,
        "industry_suggestion": industry,
        "confidence": confidence,
        "reason": str(parsed.get("reason", "")),
        "scene_labels": parsed.get("scene_labels", []) if isinstance(parsed.get("scene_labels"), list) else [],
        "intent_labels": parsed.get("intent_labels", []) if isinstance(parsed.get("intent_labels"), list) else [],
    }


def _accept_llm_result(parsed: dict | None, *, min_confidence: float = 0.3) -> dict | None:
    if parsed is None:
        return None
    if parsed["confidence"] < min_confidence:
        return None
    if not parsed.get("scene_labels") and not parsed.get("intent_labels"):
        return None
    return parsed


def refine_with_llm(
    features: TranscriptFeatures,
    ranking: CandidateRanking,
    *,
    reasoning_config: AgentConfig,
    scene_classifier_prompt: str,
    rules_confidence: float,
    rules_template: str,
) -> dict | None:
    messages = _build_llm_payload(
        features, ranking, rules_confidence, rules_template, scene_classifier_prompt,
    )
    try:
        params = reasoning_config.call_params
        result = call_litellm(
            api_key=reasoning_config.api_key,
            model=reasoning_config.model,
            messages=messages,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            thinking=params.thinking,
            reasoning_effort=params.reasoning_effort,
            base_url=reasoning_config.base_url,
        )
    except RuntimeError:
        return None

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        return None

    return _parse_llm_response(content, ranking)
