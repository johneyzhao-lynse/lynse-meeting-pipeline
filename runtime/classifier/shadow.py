from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .models import ClassifierResult


@dataclass(frozen=True)
class ShadowResult:
    rules_result: ClassifierResult
    llm_result: ClassifierResult | None
    llm_error: str | None
    agreed_template: bool
    agreed_industry: bool
    rules_confidence: float
    llm_confidence: float | None
    rules_latency_ms: float
    llm_latency_ms: float | None
    timestamp: str

    def as_dict(self) -> dict:
        data = asdict(self)
        data["rules_confidence"] = round(self.rules_confidence, 4)
        if self.llm_confidence is not None:
            data["llm_confidence"] = round(self.llm_confidence, 4)
        return data


def write_shadow_log(result: ShadowResult, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = result.as_dict()
    line = json.dumps(entry, ensure_ascii=False)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
