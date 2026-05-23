#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory

from runtime.assets import ROOT as PROJECT_ROOT
from runtime.tui.commands import COMMANDS, ALIASES, dispatch
from runtime.tui.display import console, show_banner, show_error, show_info, show_token_usage
from runtime.tui.logger import SessionLogger
from runtime.tui.state import SessionState, load_initial_state


HISTORY_PATH = Path.home() / ".lynse_history"


def build_command_completer() -> WordCompleter:
    all_commands = sorted(set(list(COMMANDS.keys()) + list(ALIASES.keys())))
    return WordCompleter(all_commands, sentence=True)


def run_repl() -> None:
    state = load_initial_state(PROJECT_ROOT)
    logger = SessionLogger(
        log_dir=PROJECT_ROOT / "examples" / "tui-logs",
    )

    show_banner()
    show_info(f"日志文件: {logger.log_path}")
    console.print("")

    session: PromptSession[str] = PromptSession(
        history=FileHistory(str(HISTORY_PATH)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=build_command_completer(),
        complete_while_typing=True,
    )

    while True:
        try:
            line = session.prompt(
                "[lynse] > ",
            ).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]再见[/dim]")
            break

        if not line:
            continue

        if line.lower() in ("/quit", "/q", "/exit"):
            if state.call_count > 0:
                show_token_usage(
                    {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                    state.token_usage.as_dict(),
                    state.call_count,
                )
                logger.log_token_summary({
                    **state.token_usage.as_dict(),
                    "total_calls": state.call_count,
                })
            console.print("[dim]再见[/dim]")
            break

        dispatch(line, state, logger, PROJECT_ROOT)
        console.print("")


def main() -> int:
    try:
        run_repl()
    except ImportError as exc:
        print(f"缺少依赖: {exc}", file=sys.stderr)
        print("请安装: pip install rich prompt_toolkit", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
