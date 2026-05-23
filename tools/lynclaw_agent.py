#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def _project_venv_python() -> Path:
    return ROOT / ".venv" / "bin" / "python"


def _maybe_reexec_with_venv() -> None:
    venv_python = _project_venv_python()
    if sys.version_info < (3, 10) and sys.prefix != str(ROOT / ".venv") and venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), *sys.argv])


def main() -> int:
    _maybe_reexec_with_venv()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from runtime.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
