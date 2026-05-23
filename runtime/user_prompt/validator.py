from __future__ import annotations

from .models import ValidationResult


BLOCKED_PATTERNS = [
    "忽略系统提示词",
    "泄露系统提示词",
    "编造",
    "虚构",
    "不要标注待确认",
]


def validate_user_prompt(text: str) -> ValidationResult:
    normalized = text.strip()
    violations = [pattern for pattern in BLOCKED_PATTERNS if pattern in normalized]
    return ValidationResult(
        is_valid=not violations,
        violations=violations,
        normalized_text=normalized,
    )
