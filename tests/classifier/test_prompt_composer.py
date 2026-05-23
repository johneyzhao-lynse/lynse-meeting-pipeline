from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from runtime.classifier.models import (
    Candidate,
    CandidateRanking,
    ClassifierResult,
)
from runtime.classifier.prompt_composer import compose_dynamic_template
from runtime.classifier.scene_instructions import get_all_scene_labels, get_scene_instruction
from runtime.messages import build_messages


def _make_classification(scene_labels=None, template="general-meeting.md") -> ClassifierResult:
    if scene_labels is None:
        scene_labels = ["会议协作"]
    return ClassifierResult(
        scene_labels=scene_labels,
        industry_labels=[],
        intent_labels=["总结"],
        output_shape=["会议概览", "关键讨论"],
        recommended_template=template,
        recommended_industry_prompt=None,
        confidence=0.85,
        fallback_used=False,
        fallback_reason=None,
        evidence_keywords=["会议"],
        reason_summary="测试",
        candidate_ranking=CandidateRanking(
            templates=[Candidate(name=template, score=10.0)],
            industries=[],
        ),
        feature_summary={"char_count": 100, "speaker_count": 2, "keyword_hits": {}},
    )


def _make_base_template(content: str | None = None) -> Path:
    if content is None:
        content = (
            "# 模板说明\n\n测试模板\n\n"
            "# 总结目标\n\n生成总结\n\n"
            "# 输出结构\n\n## 概览\n\n概述\n\n"
            "# 特殊要求\n\n- 要求1\n"
        )
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


class TestComposeDynamicTemplate(unittest.TestCase):
    def test_compose_dynamic_template_appends_to_base(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification(scene_labels=["客户沟通"])
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
            )
            self.assertIn("# 模板说明", result)
            self.assertIn("测试模板", result)
            self.assertIn("动态增强指令", result)
            self.assertIn("客户沟通场景增强指令", result)
        finally:
            base_path.unlink()

    def test_compose_dynamic_template_includes_date_hint(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification()
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
                current_date="2026-05-22",
            )
            self.assertIn("2026-05-22", result)
            self.assertIn("请注意时效性", result)
        finally:
            base_path.unlink()

    def test_compose_dynamic_template_includes_duration_hint(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification()
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
                transcript_char_count=500,
            )
            self.assertIn("500字符", result)
            self.assertIn("精炼总结", result)
        finally:
            base_path.unlink()

    def test_compose_dynamic_template_long_transcript_hint(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification()
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
                transcript_char_count=6000,
            )
            self.assertIn("6000字符", result)
            self.assertIn("深度总结", result)
        finally:
            base_path.unlink()

    def test_compose_dynamic_template_unknown_scene_still_works(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification(scene_labels=["未知场景"])
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
                current_date="2026-01-01",
                transcript_char_count=1000,
            )
            self.assertIn("1000字符", result)
            self.assertIn("2026-01-01", result)
            self.assertNotIn("未知场景场景增强指令", result)
        finally:
            base_path.unlink()

    def test_compose_dynamic_template_no_enhancements_returns_base(self):
        base_path = _make_base_template()
        try:
            classification = _make_classification(scene_labels=["未知场景"])
            result = compose_dynamic_template(
                classification,
                base_template_path=base_path,
            )
            base = base_path.read_text(encoding="utf-8")
            self.assertEqual(result, base)
        finally:
            base_path.unlink()


class TestBuildMessagesDynamicTemplate(unittest.TestCase):
    def test_build_messages_user_prompt_takes_priority(self):
        base_path = _make_base_template("base template content")
        transcript_path = _make_base_template("transcript content")
        platform_path = _make_base_template("platform prompt")
        try:
            messages = build_messages(
                industry_prompt_path=None,
                template_path=base_path,
                transcript_path=transcript_path,
                user_style="test style",
                platform_prompt_path=platform_path,
                user_prompt_text="USER PROMPT TEXT",
                dynamic_template_text="DYNAMIC TEMPLATE TEXT",
            )
            user_msg = messages[1]["content"]
            self.assertIn("USER PROMPT TEXT", user_msg)
            self.assertNotIn("DYNAMIC TEMPLATE TEXT", user_msg)
        finally:
            base_path.unlink()
            transcript_path.unlink()
            platform_path.unlink()

    def test_build_messages_dynamic_over_file(self):
        base_path = _make_base_template("base template content")
        transcript_path = _make_base_template("transcript content")
        platform_path = _make_base_template("platform prompt")
        try:
            messages = build_messages(
                industry_prompt_path=None,
                template_path=base_path,
                transcript_path=transcript_path,
                user_style="test style",
                platform_prompt_path=platform_path,
                dynamic_template_text="DYNAMIC TEMPLATE TEXT",
            )
            user_msg = messages[1]["content"]
            self.assertIn("DYNAMIC TEMPLATE TEXT", user_msg)
            self.assertNotIn("base template content", user_msg)
        finally:
            base_path.unlink()
            transcript_path.unlink()
            platform_path.unlink()

    def test_build_messages_no_dynamic_falls_to_file(self):
        base_path = _make_base_template("base template content")
        transcript_path = _make_base_template("transcript content")
        platform_path = _make_base_template("platform prompt")
        try:
            messages = build_messages(
                industry_prompt_path=None,
                template_path=base_path,
                transcript_path=transcript_path,
                user_style="test style",
                platform_prompt_path=platform_path,
            )
            user_msg = messages[1]["content"]
            self.assertIn("base template content", user_msg)
        finally:
            base_path.unlink()
            transcript_path.unlink()
            platform_path.unlink()


class TestSceneInstructions(unittest.TestCase):
    def test_all_scene_labels_have_instructions(self):
        for label in get_all_scene_labels():
            instruction = get_scene_instruction(label)
            self.assertIsNotNone(instruction, f"Missing instruction for scene label: {label}")
            self.assertIn("target_audience", instruction)
            self.assertIn("special_requirements", instruction)


if __name__ == "__main__":
    unittest.main()
