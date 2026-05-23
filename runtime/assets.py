from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = ROOT / "assets"
INDUSTRY_DIR = ASSETS_ROOT / "prompts" / "industries"
TEMPLATE_DIR = ASSETS_ROOT / "templates" / "summary"
TRANSCRIPT_DIR = ROOT / "examples" / "transcripts"
OUTPUT_DIR = ROOT / "examples" / "outputs"
RUN_LOG_DIR = ROOT / "examples" / "run-logs"
FLYWHEEL_DIR = ROOT / "examples" / "flywheel"
PLATFORM_PROMPT = ASSETS_ROOT / "prompts" / "meta" / "summary-platform-system-v5.md"
FLYWHEEL_STRATEGY_PROMPT = ASSETS_ROOT / "prompts" / "meta" / "flywheel-prompt-strategy-system-v1.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def available_files(directory: Path) -> list[str]:
    if not directory.exists():
        return []
    return sorted(path.name for path in directory.iterdir() if path.is_file() and not path.name.startswith("."))


def available_transcripts(directory: Path) -> list[str]:
    return [name for name in available_files(directory) if name.endswith(".txt")]


def resolve_file(base_dir: Path, value: str) -> Path:
    requested = Path(value)
    path = requested if requested.is_absolute() else base_dir / requested
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return path


def build_default_output_path(transcript_path: Path, template_path: Path) -> Path:
    return OUTPUT_DIR / f"{transcript_path.stem}__{template_path.stem}.md"


def load_local_config() -> dict:
    config_path = ROOT / "config" / "local.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))
