#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse

from runtime.assets import read_text
from runtime.user_prompt.validator import validate_user_prompt


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate an editable user prompt.")
    parser.add_argument("--user-prompt-file", required=True)
    args = parser.parse_args(argv)
    result = validate_user_prompt(read_text(Path(args.user_prompt_file)))
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0 if result.is_valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
