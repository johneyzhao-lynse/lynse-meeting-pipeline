#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.agent.config import load_model_pair_config
from runtime.assets import FLYWHEEL_DIR, ROOT as PROJECT_ROOT, resolve_file
from runtime.client import call_litellm
from runtime.flywheel.analysis import build_reasoning_analysis_messages, write_analysis_record
from runtime.flywheel.models import FeedbackRecord


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Run offline flywheel analysis with the reasoning model.")
    parser.add_argument("--samples-json", required=True, help="JSON file with sample objects")
    parser.add_argument("--feedback-json", required=True, help="JSON file with feedback objects")
    parser.add_argument("--analysis-goal", required=True)
    parser.add_argument("--output-dir", default=str(FLYWHEEL_DIR / "analyses"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-tokens", type=int, default=3000)
    parser.add_argument("--temperature", type=float, default=0.2)
    return parser.parse_args(argv)


def _load_json_list(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array: {path}")
    return data


def main(argv=None):
    args = parse_args(argv)
    try:
        samples_path = resolve_file(PROJECT_ROOT, args.samples_json)
        feedback_path = resolve_file(PROJECT_ROOT, args.feedback_json)
        samples = _load_json_list(samples_path)
        feedbacks = [FeedbackRecord(**item) for item in _load_json_list(feedback_path)]
        model_pair = load_model_pair_config(PROJECT_ROOT)
        reasoning_config = model_pair.reasoning
        messages = build_reasoning_analysis_messages(
            samples=samples,
            feedbacks=feedbacks,
            analysis_goal=args.analysis_goal,
        )
        payload = {
            "model": reasoning_config.model,
            "messages": messages,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
        }
        if args.dry_run:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        api_key = reasoning_config.api_key
        if not api_key:
            print("Missing reasoning API key. Set REASONING_API_KEY or run with --dry-run.", file=sys.stderr)
            return 2
        result = call_litellm(
            api_key=api_key,
            model=reasoning_config.model,
            messages=messages,
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            base_url=reasoning_config.base_url,
        )
        content = result["choices"][0]["message"]["content"]
        path = write_analysis_record(
            Path(args.output_dir),
            sample_ids=[str(item.get("summary_id") or item.get("sample_id") or index) for index, item in enumerate(samples)],
            reasoning_model=reasoning_config.model,
            analysis_goal=args.analysis_goal,
            findings=[content],
            recommended_prompt_changes=[],
        )
        print(str(path))
        return 0
    except (FileNotFoundError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
