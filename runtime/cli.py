from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import sys
from pathlib import Path

from .failure_detector import classify_api_failure, classify_generation_failure
from .agent.config import load_agent_config, load_model_pair_config
from .assets import (
    INDUSTRY_DIR,
    OUTPUT_DIR,
    PLATFORM_PROMPT,
    RUN_LOG_DIR,
    ROOT,
    TEMPLATE_DIR,
    TRANSCRIPT_DIR,
    available_files,
    available_transcripts,
    build_default_output_path,
    load_local_config,
    read_text,
    resolve_file,
)
from .classifier.pipeline import classify_transcript
from .classifier.report import write_classification_report
from .classifier.assets import load_template_manifest
from .classifier.meeting_types import get_meeting_info, get_meeting_type
from .client import call_litellm
from .messages import build_messages, redact_payload_for_preview
from .output import format_summary_output
from .reasoning import normalize_reasoning_effort
from .title import extract_date
from .safety import detect_safety_risks, sanitize_sensitive_output
from .user_prompt.parser import parse_user_prompt_markdown
from .user_prompt.compiler import compile_user_prompt
from .user_prompt.profile import compile_profile_prompt, load_user_prompt_profile
from .user_prompt.validator import validate_user_prompt


DEFAULT_STYLE = "请使用专业、简洁、清晰、适合业务沟通的表达。区分已确认事实、分析判断和待确认信息。"
DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_USER_PROMPT_PROFILE_FILE = ROOT / "config" / "user_prompts.local.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    local_config = load_local_config()
    agent_config = load_agent_config(root=ROOT)
    parser = argparse.ArgumentParser(
        description="Run a full DeepSeek official API test with local real prompts and transcript."
    )
    parser.add_argument("--industry", help="Industry enhancement prompt filename under assets/prompts/industries/")
    parser.add_argument("--template", help="User template filename under assets/templates/summary/")
    parser.add_argument("--transcript", help="Transcript filename under examples/transcripts/ or absolute path")
    parser.add_argument("--style", default=DEFAULT_STYLE, help="User style text injected into the user message")
    parser.add_argument(
        "--model",
        default=agent_config.model,
        help="Summary model ID. Defaults to SUMMARY_MODEL, config/agent.local.json, or LYNCLAW_AGENT_MODEL.",
    )
    parser.add_argument("--prompt-version", default=DEFAULT_PROMPT_VERSION, help="Prompt asset version for flywheel records")
    parser.add_argument(
        "--thinking",
        default=agent_config.call_params.thinking,
        choices=["enabled", "disabled"],
        help="DeepSeek thinking mode",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=agent_config.call_params.reasoning_effort,
        choices=["low", "medium", "high", "低", "中", "高"],
        help="Reasoning effort level: low/medium/high, or 低/中/高",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=agent_config.call_params.max_tokens,
        help="Maximum output tokens",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=agent_config.call_params.temperature,
        help="Sampling temperature",
    )
    parser.add_argument(
        "--base-url",
        default=agent_config.base_url,
        help="OpenAI-compatible base URL. Defaults to config/agent.local.json or LYNCLAW_AGENT_BASE_URL.",
    )
    parser.add_argument(
        "--output",
        help="Optional output markdown path. Defaults to examples/outputs/<transcript stem>__<template stem>.md",
    )
    parser.add_argument(
        "--run-log-output",
        help="Optional process log JSON path. Defaults to examples/run-logs/<transcript>__<timestamp>.json",
    )
    parser.add_argument(
        "--safety-mode",
        default=local_config.get("safety_mode") or os.getenv("SUMMARY_SAFETY_MODE", "reactive"),
        choices=["auto", "strict", "off", "reactive"],
        help="Sensitive-content mode. reactive retries with strict safety only after refusal-like output.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the request payload only")
    parser.add_argument(
        "--dry-run-full",
        action="store_true",
        help="With --dry-run, print the full transcript instead of the redacted preview.",
    )
    parser.add_argument("--list", action="store_true", help="List local industries/templates/transcripts")
    parser.add_argument("--auto-route", action="store_true", help="Automatically classify transcript and route template; industry remains user-selected")
    parser.add_argument("--classifier-model", help="Reserved classifier model override")
    parser.add_argument("--classifier-confidence-threshold", type=float, default=0.65, help="Classifier confidence threshold")
    parser.add_argument("--save-classification-report", action="store_true", help="Write classification report to examples/classification-reports/")
    parser.add_argument("--classifier-debug", action="store_true", help="Include classification data in outputs")
    parser.add_argument("--rules-only", action="store_true", help="Use rules-only classification, skip LLM refinement")
    parser.add_argument("--routing-mode", choices=["rules", "llm_primary", "shadow", "grayscale"], default=None,
        help="Classification routing mode (default: from config, or 'rules')")
    parser.add_argument("--grayscale-percentage", type=int, default=None,
        help="Percentage of requests routed to LLM in grayscale mode (1-100)")
    parser.add_argument("--shadow-log", default=None,
        help="Path to write shadow comparison JSONL log")
    parser.add_argument("--routing-metrics", action="store_true", help="Emit routing metrics to stderr after run")
    parser.add_argument("--dynamic-prompt", action="store_true",
        help="Compose dynamic template from classification result (requires --auto-route)")
    parser.add_argument("--classify-meeting", action="store_true",
        help="Use LLM to classify meeting type/category/mode (opt-in, requires API call)")
    parser.add_argument("--user-prompt-file", help="Editable user prompt markdown file")
    parser.add_argument("--user-prompt-profile", help="Profile name from config/user_prompts.local.json")
    parser.add_argument(
        "--user-prompt-profile-file",
        default=str(DEFAULT_USER_PROMPT_PROFILE_FILE),
        help="Local user prompt profile JSON file. Defaults to config/user_prompts.local.json.",
    )
    parser.add_argument(
        "--audience",
        choices=["self", "manager", "customer", "team"],
        help="Per-run target audience used with --user-prompt-profile.",
    )
    parser.add_argument(
        "--summary-depth",
        choices=["concise", "full"],
        help="Per-run summary depth used with --user-prompt-profile.",
    )
    parser.add_argument("--show-user-prompt", action="store_true", help="Show the resolved user prompt markdown and exit")
    parser.add_argument("--export-user-prompt", help="Write the resolved user prompt markdown to a file and exit")
    parser.add_argument("--validate-user-prompt", action="store_true", help="Validate the provided user prompt file and exit")
    return parser.parse_args(argv)


