from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from runtime.tui.state import SessionState, TokenUsage, load_initial_state


class TestTokenUsage(unittest.TestCase):
    def test_initial_values_are_zero(self):
        usage = TokenUsage()
        self.assertEqual(usage.as_dict(), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

    def test_add_accumulates(self):
        usage = TokenUsage()
        usage.add({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150})
        self.assertEqual(usage.prompt_tokens, 100)
        usage.add({"prompt_tokens": 200, "completion_tokens": 80, "total_tokens": 280})
        self.assertEqual(usage.prompt_tokens, 300)
        self.assertEqual(usage.completion_tokens, 130)
        self.assertEqual(usage.total_tokens, 430)

    def test_add_with_missing_keys_uses_zero(self):
        usage = TokenUsage()
        usage.add({})
        self.assertEqual(usage.as_dict(), {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})


class TestSessionState(unittest.TestCase):
    def test_default_values(self):
        state = SessionState()
        self.assertEqual(state.model, "deepseek-chat")
        self.assertEqual(state.safety_mode, "reactive")
        self.assertEqual(state.temperature, 0.2)
        self.assertEqual(state.reasoning_effort, "medium")

    def test_as_dict_includes_token_usage(self):
        state = SessionState()
        d = state.as_dict()
        self.assertIn("token_usage", d)
        self.assertIn("call_count", d)
        self.assertEqual(d["call_count"], 0)

    def test_load_from_agent_config(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "agent.local.json").write_text(
                json.dumps({"model": "test-model", "base_url": "https://test.api"}),
                encoding="utf-8",
            )
            state = load_initial_state(root)
            self.assertEqual(state.model, "test-model")
            self.assertEqual(state.base_url, "https://test.api")

    def test_load_from_local_config(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "local.json").write_text(
                json.dumps({"safety_mode": "strict", "temperature": 0.5}),
                encoding="utf-8",
            )
            state = load_initial_state(root)
            self.assertEqual(state.safety_mode, "strict")
            self.assertEqual(state.temperature, 0.5)

    def test_load_normalizes_reasoning_effort_from_local_config(self):
        with TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            config_dir = root / "config"
            config_dir.mkdir()
            (config_dir / "local.json").write_text(
                json.dumps({"reasoning_effort": "高"}),
                encoding="utf-8",
            )
            state = load_initial_state(root)
            self.assertEqual(state.reasoning_effort, "high")

    def test_load_without_config_files(self):
        with TemporaryDirectory() as tmp_dir:
            state = load_initial_state(Path(tmp_dir))
            self.assertEqual(state.model, "deepseek-chat")
            self.assertEqual(state.safety_mode, "reactive")


if __name__ == "__main__":
    unittest.main()
