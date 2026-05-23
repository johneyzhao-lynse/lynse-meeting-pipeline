from __future__ import annotations

import json
import unittest
from unittest.mock import patch, MagicMock

from runtime.classifier.meeting_classifier import (
    MeetingClassification,
    _parse_response,
    _validate,
    classify_meeting,
    VALID_MEETING_TYPES,
    VALID_MEETING_MODES,
    TYPE_TO_CATEGORY,
)
from runtime.classifier.meeting_types import (
    MeetingInfo,
    get_meeting_info,
    get_meeting_type,
    MEETING_TYPE_TO_CATEGORY,
    MEETING_TYPE_TO_MODE,
    TEMPLATE_MEETING_TYPE,
)


class TestMeetingClassification(unittest.TestCase):
    def test_as_dict(self):
        mc = MeetingClassification(meeting_type="合作洽谈会", meeting_category="销售类", meeting_mode="谈判型")
        d = mc.as_dict()
        self.assertEqual(d["meeting_type"], "合作洽谈会")
        self.assertEqual(d["meeting_category"], "销售类")
        self.assertEqual(d["meeting_mode"], "谈判型")


class TestValidate(unittest.TestCase):
    def test_valid_all_fields(self):
        result = _validate({
            "meeting_type": "产品周会",
            "meeting_category": "产品类",
            "meeting_mode": "同步型",
        })
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_type, "产品周会")
        self.assertEqual(result.meeting_category, "产品类")
        self.assertEqual(result.meeting_mode, "同步型")

    def test_invalid_meeting_type(self):
        result = _validate({"meeting_type": "不存在的类型", "meeting_mode": "同步型"})
        self.assertIsNone(result)

    def test_invalid_meeting_mode(self):
        result = _validate({"meeting_type": "产品周会", "meeting_mode": "不存在的模式"})
        self.assertIsNone(result)

    def test_missing_meeting_type(self):
        result = _validate({"meeting_mode": "同步型"})
        self.assertIsNone(result)

    def test_category_derived_from_type(self):
        result = _validate({"meeting_type": "面试", "meeting_mode": "评估型"})
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_category, "人力类")

    def test_other_type_maps_to_other_category(self):
        result = _validate({"meeting_type": "其他", "meeting_mode": "同步型"})
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_category, "其他")


class TestParseResponse(unittest.TestCase):
    def test_valid_json(self):
        raw = json.dumps({
            "meeting_type": "合作洽谈会",
            "meeting_category": "销售类",
            "meeting_mode": "谈判型",
        })
        result = _parse_response(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_type, "合作洽谈会")

    def test_json_with_code_fences(self):
        raw = "```json\n" + json.dumps({
            "meeting_type": "销售会议",
            "meeting_mode": "谈判型",
        }) + "\n```"
        result = _parse_response(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_type, "销售会议")

    def test_invalid_json(self):
        result = _parse_response("not json at all")
        self.assertIsNone(result)

    def test_invalid_type_in_json(self):
        raw = json.dumps({"meeting_type": "不存在的", "meeting_mode": "同步型"})
        result = _parse_response(raw)
        self.assertIsNone(result)

    def test_non_dict_json(self):
        raw = json.dumps(["meeting_type", "产品周会"])
        result = _parse_response(raw)
        self.assertIsNone(result)


