# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

A Python CLI pipeline that generates structured meeting summaries from audio transcripts. It classifies transcripts by scene/industry, builds LLM prompts from modular assets, calls an OpenAI-compatible API (DeepSeek by default), and handles sensitive-content safety with automatic retry. The UI language and all prompts are in Chinese.

## Running Commands

```bash
# Run the full summary pipeline (manual mode)
python tools/lynclaw_agent.py --industry <file> --template <file> --transcript <file> [--dry-run]

# Auto-route mode (classifier picks template)
python tools/lynclaw_agent.py --auto-route --transcript <file> [--dry-run]

# List available industries, templates, transcripts
python tools/lynclaw_agent.py --list

# Run standalone classifier
python tools/run_classifier.py --transcript <file> --json

# Validate a user prompt file
python tools/validate_user_prompt.py --user-prompt-file <path>

# Run flywheel analysis
python tools/run_flywheel_analysis.py --samples-json <path> --feedback-json <path> --analysis-goal <text> [--dry-run]

# Interactive TUI (Rich + Prompt Toolkit, guided wizard for full pipeline)
python tools/lynse.py

# Run all tests (unittest, no pytest)
python -m pytest tests/ -v
# Or with unittest directly:
python -m unittest discover -s tests -v

# Run a single test file
python -m unittest tests/test_reactive_safety.py -v
```

The entry point is `tools/lynclaw_agent.py`, which auto-re-execs into `.venv` on Python < 3.10, then delegates to `runtime.cli.main()`.

## Architecture

### Pipeline Flow

1. **CLI** (`runtime/cli.py`) parses args, resolves file paths, and orchestrates the run.
2. **Classifier** (`runtime/classifier/`) — rules-based keyword matching ranks templates and industries against transcript features. Returns a recommended template with confidence score; falls back to `general-meeting.md` below threshold (default 0.65).
3. **Messages** (`runtime/messages.py`) — assembles the system + user prompt from modular parts: platform prompt, industry enhancement, safety constraints, user template/style, and transcript text. All parts are joined with `\n\n---\n\n` delimiters.
4. **Client** (`runtime/client.py`) — thin HTTP wrapper around OpenAI-compatible `/chat/completions` using `urllib` (no external deps).
5. **Safety** (`runtime/safety.py`) — local regex pre-scan for sensitive categories (political, self-harm, profanity, privacy). Four modes: `auto` (apply on detection), `reactive` (only retry after refusal), `strict` (always apply), `off`.
6. **Failure Detector** (`runtime/failure_detector.py`) — classifies API errors and model outputs as retryable vs terminal, driving the retry loop.

### Key Modules

- **`runtime/classifier/`** — `pipeline.py` (entry point), `rules.py` (keyword scoring with per-template boosts), `models.py` (frozen dataclasses), `assets.py` (manifest loading with `lru_cache`), `report.py` (JSON report writer).
- **`runtime/agent/config.py`** — loads API key, model, and base URL from `config/agent.local.json` with env-var fallbacks (`LYNCLAW_AGENT_*`, `SUMMARY_*`).
- **`runtime/flywheel/`** — offline quality loop: `FeedbackRecord` → reasoning model analysis → `AnalysisRecord` with prompt improvement suggestions.
- **`runtime/user_prompt/`** — parses editable user prompt markdown (`# 总结目标`, `# 目标读者`, `# 输出结构`, `# 特殊要求` sections), validates against blocked patterns, and compiles into a prompt string.
- **`runtime/tui/`** — interactive TUI (Rich + Prompt Toolkit). `state.py` (session config + token tracking), `logger.py` (structured JSONL logs to `examples/tui-logs/`), `display.py` (Rich tables/panels/markdown), `commands.py` (slash command dispatch), `wizard.py` (`/run` guided wizard flow). Entry point: `tools/lynse.py`.

### Asset System

All prompt content is file-based under `assets/`:
- `prompts/meta/` — platform system prompt (`summary-platform-system-v5.md`) and flywheel strategy prompt
- `prompts/industries/` — per-industry enhancement prompts (insurance, legal, marketing, etc.)
- `prompts/safety/` — safety-focused prompt additions
- `templates/summary/` — 35+ structured summary templates (Markdown)
- `manifests/` — `template_manifest.json` and `industry_manifest.json` define templates/industries with keywords, scene labels, and routing metadata

Config lives in `config/` (gitignored): `agent.local.json` for API credentials, `local.json` for default settings.

### Data Flow

`examples/transcripts/` → classifier → template selection → prompt assembly → LLM call → `examples/outputs/` + `examples/run-logs/`

## Testing

Tests use `unittest` (no pytest dependency required). Test files live in `tests/` mirroring the `runtime/` structure. Tests mock `call_litellm` and `load_agent_config` to avoid requiring API keys. Key test classes:

- `test_cli_integration.py` — end-to-end CLI tests with dry-run and mocked API
- `test_reactive_safety.py` — safety detection, retry classification, and mode logic
- `test_flywheel_runtime.py` — flywheel record creation and analysis
- `tests/classifier/` — classifier pipeline, rules, manifest loading
- `tests/tui/` — TUI state, logger, command dispatch

## Conventions

- All runtime code uses `from __future__ import annotations` for modern type syntax
- Data models are frozen `@dataclass` classes with `as_dict()` methods
- Core pipeline has no external Python dependencies — uses only stdlib (`urllib`, `json`, `re`, `pathlib`, `argparse`)
- TUI layer adds `rich` and `prompt_toolkit` (install via `.venv/bin/pip install rich prompt_toolkit`)
- Asset manifests use `@lru_cache` for single-load behavior
- The project has no `pyproject.toml` or `setup.py` — it runs directly from the repo root with `sys.path` manipulation
