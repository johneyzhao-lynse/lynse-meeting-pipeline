from __future__ import annotations

from pathlib import Path

from .models import ClassifierResult
from .scene_instructions import get_scene_instruction


def compose_dynamic_template(
    classification: ClassifierResult,
    *,
    base_template_path: Path,
    transcript_char_count: int = 0,
    current_date: str | None = None,
) -> str:
    base_text = base_template_path.read_text(encoding="utf-8")

    enhancements: list[str] = []

    for label in classification.scene_labels:
        instruction = get_scene_instruction(label)
        if instruction is None:
            continue
        special = instruction.get("special_requirements", [])
        if special:
            enhancements.append(f"## {label}场景增强指令\n")
            for req in special:
                enhancements.append(f"- {req}")
            enhancements.append("")

    if transcript_char_count > 0:
        estimated_minutes = max(1, transcript_char_count // 100)
        if estimated_minutes <= 5:
            duration_hint = "本转写约{0}字符（预计{1}分钟），请生成200字以内的精炼总结。".format(
                transcript_char_count, estimated_minutes,
            )
        elif estimated_minutes <= 30:
            duration_hint = "本转写约{0}字符（预计{1}分钟），请生成适度详细的总结。".format(
                transcript_char_count, estimated_minutes,
            )
        else:
            duration_hint = "本转写约{0}字符（预计{1}分钟），请通读全文后生成深度总结，注意不要遗漏中段的关键信息。".format(
                transcript_char_count, estimated_minutes,
            )
        enhancements.append(duration_hint)

    if current_date:
        enhancements.append(
            "当前日期为{0}，请注意时效性：如文本中出现「下周」「明天」等相对时间，请转换为绝对日期。".format(
                current_date,
            )
        )

    if not enhancements:
        return base_text

    insertion = "\n# 动态增强指令\n\n" + "\n".join(enhancements)
    return base_text.rstrip() + "\n" + insertion + "\n"