class TestClassifyMeeting(unittest.TestCase):
    @patch("runtime.classifier.meeting_classifier.call_litellm")
    @patch("runtime.classifier.meeting_classifier.read_text")
    def test_llm_success(self, mock_read_text, mock_call):
        mock_read_text.return_value = "classifier prompt text"
        mock_call.return_value = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "meeting_type": "需求评审会",
                        "meeting_category": "产品类",
                        "meeting_mode": "评估型",
                    })
                }
            }]
        }
        config = MagicMock()
        config.api_key = "test-key"
        config.call_params = MagicMock()
        config.call_params.max_tokens = 1000
        config.call_params.temperature = 0.1
        config.call_params.thinking = "disabled"
        config.call_params.reasoning_effort = None
        config.base_url = "https://api.test.com"

        result = classify_meeting("一些会议转写文本", classifier_config=config)
        self.assertIsNotNone(result)
        self.assertEqual(result.meeting_type, "需求评审会")
        self.assertEqual(result.meeting_category, "产品类")
        self.assertEqual(result.meeting_mode, "评估型")

    @patch("runtime.classifier.meeting_classifier.call_litellm")
    @patch("runtime.classifier.meeting_classifier.read_text")
    def test_llm_api_failure_fallback(self, mock_read_text, mock_call):
        mock_read_text.return_value = "classifier prompt text"
        mock_call.side_effect = RuntimeError("API error")
        config = MagicMock()
        config.api_key = "test-key"
        config.call_params = MagicMock()
        config.call_params.max_tokens = 1000
        config.call_params.temperature = 0.1
        config.call_params.thinking = "disabled"
        config.call_params.reasoning_effort = None
        config.base_url = "https://api.test.com"

        result = classify_meeting("一些会议转写文本", classifier_config=config)
        self.assertIsNone(result)

    @patch("runtime.classifier.meeting_classifier.call_litellm")
    @patch("runtime.classifier.meeting_classifier.read_text")
    def test_llm_invalid_response_fallback(self, mock_read_text, mock_call):
        mock_read_text.return_value = "classifier prompt text"
        mock_call.return_value = {
            "choices": [{"message": {"content": "invalid json"}}]
        }
        config = MagicMock()
        config.api_key = "test-key"
        config.call_params = MagicMock()
        config.call_params.max_tokens = 1000
        config.call_params.temperature = 0.1
        config.call_params.thinking = "disabled"
        config.call_params.reasoning_effort = None
        config.base_url = "https://api.test.com"

        result = classify_meeting("一些会议转写文本", classifier_config=config)
        self.assertIsNone(result)

    @patch("runtime.classifier.meeting_classifier.call_litellm")
    @patch("runtime.classifier.meeting_classifier.read_text")
    def test_preview_chars_limit(self, mock_read_text, mock_call):
        mock_read_text.return_value = "prompt"
        mock_call.return_value = {
            "choices": [{"message": {"content": json.dumps({
                "meeting_type": "其他", "meeting_mode": "同步型",
            })}}]
        }
        config = MagicMock()
        config.api_key = "test-key"
        config.call_params = MagicMock()
        config.call_params.max_tokens = 1000
        config.call_params.temperature = 0.1
        config.call_params.thinking = "disabled"
        config.call_params.reasoning_effort = None
        config.base_url = "https://api.test.com"

        long_transcript = "x" * 5000
        classify_meeting(long_transcript, classifier_config=config, preview_chars=100)

        call_args = mock_call.call_args
        user_msg = call_args.kwargs["messages"][1]["content"]
        self.assertLessEqual(len(user_msg), 100)


class TestMeetingInfo(unittest.TestCase):
    def test_meeting_info_as_dict(self):
        info = MeetingInfo(meeting_type="产品周会", meeting_category="产品类", meeting_mode="同步型")
        d = info.as_dict()
        self.assertEqual(d["meeting_type"], "产品周会")
        self.assertEqual(d["meeting_category"], "产品类")
        self.assertEqual(d["meeting_mode"], "同步型")

    def test_get_meeting_info_known_template(self):
        info = get_meeting_info("product-analysis.md")
        self.assertEqual(info.meeting_type, "产品周会")
        self.assertEqual(info.meeting_category, "产品类")
        self.assertEqual(info.meeting_mode, "同步型")

    def test_get_meeting_info_unknown_template(self):
        info = get_meeting_info("nonexistent-template.md")
        self.assertEqual(info.meeting_type, "其他")
        self.assertEqual(info.meeting_category, "其他")

    def test_get_meeting_type_new_templates(self):
        self.assertEqual(get_meeting_type("channel-meeting.md"), "渠道会议")
        self.assertEqual(get_meeting_type("sales-follow-up.md"), "销售会议")
        self.assertEqual(get_meeting_type("financial-survey-visit.md"), "银企访谈")


class TestCategoryMappingConsistency(unittest.TestCase):
    def test_all_template_types_have_category(self):
        for template, meeting_type in TEMPLATE_MEETING_TYPE.items():
            self.assertIn(meeting_type, MEETING_TYPE_TO_CATEGORY,
                          f"Missing category for meeting_type '{meeting_type}' (template: {template})")

    def test_all_template_types_have_mode(self):
        for template, meeting_type in TEMPLATE_MEETING_TYPE.items():
            self.assertIn(meeting_type, MEETING_TYPE_TO_MODE,
                          f"Missing mode for meeting_type '{meeting_type}' (template: {template})")

    def test_classifier_type_to_category_matches_meeting_types(self):
        for meeting_type in VALID_MEETING_TYPES:
            self.assertIn(meeting_type, TYPE_TO_CATEGORY,
                          f"Missing TYPE_TO_CATEGORY for '{meeting_type}'")

    def test_category_matches_between_modules(self):
        for mt, cat in MEETING_TYPE_TO_CATEGORY.items():
            self.assertEqual(TYPE_TO_CATEGORY.get(mt), cat,
                             f"Mismatch for '{mt}': meeting_types says '{cat}', classifier says '{TYPE_TO_CATEGORY.get(mt)}'")


if __name__ == "__main__":
    unittest.main()
