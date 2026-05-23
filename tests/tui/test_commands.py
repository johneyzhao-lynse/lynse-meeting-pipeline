from __future__ import annotations

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from runtime.tui.commands import dispatch, COMMANDS, ALIASES
from runtime.tui.logger import SessionLogger
from runtime.tui.state import SessionState


class TestCommandRegistry(unittest.TestCase):
    def test_all_commands_have_handlers(self):
        for cmd in ["/run", "/classify", "/config", "/list", "/help"]:
            self.assertIn(cmd, COMMANDS)

    def test_aliases_resolve(self):
        self.assertEqual(ALIASES["/r"], "/run")
        self.assertEqual(ALIASES["/c"], "/classify")
        self.assertEqual(ALIASES["/cfg"], "/config")
        self.assertEqual(ALIASES["/ls"], "/list")
        self.assertEqual(ALIASES["/h"], "/help")
        self.assertEqual(ALIASES["/?"], "/help")

    def test_dispatch_unknown_command_shows_error(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/unknown", state, logger, root)
            self.assertTrue(any(e["event"] == "command_error" for e in logger.entries))


class TestConfigCommand(unittest.TestCase):
    def test_config_updates_state(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/config safety_mode strict", state, logger, root)
            self.assertEqual(state.safety_mode, "strict")
            config_changes = [e for e in logger.entries if e["event"] == "config_change"]
            self.assertEqual(len(config_changes), 1)
            self.assertEqual(config_changes[0]["data"]["key"], "safety_mode")
            self.assertEqual(config_changes[0]["data"]["new"], "strict")

    def test_config_updates_float(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/config temperature 0.5", state, logger, root)
            self.assertEqual(state.temperature, 0.5)

    def test_config_updates_int(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/config max_tokens 5000", state, logger, root)
            self.assertEqual(state.max_tokens, 5000)

    def test_config_normalizes_reasoning_effort_shortcut(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/config reasoning_effort 高", state, logger, root)
            self.assertEqual(state.reasoning_effort, "high")

    def test_config_rejects_unknown_reasoning_effort(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/config reasoning_effort deeper", state, logger, root)
            self.assertEqual(state.reasoning_effort, "medium")

    def test_config_rejects_unknown_key(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            original_model = state.model
            with patch("runtime.tui.display.console"):
                dispatch("/config nonexistent_key value", state, logger, root)
            self.assertEqual(state.model, original_model)


class TestModelCommand(unittest.TestCase):
    def test_builtin_qwen_profile_uses_max_model_name(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/model qwen", state, logger, root)
            self.assertEqual(state.model, "qwen-3.7-max")
            self.assertEqual(state.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")

    def test_builtin_qwen_plus_profile_uses_plus_model_name(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/model qwen-plus", state, logger, root)
            self.assertEqual(state.model, "qwen-3.6-plus")
            self.assertEqual(state.base_url, "https://dashscope.aliyuncs.com/compatible-mode/v1")


class TestListCommand(unittest.TestCase):
    def test_list_runs_without_error(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(__file__).resolve().parents[2]
            with patch("runtime.tui.display.console"):
                dispatch("/list", state, logger, root)
                dispatch("/list transcripts", state, logger, root)
                dispatch("/list templates", state, logger, root)
                dispatch("/list industries", state, logger, root)

    def test_list_unknown_type_shows_error(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(__file__).resolve().parents[2]
            with patch("runtime.tui.display.console"):
                dispatch("/list foobar", state, logger, root)


class TestHelpCommand(unittest.TestCase):
    def test_help_runs_without_error(self):
        state = SessionState()
        with TemporaryDirectory() as tmp_dir:
            logger = SessionLogger(log_dir=Path(tmp_dir))
            root = Path(tmp_dir)
            with patch("runtime.tui.display.console"):
                dispatch("/help", state, logger, root)


if __name__ == "__main__":
    unittest.main()
