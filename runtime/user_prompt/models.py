from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class UserPrompt:
    summary_goal: str = ""
    target_audience: str = ""
    output_sections: list[str] = field(default_factory=list)
    special_requirements: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ValidationResult:
    is_valid: bool
    violations: list[str]
    normalized_text: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
