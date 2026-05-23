from __future__ import annotations

from dataclasses import dataclass

from runtime.safety import REFUSAL_MARKERS


@dataclass(frozen=True)
class GenerationFailure:
    retryable: bool
    reason: str
    markers: list[str]


def classify_generation_failure(content: str) -> GenerationFailure:
    stripped = content.strip()
    if not stripped:
        return GenerationFailure(retryable=True, reason="empty_output", markers=[])
    lowered = stripped.lower()
    matched = [marker for marker in REFUSAL_MARKERS if marker.lower() in lowered]
    if matched:
        return GenerationFailure(retryable=True, reason="model_refusal", markers=matched)
    if "##" not in stripped and "- " not in stripped:
        return GenerationFailure(retryable=True, reason="invalid_summary_shape", markers=[])
    return GenerationFailure(retryable=False, reason="ok", markers=[])


def classify_api_failure(error_text: str) -> GenerationFailure:
    lowered = error_text.lower()
    sensitive_markers = [
        "content_filter",
        "sensitive",
        "safety",
        "policy",
        "敏感",
        "审核",
    ]
    matched = [marker for marker in sensitive_markers if marker in lowered]
    if matched:
        return GenerationFailure(retryable=True, reason="sensitive_api_failure", markers=matched)
    return GenerationFailure(retryable=False, reason="api_failure", markers=[])
