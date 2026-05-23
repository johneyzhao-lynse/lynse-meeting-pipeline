from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import ClassifierResult


def write_classification_report(
    result: ClassifierResult,
    output_dir: Path,
    *,
    transcript_id: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = result.as_dict()
    report["transcript_id"] = transcript_id
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    path = output_dir / f"{transcript_id}__classification.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
