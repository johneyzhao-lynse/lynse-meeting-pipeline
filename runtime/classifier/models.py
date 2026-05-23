from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class TemplateManifestItem:
    name: str
    display_name: str
    short_description: str
    scene_labels: list[str]
    intent_labels: list[str]
    output_shape: list[str]
    keywords: list[str]
    editable: bool
    default_for_fallback: bool = False


@dataclass(frozen=True)
class IndustryManifestItem:
    name: str
    display_name: str
    short_description: str
    industry_labels: list[str]
    keywords: list[str]
    risk_level: str
    user_visible_summary: str
    editable: bool


@dataclass(frozen=True)
class TemplateManifest:
    templates: list[TemplateManifestItem]


@dataclass(frozen=True)
class IndustryManifest:
    industries: list[IndustryManifestItem]


@dataclass(frozen=True)
class Candidate:
    name: str
    score: float
    matched_keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateRanking:
    templates: list[Candidate]
    industries: list[Candidate]


@dataclass(frozen=True)
class TranscriptFeatures:
    transcript: str
    char_count: int
    speaker_count: int
    keyword_hits: dict[str, int]
    head_snippet: str
    tail_snippet: str
    key_windows: list[str]


@dataclass(frozen=True)
class ClassifierResult:
    scene_labels: list[str]
    industry_labels: list[str]
    intent_labels: list[str]
    output_shape: list[str]
    recommended_template: str
    recommended_industry_prompt: str | None
    confidence: float
    fallback_used: bool
    fallback_reason: str | None
    evidence_keywords: list[str]
    reason_summary: str
    candidate_ranking: CandidateRanking
    feature_summary: dict[str, object]
    routing_mode: str = "rules"
    shadow_comparison: dict | None = None

    def as_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["confidence"] = round(self.confidence, 4)
        return data
