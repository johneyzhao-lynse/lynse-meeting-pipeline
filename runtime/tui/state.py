from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from runtime.reasoning import normalize_reasoning_effort


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def add(self, usage: dict[str, int]) -> None:
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class SessionState:
    model: str = "deepseek-chat"
    base_url: str = ""
    api_key: str = ""
    api_key_env: str = ""
    safety_mode: str = "reactive"
    temperature: float = 0.2
    max_tokens: int = 3000
    thinking: str = "disabled"
    reasoning_effort: str | None = "medium"
    prompt_version: str = "v1"
    confidence_threshold: float = 0.65
    routing_mode: str = "llm_primary"
    dynamic_prompt: bool = False
    profile_enabled: bool = True
    classify_meeting: bool = False
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    call_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def load_initial_state(root: Path) -> SessionState:
    state = SessionState()
    agent_config_path = root / "config" / "agent.local.json"
    if agent_config_path.exists():
        data = json.loads(agent_config_path.read_text(encoding="utf-8"))
        state.model = data.get("model", state.model)
        state.base_url = data.get("base_url", state.base_url)
        if data.get("api_key"):
            state.api_key = data["api_key"]
        if "api_key_env" in data:
            state.api_key_env = data["api_key_env"]
    local_config_path = root / "config" / "local.json"
    if local_config_path.exists():
        data = json.loads(local_config_path.read_text(encoding="utf-8"))
        state.safety_mode = data.get("safety_mode", state.safety_mode)
        state.profile_enabled = data.get("profile_enabled", state.profile_enabled)
        state.temperature = float(data.get("temperature", state.temperature))
        state.max_tokens = int(data.get("max_tokens", state.max_tokens))
        state.thinking = data.get("thinking", state.thinking)
        state.reasoning_effort = normalize_reasoning_effort(data.get("reasoning_effort", state.reasoning_effort))
    state.base_url = os.getenv("LYNCLAW_AGENT_BASE_URL", state.base_url)
    state.safety_mode = os.getenv("SUMMARY_SAFETY_MODE", state.safety_mode)
    return state
