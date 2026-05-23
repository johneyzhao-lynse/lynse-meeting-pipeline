from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pathlib import Path

from runtime.agent.config import AgentConfig
from runtime.assets import read_text
from runtime.client import call_litellm


MEETING_CLASSIFIER_PROMPT_PATH = Path("assets/prompts/classifier/meeting-classifier.md")

VALID_MEETING_TYPES = {
    # 产品类
    "产品周会", "需求评审会", "技术评审会",
    "每日站会", "架构与设计评审", "Bug/缺陷排查会",
    # 销售类
    "销售会议", "合作洽谈会", "客户谈判", "渠道会议", "银企访谈",
    "客诉与售后跟进会", "供应商评审会", "商业地产顾问会",
    # 人力类
    "面试", "1对1沟通", "全员大会", "团队分享会/技术沙龙", "绩效面谈",
    # 营销类
    "推广策划会", "用户调研/访谈", "运营数据分析会", "头脑风暴会",
    # 项目类
    "项目推进会", "复盘会", "项目启动会", "跨部门协调会", "事故复盘/根因分析",
    # 管理类
    "管理层例会",
    # 战略类
    "战略会议", "董事会/股东会",
    # 财务类
    "财务会议", "预算审计会",
    # 法务类
    "法务合规",
    # 其他
    "其他",
}

VALID_MEETING_CATEGORIES = {
    "产品类", "销售类", "人力类", "营销类",
    "项目类", "管理类", "战略类", "财务类", "法务类", "其他",
}

VALID_MEETING_MODES = {"决策型", "同步型", "评估型", "谈判型"}

TYPE_TO_CATEGORY: dict[str, str] = {
    # 产品类
    "产品周会": "产品类", "需求评审会": "产品类", "技术评审会": "产品类",
    "每日站会": "产品类", "架构与设计评审": "产品类", "Bug/缺陷排查会": "产品类",
    # 销售类
    "销售会议": "销售类", "合作洽谈会": "销售类", "客户谈判": "销售类",
    "渠道会议": "销售类", "银企访谈": "销售类",
    "客诉与售后跟进会": "销售类", "供应商评审会": "销售类", "商业地产顾问会": "销售类",
    # 人力类
    "面试": "人力类", "1对1沟通": "人力类", "全员大会": "人力类",
    "团队分享会/技术沙龙": "人力类", "绩效面谈": "人力类",
    # 营销类
    "推广策划会": "营销类", "用户调研/访谈": "营销类",
    "运营数据分析会": "营销类", "头脑风暴会": "营销类",
    # 项目类
    "项目推进会": "项目类", "复盘会": "项目类",
    "项目启动会": "项目类", "跨部门协调会": "项目类", "事故复盘/根因分析": "项目类",
    # 管理类
    "管理层例会": "管理类",
    # 战略类
    "战略会议": "战略类", "董事会/股东会": "战略类",
    # 财务类
    "财务会议": "财务类", "预算审计会": "财务类",
    # 法务类
    "法务合规": "法务类",
    # 其他
    "其他": "其他",
}

_CODE_FENCE_RE = re.compile(r"```\s*[\w]*\s*\n?(.*?)\n?\s*```", re.DOTALL)


@dataclass(frozen=True)
class MeetingClassification:
    meeting_type: str
    meeting_category: str
    meeting_mode: str

    def as_dict(self) -> dict[str, str]:
        return {
            "meeting_type": self.meeting_type,
            "meeting_category": self.meeting_category,
            "meeting_mode": self.meeting_mode,
        }


def _strip_code_fences(text: str) -> str:
    m = _CODE_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _validate(parsed: dict) -> MeetingClassification | None:
    meeting_type = parsed.get("meeting_type", "")
    meeting_mode = parsed.get("meeting_mode", "")

    if meeting_type not in VALID_MEETING_TYPES:
        return None
    if meeting_mode not in VALID_MEETING_MODES:
        return None

    meeting_category = TYPE_TO_CATEGORY.get(meeting_type, "其他")

    return MeetingClassification(
        meeting_type=meeting_type,
        meeting_category=meeting_category,
        meeting_mode=meeting_mode,
    )


def _parse_response(raw: str) -> MeetingClassification | None:
    cleaned = _strip_code_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    return _validate(parsed)


def classify_meeting(
    transcript: str,
    *,
    classifier_config: AgentConfig,
    preview_chars: int = 2000,
) -> MeetingClassification | None:
    system_prompt = read_text(MEETING_CLASSIFIER_PROMPT_PATH)
    preview = transcript[:preview_chars]

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": preview},
    ]

    params = classifier_config.call_params
    try:
        result = call_litellm(
            api_key=classifier_config.api_key,
            model=classifier_config.model,
            messages=messages,
            max_tokens=params.max_tokens,
            temperature=params.temperature,
            thinking=params.thinking,
            reasoning_effort=params.reasoning_effort,
            base_url=classifier_config.base_url,
        )
    except RuntimeError:
        return None

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        return None

    return _parse_response(content)
