#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import argparse

from runtime.assets import ROOT as PROJECT_ROOT, TRANSCRIPT_DIR, read_text, resolve_file
from runtime.classifier.pipeline import classify_transcript
from runtime.classifier.report import write_classification_report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run the standalone scene classifier.")
    parser.add_argument("--transcript", required=True, help="Transcript filename under examples/transcripts/ or absolute path")
    parser.add_argument("--rules-only", action="store_true", help="Run rules-only classification")
    parser.add_argument("--routing-mode", choices=["rules", "llm_primary", "shadow", "grayscale"], default=None,
        help="Classification routing mode")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--save-report", action="store_true", help="Write a classification report")
    parser.add_argument("--classifier-confidence-threshold", type=float, default=0.65)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    transcript_path = resolve_file(TRANSCRIPT_DIR, args.transcript)

    routing_mode = args.routing_mode or "llm_primary"
    reasoning_config = None
    if not args.rules_only and routing_mode != "rules":
        from runtime.agent.config import load_model_pair_config
        model_pair = load_model_pair_config(root=PROJECT_ROOT)
        reasoning_config = model_pair.classifier
        if args.routing_mode is None:
            routing_mode = model_pair.router.routing_mode

    result = classify_transcript(
        read_text(transcript_path),
        rules_only=args.rules_only,
        routing_mode=routing_mode,
        confidence_threshold=args.classifier_confidence_threshold,
        reasoning_config=reasoning_config,
    )
    if args.save_report:
        write_classification_report(
            result,
            PROJECT_ROOT / "examples" / "classification-reports",
            transcript_id=transcript_path.stem,
        )
    if args.json:
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(result.recommended_template)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
