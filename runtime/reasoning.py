from __future__ import annotations


REASONING_EFFORTS = ("low", "medium", "high")
REASONING_BUDGETS = {
    "low": 1000,
    "medium": 4000,
    "high": 8000,
}

_REASONING_ALIASES = {
    "低": "low",
    "低档": "low",
    "低深度": "low",
    "中": "medium",
    "中档": "medium",
    "中等": "medium",
    "中深度": "medium",
    "高": "high",
    "高档": "high",
    "高深度": "high",
}


def normalize_reasoning_effort(value: str | None) -> str:
    if value is None or not str(value).strip():
        return "medium"
    normalized = str(value).strip().lower()
    normalized = _REASONING_ALIASES.get(normalized, normalized)
    if normalized not in REASONING_EFFORTS:
        raise ValueError("推理深度必须是 low/medium/high 或 低/中/高")
    return normalized


def reasoning_budget(value: str | None) -> int:
    return REASONING_BUDGETS[normalize_reasoning_effort(value)]
