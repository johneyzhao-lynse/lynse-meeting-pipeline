from __future__ import annotations

import json
from urllib import request, error

from .reasoning import reasoning_budget


def _is_qwen_model(model: str) -> bool:
    return model.lower().startswith("qwen")


def call_litellm(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    thinking: str = "disabled",
    reasoning_effort: str | None = None,
    max_tokens: int = 3000,
    temperature: float = 0.2,
    base_url: str | None = None,
) -> dict:
    endpoint = (base_url or "https://api.deepseek.com").rstrip("/") + "/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    if _is_qwen_model(model):
        if thinking == "enabled":
            payload["enable_thinking"] = True
            payload["thinking_budget"] = reasoning_budget(reasoning_effort)
    else:
        payload["thinking"] = {"type": thinking}
        if thinking == "enabled" and reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API HTTP {exc.code}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM API request failed: {exc}") from exc
