from __future__ import annotations

import unittest

from runtime.output import format_summary_output


class TestSummaryOutputFormat(unittest.TestCase):
    def test_inserts_params_after_bold_title(self):
        content = "**2026-05-22 项目周会总结**\n\n## 会议概览\n\n- 内容"
        result = format_summary_output(content, "| 模型: test |")

        self.assertEqual(
            result,
            "**2026-05-22 项目周会总结**\n| 模型: test |\n\n## 会议概览\n\n- 内容",
        )

    def test_inserts_params_after_markdown_heading_title(self):
        content = "## 会议概览\n\n- 内容"
        result = format_summary_output(content, "| 模型: test |")

        self.assertEqual(result, "## 会议概览\n| 模型: test |\n\n- 内容")

    def test_appends_params_when_content_has_no_title(self):
        content = "- 内容"
        result = format_summary_output(content, "| 模型: test |")

        self.assertEqual(result, "- 内容\n\n| 模型: test |")


if __name__ == "__main__":
    unittest.main()
