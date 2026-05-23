import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime import assets, cli


class RefactorRuntimeTest(unittest.TestCase):
    def test_asset_roots_are_unified_under_new_structure(self):
        root = Path(__file__).resolve().parents[1]

        self.assertEqual(assets.ASSETS_ROOT, root / "assets")
        self.assertEqual(assets.INDUSTRY_DIR, root / "assets" / "prompts" / "industries")
        self.assertEqual(assets.TEMPLATE_DIR, root / "assets" / "templates" / "summary")

    def test_formal_scenario_legacy_directory_has_been_removed(self):
        root = Path(__file__).resolve().parents[1]
        self.assertFalse((root / "archive" / "process-files" / "正式场景联调测试").exists())

    def test_current_assets_contain_known_migrated_files(self):
        self.assertIn("marketing-campaign-planning.md", assets.available_files(assets.TEMPLATE_DIR))
        self.assertIn("marketing-industry.md", assets.available_files(assets.INDUSTRY_DIR))
        self.assertNotIn("sensitive-content-neutral-summary.md", assets.available_files(assets.INDUSTRY_DIR))

    def test_list_command_reads_from_new_asset_directories(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main(["--list"])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("marketing-industry.md", output)
        self.assertIn("marketing-campaign-planning.md", output)
        self.assertIn("2026-04-20 16:01:10.txt", output)

    def test_dry_run_redacts_transcript_by_default(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "--industry",
                    "insurance-industry.md",
                    "--template",
                    "insurance-claim-communication.md",
                    "--transcript",
                    "2026-04-20 16:01:10.txt",
                    "--dry-run",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        user_message = payload["messages"][1]["content"]
        self.assertIn("[dry-run 默认隐藏转写全文", user_message)
        self.assertNotIn("其实不是希望他有有", user_message)

    def test_dry_run_full_includes_transcript_text(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli.main(
                [
                    "--industry",
                    "insurance-industry.md",
                    "--template",
                    "insurance-claim-communication.md",
                    "--transcript",
                    "2026-04-20 16:01:10.txt",
                    "--dry-run",
                    "--dry-run-full",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        user_message = payload["messages"][1]["content"]
        self.assertIn("其实不是希望他有有", user_message)
        self.assertNotIn("[dry-run 默认隐藏转写全文", user_message)

    def test_missing_file_returns_clear_error(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = cli.main(
                [
                    "--industry",
                    "不存在.md",
                    "--template",
                    "insurance-claim-communication.md",
                    "--transcript",
                    "2026-04-20 16:01:10.txt",
                    "--dry-run",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertIn("File not found", stderr.getvalue())

    def test_strict_mode_still_replaces_user_template(self):
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            platform_file = tmp_path / "platform.md"
            industry_prompt = tmp_path / "industry.md"
            template = tmp_path / "template.md"
            transcript = tmp_path / "transcript.txt"

            platform_file.write_text("平台提示词", encoding="utf-8")
            industry_prompt.write_text("行业提示词", encoding="utf-8")
            template.write_text("## 自定义结构", encoding="utf-8")
            transcript.write_text("普通版本讨论。", encoding="utf-8")

            messages = cli.build_messages(
                industry_prompt_path=industry_prompt,
                template_path=template,
                transcript_path=transcript,
                user_style="专业",
                safety_mode="strict",
                platform_prompt_path=platform_file,
            )

        self.assertIn("## 安全与合规风险", messages[1]["content"])
        self.assertNotIn("## 自定义结构", messages[1]["content"])


if __name__ == "__main__":
    unittest.main()
