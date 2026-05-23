from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


FEEDBACK_TYPES = {
    "漏信息",
    "结构不合适",
    "事实错误",
    "语气不专业",
    "行动项不清楚",
    "行业重点缺失",
}
SEVERITIES = {"low", "medium", "high"}
REVIEW_STATUSES = {"pending", "accepted", "rejected"}


@dataclass(frozen=True)
class FeedbackRecord:
    summary_id: str
    feedback_type: str
    severity: str
    user_comment: str
    preferred_fix: str | None = None
    review_status: str = "pending"

    def __post_init__(self) -> None:
        if self.feedback_type not in FEEDBACK_TYPES:
            raise ValueError(f"Unsupported feedback_type: {self.feedback_type}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unsupported severity: {self.severity}")
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError(f"Unsupported review_status: {self.review_status}")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EvaluationSample:
    transcript: str
    expected_focus_points: list[str]
    required_sections: list[str]
    forbidden_behaviors: list[str]
    golden_summary: str | None = None
    review_rubric: str | None = None

    def __post_init__(self) -> None:
        if not (self.golden_summary or self.review_rubric):
            raise ValueError("EvaluationSample requires golden_summary or review_rubric")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    sample_ids: list[str]
    reasoning_model: str
    analysis_goal: str
    findings: list[str]
    recommended_prompt_changes: list[str]
    review_status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        if self.review_status not in REVIEW_STATUSES:
            raise ValueError(f"Unsupported review_status: {self.review_status}")

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
