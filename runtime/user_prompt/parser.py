from __future__ import annotations

from .models import UserPrompt


def _extract_block(markdown: str, heading: str) -> str:
    marker = f"# {heading}"
    if marker not in markdown:
        return ""
    tail = markdown.split(marker, 1)[1]
    next_heading_index = tail.find("\n# ")
    block = tail[:next_heading_index] if next_heading_index != -1 else tail
    return block.strip()


def parse_user_prompt_markdown(markdown: str) -> UserPrompt:
    summary_goal = _extract_block(markdown, "总结目标").splitlines()[0].strip() if _extract_block(markdown, "总结目标") else ""
    target_audience = _extract_block(markdown, "目标读者").splitlines()[0].strip() if _extract_block(markdown, "目标读者") else ""
    output_block = _extract_block(markdown, "输出结构")
    sections = [line.replace("##", "", 1).strip() for line in output_block.splitlines() if line.strip().startswith("## ")]
    special_block = _extract_block(markdown, "特殊要求")
    requirements = [line[1:].strip() for line in special_block.splitlines() if line.strip().startswith("-")]
    return UserPrompt(
        summary_goal=summary_goal,
        target_audience=target_audience,
        output_sections=sections,
        special_requirements=requirements,
    )
