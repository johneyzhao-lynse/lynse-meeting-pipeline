from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class SessionLogger:
    def __init__(self, log_dir: Path, session_id: str | None = None) -> None:
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_id = session_id or f"tui-{timestamp}"
        self.entries: list[dict[str, Any]] = []
        self.log_path = self.log_dir / f"{self.session_id}.jsonl"

    def log(
        self,
        event: str,
        *,
        data: dict[str, Any] | None = None,
    ) -> None:
        entry: dict[str, Any] = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "session_id": self.session_id,
            "event": event,
        }
        if data:
            entry["data"] = data
        self.entries.append(entry)
        self._append_to_file(entry)

    def log_command(
        self,
        command: str,
        *,
        args: str = "",
        params: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            "command",
            data={"command": command, "args": args, **(params or {})},
        )

    def log_classification(
        self,
        transcript: str,
        result: dict[str, Any],
        *,
        config_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            "classification",
            data={
                "transcript": transcript,
                "recommended_template": result.get("recommended_template"),
                "recommended_industry": result.get("recommended_industry_prompt"),
                "confidence": result.get("confidence"),
                "fallback_used": result.get("fallback_used"),
                "fallback_reason": result.get("fallback_reason"),
                "scene_labels": result.get("scene_labels"),
                "intent_labels": result.get("intent_labels"),
                "evidence_keywords": result.get("evidence_keywords"),
                "candidate_templates": [
                    {"name": c["name"], "score": c["score"]}
                    for c in result.get("candidate_ranking", {}).get("templates", [])[:5]
                ],
                "config_snapshot": config_snapshot,
            },
        )

    def log_generation(
        self,
        *,
        transcript: str,
        template: str,
        industry: str | None,
        safety_mode: str,
        model: str,
        thinking: str,
        temperature: float,
        max_tokens: int,
        safety_risks: list[str],
        token_usage: dict[str, int] | None = None,
        attempt_count: int = 1,
        final_status: str = "success",
        output_path: str | None = None,
        error: str | None = None,
    ) -> None:
        self.log(
            "generation",
            data={
                "transcript": transcript,
                "template": template,
                "industry": industry,
                "safety_mode": safety_mode,
                "model": model,
                "thinking": thinking,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "safety_risks": safety_risks,
                "token_usage": token_usage,
                "attempt_count": attempt_count,
                "final_status": final_status,
                "output_path": output_path,
                "error": error,
            },
        )

    def log_config_change(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
    ) -> None:
        self.log(
            "config_change",
            data={"key": key, "old": str(old_value), "new": str(new_value)},
        )

    def log_token_summary(self, summary: dict[str, Any]) -> None:
        self.log("token_summary", data=summary)

    def _append_to_file(self, entry: dict[str, Any]) -> None:
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        self.log_path.write_text(
            self.log_path.read_text(encoding="utf-8") + line if self.log_path.exists() else line,
            encoding="utf-8",
        )
