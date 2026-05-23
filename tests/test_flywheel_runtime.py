import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from runtime import cli
from runtime.agent.config import AgentConfig, load_model_pair_config
from runtime.flywheel.models import FeedbackRecord
from runtime.flywheel.analysis import build_reasoning_analysis_messages, write_analysis_record


class FlywheelRuntimeTest(unittest.TestCase):
    def test_model_pair_config_keeps_summary_and_reasoning_separate(self):
        with patch.dict(
            "os.environ",
            {
                "SUMMARY_MODEL": "summary-fast",
                "SUMMARY_BASE_URL": "https://summary.example.test",
                "SUMMARY_API_KEY": "summary-key",
                "REASONING_MODEL": "reasoning-deep",
                "REASONING_BASE_URL": "https://reasoning.example.test",
                "REASONING_API_KEY": "reasoning-key",
            },
            clear=True,
        ):
            pair = load_model_pair_config(root=Path("/tmp/not-used"))

        self.assertEqual(pair.summary.model, "summary-fast")
        self.assertEqual(pair.summary.base_url, "https://summary.example.test")
        self.assertEqual(pair.summary.api_key, "summary-key")
        self.assertEqual(pair.reasoning.model, "reasoning-deep")
        self.assertEqual(pair.reasoning.base_url, "https://reasoning.example.test")
        self.assertEqual(pair.reasoning.api_key, "reasoning-key")

    def test_summary_run_log_contains_flywheel_fields_and_summary_model(self):
        response = {"choices": [{"message": {"content": "## 会议概览\n\n- 已生成总结\n"}}]}
        stdout = io.StringIO()
        stderr = io.StringIO()

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "summary.md"
            log_path = Path(tmp_dir) / "run-log.json"
            with patch("runtime.cli.call_litellm", return_value=response) as call:
                with patch("runtime.cli.load_agent_config") as load_config:
                    load_config.return_value = AgentConfig(
                        api_key_value="summary-key",
                        model="summary-model",
                        base_url="https://summary.example.test",
                    )
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = cli.main([
                            "--industry", "insurance-industry.md",
                            "--template", "insurance-claim-communication.md",
                            "--transcript", "2026-04-20 16:01:10.txt",
                            "--output", str(output_path),
                            "--run-log-output", str(log_path),
                        ])

            log_data = json.loads(log_path.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(log_data["summary_model"], "summary-model")
        self.assertEqual(log_data["template_name"], "insurance-claim-communication.md")
        self.assertEqual(log_data["industry"], "insurance-industry.md")
        self.assertEqual(log_data["scene_type"], "保险理赔沟通")
        self.assertEqual(log_data["prompt_version"], "v1")
        self.assertEqual(log_data["transcript_id"], "2026-04-20 16:01:10")
        self.assertIn("created_at", log_data)
        self.assertEqual(call.call_args.kwargs["model"], "summary-model")
        self.assertEqual(call.call_args.kwargs["base_url"], "https://summary.example.test")

    def test_reasoning_analysis_record_uses_reasoning_model(self):
        feedback = FeedbackRecord(
            summary_id="summary-1",
            feedback_type="漏信息",
            severity="high",
            user_comment="没有提取理赔材料清单",
            preferred_fix="补充材料清单和待确认事项",
        )
        messages = build_reasoning_analysis_messages(
            samples=[
                {
                    "summary_id": "summary-1",
                    "transcript": "客户沟通理赔材料、病历和发票。",
                    "summary": "## 会议概览\n\n- 客户咨询理赔。",
                }
            ],
            feedbacks=[feedback],
            analysis_goal="提炼保险理赔沟通总结的可执行改进规则",
        )

        self.assertIn("提示词优化建议", messages[0]["content"])
        self.assertIn("没有提取理赔材料清单", messages[1]["content"])

        with TemporaryDirectory() as tmp_dir:
            path = write_analysis_record(
                Path(tmp_dir),
                sample_ids=["summary-1"],
                reasoning_model="reasoning-deep",
                analysis_goal="提炼保险理赔沟通总结的可执行改进规则",
                findings=["理赔材料是高频缺失字段"],
                recommended_prompt_changes=["在保险模板中要求列出材料清单"],
            )
            data = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(data["reasoning_model"], "reasoning-deep")
        self.assertEqual(data["review_status"], "pending")
        self.assertEqual(data["sample_ids"], ["summary-1"])


if __name__ == "__main__":
    unittest.main()
