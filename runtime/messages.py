from __future__ import annotations

import json
from pathlib import Path

from .assets import PLATFORM_PROMPT, read_text
from .safety import (
    SAFETY_SYSTEM_CONSTRAINT,
    SAFETY_USER_BOUNDARY_TEMPLATE,
    STRICT_FINAL_INSTRUCTION,
    STRICT_SYSTEM_CONSTRAINT,
    STRICT_USER_TEMPLATE,
    detect_safety_risks,
    should_apply_safety_constraints,
)


def _normalize_system_part(content: str) -> str:
    return content.replace("\n\n---\n\n", "\n\n")


def build_messages(
    *,
    industry_prompt_path: Path | None,
    template_path: Path,
    transcript_path: Path,
    user_style: str,
    safety_mode: str = "auto",
    platform_prompt_path: Path = PLATFORM_PROMPT,
    user_prompt_text: str | None = None,
    dynamic_template_text: str | None = None,
    profile_prompt_text: str | None = None,
    meeting_type: str | None = None,
    meeting_date: str | None = None,
) -> list[dict[str, str]]:
    transcript_text = read_text(transcript_path)
    safety_risks = detect_safety_risks(transcript_text)
    apply_safety = should_apply_safety_constraints(safety_mode, safety_risks)

    system_parts = [
        _normalize_system_part(read_text(platform_prompt_path)),
    ]
    if industry_prompt_path is not None:
        system_parts.append(_normalize_system_part(read_text(industry_prompt_path)))
    if apply_safety:
        system_parts.append(SAFETY_SYSTEM_CONSTRAINT)
    if safety_mode == "strict":
        system_parts.append(STRICT_SYSTEM_CONSTRAINT)

    system_prompt = "\n\n---\n\n".join(system_parts)

    if safety_mode == "strict":
        template_text = STRICT_USER_TEMPLATE
    elif user_prompt_text is not None:
        template_text = user_prompt_text
    elif dynamic_template_text is not None:
        template_text = dynamic_template_text
    else:
        template_text = read_text(template_path)
    if profile_prompt_text is not None and user_prompt_text is None and safety_mode != "strict":
        template_text = template_text.rstrip() + "\n\n---\n\n" + profile_prompt_text.strip() + "\n"
    user_parts = [
        f"# 用户个性化风格\n\n{user_style.strip()}",
        f"# 用户总结模板\n\n{template_text}",
    ]
    if apply_safety:
        risk_labels = ", ".join(safety_risks) if safety_risks else "strict_mode_no_local_hit"
        user_parts.append(SAFETY_USER_BOUNDARY_TEMPLATE.format(risk_labels=risk_labels))
    user_parts.append(f"# 录音转写文本\n\n{transcript_text}")
    if safety_mode == "strict":
        user_parts.append(STRICT_FINAL_INSTRUCTION)

    if meeting_type:
        date_hint = f"日期为{meeting_date}" if meeting_date else "日期从转写文本中提取"
        title_instruction = (
            f"# 标题生成要求\n\n"
            f"在总结正文最前面，先用一行输出会议标题，格式为：\n"
            f"**MM-DD {meeting_type}：会议主题**\n"
            f"其中{date_hint}，会议类型为「{meeting_type}」，"
            f"会议主题请根据转写内容用一句话概括（不超过20字）。"
            f"标题行之后空一行再开始总结正文。"
        )
        user_parts.append(title_instruction)

    user_prompt = "\n\n---\n\n".join(user_parts)

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def redact_payload_for_preview(payload: dict, transcript_path: Path, risks: list[str]) -> dict:
    preview = json.loads(json.dumps(payload, ensure_ascii=False))
    marker = (
        f"# 录音转写文本\n\n"
        f"[dry-run 默认隐藏转写全文；文件：{transcript_path}；"
        f"字符数：{len(read_text(transcript_path))}；"
        f"风险标签：{', '.join(risks) if risks else 'none'}]"
    )
    for message in preview.get("messages", []):
        if message.get("role") == "user" and "# 录音转写文本" in message.get("content", ""):
            before, _, _after = message["content"].partition("# 录音转写文本")
            message["content"] = before + marker
    return preview
