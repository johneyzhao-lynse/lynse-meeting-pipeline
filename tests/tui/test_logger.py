from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.tui.logger import SessionLogger


class TestSessionLogger(unittest.TestCase):
    def test_creates_log_directory(self):
        with TemporaryDirectory() as tmp_dir:
            log_dir = Path(tmp_dir) / "logs"
            logger = SessionLogger(log_dir=log_dir)
            self.assertTrue(log_dir.exists())

    def test_log_writes_jsonl(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir), session_id="test-session")
            logger.log("test_event", data={"key": "value"})
            content = logger.log_path.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            self.assertEqual(len(lines), 1)
            entry = json.loads(lines[0])
            self.assertEqual(entry["event"], "test_event")
            self.assertEqual(entry["session_id"], "test-session")
            self.assertEqual(entry["data"]["key"], "value")
            self.assertIn("ts", entry)

    def test_log_command(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            logger.log_command("/run", args="--dry-run")
            entry = logger.entries[-1]
            self.assertEqual(entry["event"], "command")
            self.assertEqual(entry["data"]["command"], "/run")
            self.assertEqual(entry["data"]["args"], "--dry-run")

    def test_log_classification(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            result = {
                "recommended_template": "product-analysis.md",
                "recommended_industry_prompt": None,
                "confidence": 0.82,
                "fallback_used": False,
                "fallback_reason": None,
                "scene_labels": ["技术讨论"],
                "intent_labels": ["问题诊断"],
                "evidence_keywords": ["产品", "版本"],
                "candidate_ranking": {
                    "templates": [{"name": "product-analysis.md", "score": 30.5}],
                },
            }
            logger.log_classification("test.txt", result)
            entry = logger.entries[-1]
            self.assertEqual(entry["event"], "classification")
            self.assertEqual(entry["data"]["transcript"], "test.txt")
            self.assertEqual(entry["data"]["recommended_template"], "product-analysis.md")
            self.assertEqual(entry["data"]["confidence"], 0.82)

    def test_log_generation(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            logger.log_generation(
                transcript="test.txt",
                template="general-meeting.md",
                industry=None,
                safety_mode="reactive",
                model="deepseek-chat",
                thinking="disabled",
                temperature=0.2,
                max_tokens=3000,
                safety_risks=[],
                token_usage={"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700},
                attempt_count=2,
                final_status="success",
                output_path="/tmp/out.md",
            )
            entry = logger.entries[-1]
            self.assertEqual(entry["event"], "generation")
            self.assertEqual(entry["data"]["token_usage"]["total_tokens"], 700)
            self.assertEqual(entry["data"]["attempt_count"], 2)

    def test_log_config_change(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            logger.log_config_change("safety_mode", "reactive", "strict")
            entry = logger.entries[-1]
            self.assertEqual(entry["event"], "config_change")
            self.assertEqual(entry["data"]["key"], "safety_mode")
            self.assertEqual(entry["data"]["old"], "reactive")
            self.assertEqual(entry["data"]["new"], "strict")

    def test_multiple_entries_append(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            logger.log("event1")
            logger.log("event2")
            logger.log("event3")
            content = logger.log_path.read_text(encoding="utf-8")
            lines = content.strip().split("\n")
            self.assertEqual(len(lines), 3)
            self.assertEqual(len(logger.entries), 3)

    def test_log_token_summary(self):
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            logger.log_token_summary({"total_tokens": 1000, "total_calls": 3})
            entry = logger.entries[-1]
            self.assertEqual(entry["event"], "token_summary")
            self.assertEqual(entry["data"]["total_tokens"], 1000)


if __name__ == "__main__":
    unittest.main()
