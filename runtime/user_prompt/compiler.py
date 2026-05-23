from __future__ import annotations

from .models import UserPrompt


def compile_user_prompt(prompt: UserPrompt) -> str:
    lines = ["# 总结目标", prompt.summary_goal or "未提供", ""]
    if prompt.target_audience:
        lines.extend(["# 目标读者", prompt.target_audience, ""])
    lines.extend(["# 输出结构", ""])
    for section in prompt.output_sections:
        lines.extend([f"## {section}", ""])
    if prompt.special_requirements:
        lines.extend(["# 特殊要求", ""])
        for requirement in prompt.special_requirements:
            lines.append(f"- {requirement}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
