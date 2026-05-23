import io
import importlib.util
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from runtime import cli
from runtime.agent.config import AgentConfig


ROOT = Path(__file__).resolve().parents[1]


def load_module_from_path(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CliIntegrationTest(unittest.TestCase):
    def test_agent_launcher_reexecs_project_venv_on_python39(self):
        launcher = load_module_from_path("lynclaw_agent_launcher_test", ROOT / "tools" / "lynclaw_agent.py")
        with TemporaryDirectory() as tmp_dir:
            venv_python = Path(tmp_dir) / "python"
            venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
            venv_dir = Path(tmp_dir) / ".venv"
            venv_dir.mkdir(parents=True, exist_ok=True)
            with patch.object(launcher.sys, "version_info", (3, 9, 6)), \
                patch.object(launcher.sys, "prefix", "/usr"), \
                patch.object(launcher.sys, "executable", "/usr/bin/python3"), \
                patch.object(launcher, "_project_venv_python", return_value=venv_python), \
                patch.object(launcher, "ROOT", Path(tmp_dir)), \
                patch.object(launcher.os, "execv") as execv:
                launcher._maybe_reexec_with_venv()

        execv.assert_called_once()
        self.assertEqual(execv.call_args.args[0], str(venv_python))

    def test_auto_route_dry_run_includes_classification_route(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main(["--auto-route", "--transcript", "2026-04-20 16:01:10.txt", "--dry-run"])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertIn("classification", payload)
        self.assertIn("messages", payload)
        self.assertIsNotNone(payload["classification"]["recommended_industry_prompt"])
        self.assertTrue(payload["classification"]["recommended_industry_prompt"].endswith(".md"))
        self.assertIn("\n\n---\n\n", payload["messages"][0]["content"])

    def test_manual_mode_does_not_require_classifier(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = cli.main([
                "--industry", "insurance-industry.md",
                "--template", "insurance-claim-communication.md",
                "--transcript", "2026-04-20 16:01:10.txt",
                "--dry-run",
            ])
        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertNotIn("classification", payload)

    def test_reactive_mode_retries_only_for_sensitive_api_failure(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        responses = [
            RuntimeError('DeepSeek API HTTP 400: {"error":{"code":"content_filter","message":"sensitive content"}}'),
            {"choices": [{"message": {"content": "## 会议概览\n\n- 已恢复输出\n\n## 后续行动\n\n- 无"}}]},
        ]

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "retry.md"
            log_path = Path(tmp_dir) / "retry-log.json"
            with patch("runtime.cli.call_litellm", side_effect=responses):
                with patch("runtime.cli.load_agent_config") as load_config:
                    load_config.return_value = AgentConfig(
                        api_key_value="sk-test",
                        model="agent-model",
                        base_url="https://llm.example.test",
                    )
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = cli.main([
                            "--industry", "marketing-industry.md",
                            "--template", "general-meeting.md",
                            "--transcript", "04-27 产品：1.06版本功能评审与上架安排.txt",
                            "--safety-mode", "reactive",
                            "--output", str(output_path),
                            "--run-log-output", str(log_path),
                        ])
            log_data = json.loads(log_path.read_text(encoding="utf-8"))
            summary_text = output_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("已恢复输出", summary_text)
        self.assertIn("sensitive-content filter", stderr.getvalue())
        self.assertEqual(log_data["attempts"][0]["reason"], "sensitive_api_failure")

    def test_successful_run_writes_summary_and_run_log_without_printing_summary(self):
        response = {"choices": [{"message": {"content": "**2026-04-20 保险理赔沟通总结**\n\n## 会议概览\n\n- 已生成总结\n\n## 后续行动\n\n- 无"}}]}
        stdout = io.StringIO()
        stderr = io.StringIO()

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "summary.md"
            log_path = Path(tmp_dir) / "run-log.json"
            with patch("runtime.cli.call_litellm", return_value=response) as call:
                with patch("runtime.cli.load_agent_config") as load_config:
                    load_config.return_value = AgentConfig(
                        api_key_value="sk-test",
                        model="agent-model",
                        base_url="https://llm.example.test",
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
            summary_text = output_path.read_text(encoding="utf-8")

            self.assertEqual(code, 0)
            self.assertEqual(stdout.getvalue(), "")
            self.assertTrue(summary_text.startswith("**2026-04-20 保险理赔沟通总结**\n| 模型: agent-model"))
            self.assertIn("已生成总结", summary_text)
            self.assertIn("Saved summary", stderr.getvalue())
            self.assertEqual(log_data["final_status"], "success")
            self.assertEqual(log_data["output_path"], str(output_path))
            self.assertNotIn("已生成总结", json.dumps(log_data, ensure_ascii=False))
            self.assertEqual(call.call_args.kwargs["model"], "agent-model")
            self.assertEqual(call.call_args.kwargs["reasoning_effort"], "medium")
            self.assertEqual(call.call_args.kwargs["base_url"], "https://llm.example.test")

    def test_reasoning_effort_accepts_chinese_shortcut(self):
        response = {"choices": [{"message": {"content": "**标题**\n\n正文"}}]}

        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "summary.md"
            log_path = Path(tmp_dir) / "run-log.json"
            with patch("runtime.cli.call_litellm", return_value=response) as call:
                with patch("runtime.cli.load_agent_config") as load_config:
                    load_config.return_value = AgentConfig(
                        api_key_value="sk-test",
                        model="agent-model",
                        base_url="https://llm.example.test",
                    )
                    code = cli.main([
                        "--industry", "insurance-industry.md",
                        "--template", "insurance-claim-communication.md",
                        "--transcript", "2026-04-20 16:01:10.txt",
                        "--reasoning-effort", "高",
                        "--output", str(output_path),
                        "--run-log-output", str(log_path),
                    ])

        self.assertEqual(code, 0)
        self.assertEqual(call.call_args.kwargs["reasoning_effort"], "high")
