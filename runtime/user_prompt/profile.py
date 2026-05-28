from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


AUDIENCE_LABELS = {
    "self": "自己",
    "manager": "上级",
    "customer": "客户",
    "team": "项目组",
}

SUMMARY_DEPTH_LABELS = {
    "concise": "概要决策型",
    "full": "完整纪要型",
}


@dataclass(frozen=True)
class UserPromptProfile:
    name: str
    user_role: str = ""
    industry: str = ""
    meeting_scenarios: list[str] = field(default_factory=list)
    style_preference: str = ""
    evidence_preference: str = ""

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _as_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def load_user_prompt_profile(path: Path, name: str) -> UserPromptProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict) or name not in profiles:
        raise ValueError(f"User prompt profile not found: {name}")
    raw = profiles[name]
    if not isinstance(raw, dict):
        raise ValueError(f"User prompt profile must be an object: {name}")
    return UserPromptProfile(
        name=name,
        user_role=_as_string(raw.get("user_role")),
        industry=_as_string(raw.get("industry")),
        meeting_scenarios=_as_string_list(raw.get("meeting_scenarios")),
        style_preference=_as_string(raw.get("style_preference")),
        evidence_preference=_as_string(raw.get("evidence_preference")),
    )


def compile_profile_prompt(
    profile: UserPromptProfile,
    *,
    audience: str | None = None,
    summary_depth: str | None = None,
) -> str:
    lines = ["# 用户画像增强", ""]
    if profile.user_role:
        lines.append(f"- 用户角色：{profile.user_role}")
    if profile.industry:
        lines.append(f"- 固定行业：{profile.industry}")
    if profile.meeting_scenarios:
        lines.append(f"- 常见会议场景：{'、'.join(profile.meeting_scenarios)}")
    if profile.style_preference:
        lines.append(f"- 表达风格：{profile.style_preference}")
    if profile.evidence_preference:
        lines.append(f"- 证据/原话偏好：{profile.evidence_preference}")

    if audience:
        lines.append(f"- 本次目标读者：{AUDIENCE_LABELS[audience]}")
    if summary_depth:
        lines.append(f"- 本次输出详略：{SUMMARY_DEPTH_LABELS[summary_depth]}")

    lines.extend([
        "",
        "# 画像使用边界",
        "",
        "- 会议事实优先于用户风格；用户风格只影响表达方式，不允许改变、弱化或隐藏事实。",
    ])
    return "\n".join(lines).strip() + "\n"
