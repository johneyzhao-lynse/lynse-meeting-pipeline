#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate classifier against labeled transcript cases.")
    parser.add_argument("--cases-json", help="Optional JSON cases file for future batch evaluation.")
    return parser.parse_args(argv)


def main(argv=None):
    parse_args(argv)
    print("Classifier evaluation is ready for labeled cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
