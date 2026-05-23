from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path

from runtime.reasoning import normalize_reasoning_effort


@dataclass(frozen=True)
class CallParams:
    thinking: str = "disabled"
    reasoning_effort: str | None = "medium"
    max_tokens: int = 3000
    temperature: float = 0.2


@dataclass(frozen=True)
class AgentConfig:
    api_key_value: str | None
    model: str
    base_url: str | None = None
    api_key_env: str | None = None
    call_params: CallParams = field(default_factory=CallParams)

    @property
    def api_key(self) -> str | None:
        if self.api_key_value:
            return self.api_key_value
        if self.api_key_env:
            return os.getenv(self.api_key_env)
        return None


@dataclass(frozen=True)
class RouterConfig:
    routing_mode: str = "llm_primary"
    grayscale_percentage: int = 100
    shadow_log_path: str | None = None
    metrics_enabled: bool = False


@dataclass(frozen=True)
class ModelPairConfig:
    summary: AgentConfig
    reasoning: AgentConfig
    classifier: AgentConfig
    router: RouterConfig = field(default_factory=RouterConfig)


def _read_local_agent_config(root: Path) -> dict:
    path = root / "config" / "agent.local.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_call_params(local: dict, prefix: str | None = None) -> CallParams:
    section = local.get(prefix, {}) if prefix else local
    section = section if isinstance(section, dict) else {}
    return CallParams(
        thinking=section.get("thinking", "disabled"),
        reasoning_effort=normalize_reasoning_effort(section.get("reasoning_effort")),
        max_tokens=int(section.get("max_tokens", 3000)),
        temperature=float(section.get("temperature", 0.2)),
    )


def _from_env_or_local(
    *,
    local: dict,
    prefix: str,
    fallback_prefix: str | None = None,
    default_model: str = "deepseek-chat",
    call_params_prefix: str | None = None,
) -> AgentConfig:
    fallback = fallback_prefix or prefix
    model = (
        os.getenv(f"{prefix}_MODEL")
        or local.get(f"{prefix.lower()}_model")
        or os.getenv(f"{fallback}_MODEL")
        or local.get("model")
        or default_model
    )
    base_url = (
        os.getenv(f"{prefix}_BASE_URL")
        or local.get(f"{prefix.lower()}_base_url")
        or os.getenv(f"{fallback}_BASE_URL")
        or local.get("base_url")
    )
    api_key = (
        os.getenv(f"{prefix}_API_KEY")
        or local.get(f"{prefix.lower()}_api_key")
        or os.getenv(f"{fallback}_API_KEY")
        or local.get("api_key")
    )
    api_key_env = (
        os.getenv(f"{prefix}_API_KEY_ENV")
        or local.get(f"{prefix.lower()}_api_key_env")
        or os.getenv(f"{fallback}_API_KEY_ENV")
        or local.get("api_key_env")
    )
    params = _parse_call_params(local, prefix=call_params_prefix)
    return AgentConfig(
        api_key_value=api_key,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        call_params=params,
    )


def load_model_pair_config(root: Path) -> ModelPairConfig:
    local = _read_local_agent_config(root)
    summary = _from_env_or_local(
        local=local,
        prefix="SUMMARY",
        fallback_prefix="LYNCLAW_AGENT",
        default_model="deepseek-chat",
    )
    reasoning = _from_env_or_local(
        local=local,
        prefix="REASONING",
        fallback_prefix="SUMMARY",
        default_model=summary.model,
        call_params_prefix="reasoning",
    )
    classifier = _from_env_or_local(
        local=local,
        prefix="CLASSIFIER",
        fallback_prefix="SUMMARY",
        default_model=summary.model,
        call_params_prefix="classifier",
    )
    router_raw = local.get("router", {})
    router_raw = router_raw if isinstance(router_raw, dict) else {}
    router = RouterConfig(
        routing_mode=str(router_raw.get("routing_mode", "llm_primary")),
        grayscale_percentage=int(router_raw.get("grayscale_percentage", 100)),
        shadow_log_path=router_raw.get("shadow_log_path"),
        metrics_enabled=bool(router_raw.get("metrics_enabled", False)),
    )

    return ModelPairConfig(
        summary=summary,
        reasoning=reasoning,
        classifier=classifier,
        router=router,
    )


def load_agent_config(root: Path) -> AgentConfig:
    return load_model_pair_config(root).summary