def print_available() -> None:
    print("行业增强提示词:")
    for name in available_files(INDUSTRY_DIR):
        print(f"  - {name}")
    print("\n用户总结模板:")
    for name in available_files(TEMPLATE_DIR):
        print(f"  - {name}")
    print("\n转写文本:")
    for name in available_transcripts(TRANSCRIPT_DIR):
        print(f"  - {name}")


def emit_log(message: str) -> None:
    print(f"[run] {message}", file=sys.stderr)


def resolve_output_path(value: str | None, transcript_path: Path, template_path: Path) -> Path:
    if value:
        requested_output = Path(value)
        return requested_output if requested_output.is_absolute() else ROOT / requested_output
    return build_default_output_path(transcript_path, template_path)


def resolve_run_log_path(value: str | None, transcript_path: Path) -> Path:
    if value:
        requested_output = Path(value)
        return requested_output if requested_output.is_absolute() else ROOT / requested_output
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return RUN_LOG_DIR / f"{transcript_path.stem}__{timestamp}.json"


def write_run_log(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def infer_scene_type(template_name: str) -> str:
    for item in load_template_manifest().templates:
        if item.name == template_name:
            return item.display_name.removesuffix("总结")
    return Path(template_name).stem.removesuffix("总结")


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        args.reasoning_effort = normalize_reasoning_effort(args.reasoning_effort)

        if args.list:
            print_available()
            return 0

        if args.auto_route:
            missing = [name for name in ["transcript"] if getattr(args, name) is None]
        else:
            missing = [name for name in ["industry", "template", "transcript"] if getattr(args, name) is None]
        if missing:
            print(f"Missing required arguments: {', '.join('--' + item for item in missing)}", file=sys.stderr)
            print("Tip: use --list to see available local files.", file=sys.stderr)
            return 2

        transcript_path = resolve_file(TRANSCRIPT_DIR, args.transcript)
        classification_result = None
        if args.auto_route:
            rules_only = getattr(args, "rules_only", False)
            reasoning_config = None
            routing_mode = args.routing_mode
            grayscale_percentage = args.grayscale_percentage
            if not rules_only:
                model_pair = load_model_pair_config(root=ROOT)
                reasoning_config = model_pair.classifier
                if routing_mode is None:
                    routing_mode = model_pair.router.routing_mode
                if grayscale_percentage is None:
                    grayscale_percentage = model_pair.router.grayscale_percentage
            if routing_mode is None:
                routing_mode = "llm_primary"
            if grayscale_percentage is None:
                grayscale_percentage = 100
            if args.dry_run and routing_mode != "rules":
                emit_log(f"dry-run: 分类阶段可能调用推理模型 API (routing_mode={routing_mode})")
            elif args.dry_run and reasoning_config:
                emit_log("dry-run: 分类阶段可能调用推理模型 API")
            classification_result = classify_transcript(
                read_text(transcript_path),
                rules_only=rules_only,
                routing_mode=routing_mode,
                confidence_threshold=args.classifier_confidence_threshold,
                reasoning_config=reasoning_config,
                grayscale_percentage=grayscale_percentage,
            )
            template_path = resolve_file(TEMPLATE_DIR, classification_result.recommended_template)
            industry_prompt_path = (
                resolve_file(INDUSTRY_DIR, classification_result.recommended_industry_prompt)
                if classification_result.recommended_industry_prompt
                else None
            )
            if args.save_classification_report:
                write_classification_report(
                    classification_result,
                    ROOT / "examples" / "classification-reports",
                    transcript_id=transcript_path.stem,
                )
        else:
            industry_prompt_path = resolve_file(INDUSTRY_DIR, args.industry)
            template_path = resolve_file(TEMPLATE_DIR, args.template)

        output_path = resolve_output_path(args.output, transcript_path, template_path)
        run_log_path = resolve_run_log_path(args.run_log_output, transcript_path)

        user_prompt_text = None
        profile_prompt_text = None
        if args.user_prompt_file:
            user_prompt_raw = read_text(resolve_file(ROOT, args.user_prompt_file))
            validation = validate_user_prompt(user_prompt_raw)
            if args.validate_user_prompt:
                print(json.dumps(validation.as_dict(), ensure_ascii=False, indent=2))
                return 0 if validation.is_valid else 2
            if not validation.is_valid:
                print(
                    f"User prompt validation failed: {', '.join(validation.violations)}",
                    file=sys.stderr,
                )
                return 2
            parsed_prompt = parse_user_prompt_markdown(validation.normalized_text)
            user_prompt_text = compile_user_prompt(parsed_prompt)
            if args.show_user_prompt:
                print(user_prompt_text)
                return 0
            if args.export_user_prompt:
                export_path = resolve_file(ROOT, args.export_user_prompt)
                export_path.parent.mkdir(parents=True, exist_ok=True)
                export_path.write_text(user_prompt_text, encoding="utf-8")
                print(str(export_path))
                return 0
        elif args.user_prompt_profile:
            profile_path = resolve_file(ROOT, args.user_prompt_profile_file)
            profile = load_user_prompt_profile(profile_path, args.user_prompt_profile)
            profile_prompt_text = compile_profile_prompt(
                profile,
                audience=args.audience,
                summary_depth=args.summary_depth,
            )
            if args.show_user_prompt:
                print(profile_prompt_text)
                return 0
            if args.export_user_prompt:
                export_path = Path(args.export_user_prompt)
                export_path = export_path if export_path.is_absolute() else ROOT / export_path
                export_path.parent.mkdir(parents=True, exist_ok=True)
                export_path.write_text(profile_prompt_text, encoding="utf-8")
                print(str(export_path))
                return 0

        meeting_type = get_meeting_type(template_path.name)
        meeting_info = get_meeting_info(template_path.name)
        meeting_category = meeting_info.meeting_category
        meeting_mode = meeting_info.meeting_mode
        if args.classify_meeting:
            from runtime.classifier.meeting_classifier import classify_meeting
            model_pair = load_model_pair_config(root=ROOT)
            llm_classification = classify_meeting(
                read_text(transcript_path),
                classifier_config=model_pair.classifier,
            )
            if llm_classification is not None:
                meeting_type = llm_classification.meeting_type
                meeting_category = llm_classification.meeting_category
                meeting_mode = llm_classification.meeting_mode
        meeting_date = extract_date(read_text(transcript_path))
        dynamic_template_text = None
        if (args.auto_route and args.dynamic_prompt
                and classification_result is not None
                and user_prompt_text is None):
            from runtime.classifier.prompt_composer import compose_dynamic_template
            dynamic_template_text = compose_dynamic_template(
                classification_result,
                base_template_path=template_path,
                transcript_char_count=len(read_text(transcript_path)),
                current_date=datetime.now().strftime("%Y-%m-%d"),
            )
        messages = build_messages(
            industry_prompt_path=industry_prompt_path,
            template_path=template_path,
            transcript_path=transcript_path,
            user_style=args.style,
            safety_mode=args.safety_mode,
            platform_prompt_path=PLATFORM_PROMPT,
            user_prompt_text=user_prompt_text,
            dynamic_template_text=dynamic_template_text,
            profile_prompt_text=profile_prompt_text,
            meeting_type=meeting_type,
            meeting_date=meeting_date,
        )
        safety_risks = detect_safety_risks(read_text(transcript_path))
        created_at = datetime.now().isoformat(timespec="seconds")
        run_log = {
            "created_at": created_at,
            "started_at": created_at,
            "transcript_id": transcript_path.stem,
            "scene_type": infer_scene_type(template_path.name),
            "recommended_industry": classification_result.recommended_industry_prompt if classification_result else None,
            "industry": industry_prompt_path.name if industry_prompt_path else None,
            "template_name": template_path.name,
            "meeting_type": meeting_type,
            "meeting_category": meeting_category,
            "meeting_mode": meeting_mode,
            "prompt_version": args.prompt_version,
            "summary_model": args.model,
            "transcript_path": str(transcript_path),
            "template": template_path.name,
            "industry_prompt": industry_prompt_path.name if industry_prompt_path else None,
            "model": args.model,
            "thinking": args.thinking,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "safety_mode": args.safety_mode,
            "safety_risks": safety_risks,
            "classification": classification_result.as_dict() if classification_result else None,
            "attempts": [],
            "output_path": str(output_path),
            "run_log_path": str(run_log_path),
            "final_status": "started",
        }

        payload_preview = {
            "model": args.model,
            "messages": messages,
            "thinking": {"type": args.thinking},
            "reasoning_effort": args.reasoning_effort,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
        }
        if classification_result is not None:
            payload_preview["classification"] = classification_result.as_dict()

        if args.dry_run:
            preview = payload_preview if args.dry_run_full else redact_payload_for_preview(
                payload_preview,
                transcript_path,
                safety_risks,
            )
            print(json.dumps(preview, ensure_ascii=False, indent=2))
            return 0

        api_key = load_agent_config(root=ROOT).api_key
        if not api_key:
            print(
                "Missing API key. Configure config/agent.local.json or set LYNCLAW_AGENT_API_KEY_ENV, or run with --dry-run.",
                file=sys.stderr,
            )
            return 2

        emit_log(f"transcript: {transcript_path.name}")
        emit_log(f"template: {template_path.name}")
        if classification_result and classification_result.recommended_industry_prompt:
            emit_log(f"recommended industry: {classification_result.recommended_industry_prompt}")
        emit_log(f"industry: {industry_prompt_path.name if industry_prompt_path else 'none'}")
        emit_log(f"model: {args.model}, thinking: {args.thinking}")
        emit_log("calling model: attempt 1")

        retry_strict = False
        try:
            result = call_litellm(
                api_key=api_key,
                model=args.model,
                messages=messages,
                thinking=args.thinking,
                reasoning_effort=args.reasoning_effort,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                base_url=args.base_url,
            )
            run_log["attempts"].append({"mode": args.safety_mode, "status": "success"})
        except RuntimeError as exc:
            api_failure = classify_api_failure(str(exc))
            run_log["attempts"].append({
                "mode": args.safety_mode,
                "status": "api_error",
                "reason": api_failure.reason,
                "markers": api_failure.markers,
            })
            if args.safety_mode in {"reactive", "auto"} and api_failure.retryable:
                retry_strict = True
                result = None
            else:
                raise

        if retry_strict:
            emit_log("initial request hit sensitive-content filter; retrying with strict safety")
            strict_messages = build_messages(
                industry_prompt_path=industry_prompt_path,
                template_path=template_path,
                transcript_path=transcript_path,
                user_style=args.style,
                safety_mode="strict",
                platform_prompt_path=PLATFORM_PROMPT,
                user_prompt_text=user_prompt_text,
                profile_prompt_text=profile_prompt_text,
                meeting_type=meeting_type,
                meeting_date=meeting_date,
            )
            result = call_litellm(
                api_key=api_key,
                model=args.model,
                messages=strict_messages,
                thinking=args.thinking,
                reasoning_effort=args.reasoning_effort,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                base_url=args.base_url,
            )
            run_log["attempts"].append({"mode": "strict", "status": "success", "trigger": "sensitive_api_failure"})

        content = sanitize_sensitive_output(result["choices"][0]["message"]["content"])
        failure = classify_generation_failure(content)
        run_log["first_output_check"] = {
            "retryable": failure.retryable,
            "reason": failure.reason,
            "markers": failure.markers,
        }
        should_retry = args.safety_mode == "auto" and (failure.retryable or bool(safety_risks))
        if should_retry and args.safety_mode != "off" and args.safety_mode != "strict":
            emit_log("initial response looks refusal-like or incomplete; retrying with strict safety")
            strict_messages = build_messages(
                industry_prompt_path=industry_prompt_path,
                template_path=template_path,
                transcript_path=transcript_path,
                user_style=args.style,
                safety_mode="strict",
                platform_prompt_path=PLATFORM_PROMPT,
                user_prompt_text=user_prompt_text,
                profile_prompt_text=profile_prompt_text,
                meeting_type=meeting_type,
                meeting_date=meeting_date,
            )
            result = call_litellm(
                api_key=api_key,
                model=args.model,
                messages=strict_messages,
                thinking=args.thinking,
                reasoning_effort=args.reasoning_effort,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                base_url=args.base_url,
            )
            content = sanitize_sensitive_output(result["choices"][0]["message"]["content"])
            run_log["attempts"].append({"mode": "strict", "status": "success", "trigger": failure.reason})

        output_path.parent.mkdir(parents=True, exist_ok=True)
        params_line = (
            f"| 模型: {args.model}"
            f" | 思维模式: {args.thinking}"
            f" | 推理深度: {args.reasoning_effort}"
            f" | max_tokens: {args.max_tokens}"
            f" | temperature: {args.temperature} |"
        )
        output_path.write_text(format_summary_output(content, params_line), encoding="utf-8")
        run_log["final_status"] = "success"
        run_log["ended_at"] = datetime.now().isoformat(timespec="seconds")
        run_log["output_chars"] = len(content)
        write_run_log(run_log_path, run_log)
        emit_log(f"Saved summary: {output_path}")
        emit_log(f"Saved run log: {run_log_path}")
        return 0
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
