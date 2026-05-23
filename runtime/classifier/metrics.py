from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RoutingMetrics:
    total_requests: int = 0
    llm_requests: int = 0
    rules_requests: int = 0
    llm_fallback_to_rules: int = 0
    rules_fallback_to_general: int = 0
    avg_llm_latency_ms: float = 0.0
    avg_rules_latency_ms: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)
