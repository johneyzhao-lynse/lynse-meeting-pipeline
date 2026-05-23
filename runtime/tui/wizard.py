from __future__ import annotations

from pathlib import Path
from typing import Any

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import ValidationError, Validator

from .display import console, show_classification_result, show_error, show_info, show_success, show_summary, show_token_usage
from .logger import SessionLogger
from .state import SessionState

from runtime.assets import (
    INDUSTRY_DIR,
    OUTPUT_DIR,
    PLATFORM_PROMPT,
    TEMPLATE_DIR,
    TRANSCRIPT_DIR,
    available_files,
    available_transcripts,
    read_text,
    resolve_file,
)
from runtime.classifier.pipeline import classify_transcript
from runtime.classifier.meeting_types import get_meeting_info, get_meeting_type
from runtime.client import call_litellm
from runtime.failure_detector import classify_api_failure, classify_generation_failure
from runtime.messages import build_messages
from runtime.output import format_summary_output
from runtime.safety import detect_safety_risks, sanitize_sensitive_output
from runtime.agent.config import load_agent_config, load_model_pair_config
from runtime.title import extract_date


class NonEmptyValidator(Validator):
    def validate(self, document: Any) -> None:
        if not document.text.strip():
            raise ValidationError(message="不能为空")


def _completer_from_files(directory: Path, extension: str = "") -> WordCompleter:
    names = [
        f.name for f in directory.iterdir()
        if f.is_file() and not f.name.startswith(".") and f.name.endswith(extension)
    ] if directory.exists() else []
    return WordCompleter(sorted(names), sentence=True)


def _pick_transcript(state: SessionState) -> Path | None:
    transcripts = available_transcripts(TRANSCRIPT_DIR)
    if not transcripts:
        show_error("没有找到转写文本文件")
        return None
    completer = WordCompleter(transcripts, sentence=True)
    console.print("\n[bold]可用转写文本:[/bold]")
    for t in transcripts:
        console.print(f"  [cyan]•[/cyan] {t}")
    try:
        choice = pt_prompt(
            "选择转写文本 (文件名): ",
            completer=completer,
            complete_while_typing=True,
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not choice:
        return None
    try:
        return resolve_file(TRANSCRIPT_DIR, choice)
    except FileNotFoundError:
        show_error(f"文件不存在: {choice}")
        return None


def _pick_from_list(label: str, items: list[str], default: str | None = None) -> str | None:
    completer = WordCompleter(items, sentence=True)
    default_hint = f" [默认: {default}]" if default else ""
    try:
        choice = pt_prompt(
            f"选择{label}{default_hint}: ",
            completer=completer,
            complete_while_typing=True,
        ).strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not choice and default:
        return default
    return choice if choice else None


def run_wizard(
    state: SessionState,
    logger: SessionLogger,
    root: Path,
    dry_run: bool = False,
) -> None:
    logger.log_command("/run", args="--dry-run" if dry_run else "")
    config_snapshot = state.as_dict()

    transcript_path = _pick_transcript(state)
    if transcript_path is None:
        return

    transcript_text = read_text(transcript_path)
    show_info(f"转写文本: {transcript_path.name} ({len(transcript_text)} 字符)")

    model_pair = load_model_pair_config(root=root)
    routing_mode = getattr(state, "routing_mode", model_pair.router.routing_mode)
    classification_result = classify_transcript(
        transcript_text,
        confidence_threshold=state.confidence_threshold,
        reasoning_config=model_pair.classifier,
        routing_mode=routing_mode,
    )
    classification_dict = classification_result.as_dict()
    logger.log_classification(transcript_path.name, classification_dict, config_snapshot=config_snapshot)

    show_classification_result(classification_dict)

    recommended_template = classification_result.recommended_template
    recommended_industry = classification_result.recommended_industry_prompt

    templates = available_files(TEMPLATE_DIR)
    industries = available_files(INDUSTRY_DIR) + ["(无)"]

    template_name = _pick_from_list(
        "模板", templates, default=recommended_template,
    )
    if template_name is None:
        return

    industry_name = _pick_from_list(
        "行业提示词", industries, default=recommended_industry or "(无)",
    )
    if industry_name is None:
        return

    industry_path: Path | None = None
    if industry_name and industry_name != "(无)":
        try:
            industry_path = resolve_file(INDUSTRY_DIR, industry_name)
        except FileNotFoundError:
            show_error(f"行业提示词文件不存在: {industry_name}")
            return

    template_path = resolve_file(TEMPLATE_DIR, template_name)
    safety_risks = detect_safety_risks(transcript_text)

    console.print("\n")
    summary_table_data = {
        "转写文本": transcript_path.name,
        "模板": template_name,
        "行业提示词": industry_name or "无",
        "动态提示词": "ON" if state.dynamic_prompt else "OFF",
        "模型": state.model,
        "安全模式": state.safety_mode,
        "安全风险": ", ".join(safety_risks) if safety_risks else "无",
        "温度": str(state.temperature),
        "最大 tokens": str(state.max_tokens),
        "思维模式": state.thinking,
        "推理深度": state.reasoning_effort or "medium",
    }
    for k, v in summary_table_data.items():
        console.print(f"  [cyan]{k}:[/cyan] {v}")
    console.print("")

    meeting_type = get_meeting_type(template_path.name)
    meeting_info = get_meeting_info(template_path.name)
    meeting_category = meeting_info.meeting_category
    meeting_mode = meeting_info.meeting_mode
    if getattr(state, "classify_meeting", False):
        from runtime.classifier.meeting_classifier import classify_meeting
        llm_classification = classify_meeting(
            transcript_text,
            classifier_config=model_pair.classifier,
        )
        if llm_classification is not None:
            meeting_type = llm_classification.meeting_type
            meeting_category = llm_classification.meeting_category
            meeting_mode = llm_classification.meeting_mode
            show_info(f"LLM 会议分类: {meeting_type} / {meeting_category} / {meeting_mode}")
    meeting_date = extract_date(transcript_text)

    dynamic_template_text = None
    if state.dynamic_prompt and classification_result is not None:
        from runtime.classifier.prompt_composer import compose_dynamic_template
        dynamic_template_text = compose_dynamic_template(
            classification_result,
            base_template_path=template_path,
            transcript_char_count=len(transcript_text),
            current_date=__import__("datetime").datetime.now().strftime("%Y-%m-%d"),
        )
        if dynamic_template_text:
            base_len = template_path.read_text(encoding="utf-8").__len__()
            show_info(f"动态提示词已生效: {base_len} → {len(dynamic_template_text)} 字符 (+{len(dynamic_template_text) - base_len})")
            for label in classification_result.scene_labels:
                console.print(f"  [dim]  场景增强: {label}[/dim]")

    messages = build_messages(
        industry_prompt_path=industry_path,
        template_path=template_path,
        transcript_path=transcript_path,
        user_style="请使用专业、简洁、清晰、适合业务沟通的表达。区分已确认事实、分析判断和待确认信息。",
        safety_mode=state.safety_mode,
        platform_prompt_path=PLATFORM_PROMPT,
        dynamic_template_text=dynamic_template_text,
        meeting_type=meeting_type,
        meeting_date=meeting_date,
    )

    if dry_run:
        import json
        payload = {
            "model": state.model,
            "messages_count": len(messages),
            "system_length": len(messages[0]["content"]) if messages else 0,
            "user_length": len(messages[1]["content"]) if len(messages) > 1 else 0,
            "thinking": state.thinking,
            "reasoning_effort": state.reasoning_effort,
            "max_tokens": state.max_tokens,
            "temperature": state.temperature,
        }
        console.print(Panel(json.dumps(payload, ensure_ascii=False, indent=2), title="Dry-run Payload", border_style="yellow"))
        logger.log_generation(
            transcript=transcript_path.name, template=template_name, industry=industry_name,
            safety_mode=state.safety_mode, model=state.model, thinking=state.thinking,
            temperature=state.temperature, max_tokens=state.max_tokens, safety_risks=safety_risks,
            final_status="dry_run",
        )
        return

    agent_config = load_agent_config(root=root)
    api_key = state.api_key or agent_config.api_key
    base_url = state.base_url or agent_config.base_url

    if not api_key:
        show_error("缺少 API key。请配置 config/agent.local.json 或设置环境变量")
        return

    show_info("正在调用模型生成总结...")
    attempt_count = 0
    token_usage: dict[str, int] = {}
    result: dict[str, Any] | None = None
    error_msg: str | None = None
    retry_strict = False
    current_safety_mode = state.safety_mode

    try:
        attempt_count += 1
        result = call_litellm(
            api_key=api_key,
            model=state.model,
            messages=messages,
            thinking=state.thinking,
            reasoning_effort=state.reasoning_effort,
            max_tokens=state.max_tokens,
            temperature=state.temperature,
            base_url=base_url,
        )
    except RuntimeError as exc:
        api_failure = classify_api_failure(str(exc))
        if state.safety_mode in {"reactive", "auto"} and api_failure.retryable:
            retry_strict = True
            error_msg = str(exc)
        else:
            error_msg = str(exc)
            result = None

    if retry_strict:
        show_info("首次请求触发内容过滤，使用 strict 模式重试...")
        current_safety_mode = "strict"
        strict_messages = build_messages(
            industry_prompt_path=industry_path,
            template_path=template_path,
            transcript_path=transcript_path,
            user_style="请使用专业、简洁、清晰、适合业务沟通的表达。区分已确认事实、分析判断和待确认信息。",
            safety_mode="strict",
            platform_prompt_path=PLATFORM_PROMPT,
            meeting_type=meeting_type,
            meeting_date=meeting_date,
        )
        try:
            attempt_count += 1
            result = call_litellm(
                api_key=api_key,
                model=state.model,
                messages=strict_messages,
                thinking=state.thinking,
                reasoning_effort=state.reasoning_effort,
                max_tokens=state.max_tokens,
                temperature=state.temperature,
                base_url=base_url,
            )
        except RuntimeError as exc:
            error_msg = str(exc)
            result = None

    if result is None:
        show_error(f"生成失败: {error_msg}")
        logger.log_generation(
            transcript=transcript_path.name, template=template_name, industry=industry_name,
            safety_mode=current_safety_mode, model=state.model, thinking=state.thinking,
            temperature=state.temperature, max_tokens=state.max_tokens, safety_risks=safety_risks,
            attempt_count=attempt_count, final_status="error", error=error_msg,
        )
        return

    raw_usage = result.get("usage", {})
    token_usage = {
        "prompt_tokens": raw_usage.get("prompt_tokens", 0),
        "completion_tokens": raw_usage.get("completion_tokens", 0),
        "total_tokens": raw_usage.get("total_tokens", 0),
    }

    content = sanitize_sensitive_output(result["choices"][0]["message"]["content"])

    failure = classify_generation_failure(content)
    should_retry = state.safety_mode == "auto" and failure.retryable and bool(safety_risks)
    if should_retry and current_safety_mode != "strict":
        show_info("输出疑似拒绝，使用 strict 模式重试...")
        current_safety_mode = "strict"
        strict_messages = build_messages(
            industry_prompt_path=industry_path,
            template_path=template_path,
            transcript_path=transcript_path,
            user_style="请使用专业、简洁、清晰、适合业务沟通的表达。区分已确认事实、分析判断和待确认信息。",
            safety_mode="strict",
            platform_prompt_path=PLATFORM_PROMPT,
            meeting_type=meeting_type,
            meeting_date=meeting_date,
        )
        try:
            attempt_count += 1
            result = call_litellm(
                api_key=api_key,
                model=state.model,
                messages=strict_messages,
                thinking=state.thinking,
                reasoning_effort=state.reasoning_effort,
                max_tokens=state.max_tokens,
                temperature=state.temperature,
                base_url=base_url,
            )
            retry_usage = result.get("usage", {})
            token_usage = {
                "prompt_tokens": token_usage["prompt_tokens"] + retry_usage.get("prompt_tokens", 0),
                "completion_tokens": token_usage["completion_tokens"] + retry_usage.get("completion_tokens", 0),
                "total_tokens": token_usage["total_tokens"] + retry_usage.get("total_tokens", 0),
            }
            content = sanitize_sensitive_output(result["choices"][0]["message"]["content"])
        except RuntimeError as exc:
            error_msg = str(exc)
            show_error(f"重试失败: {error_msg}")

    state.token_usage.add(token_usage)
    state.call_count += attempt_count

    show_token_usage(token_usage, state.token_usage.as_dict(), state.call_count)

    output_path = OUTPUT_DIR / f"{transcript_path.stem}__{template_path.stem}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    params_line = (
        f"| 模型: {state.model}"
        f" | 思维模式: {state.thinking}"
        f" | 推理深度: {state.reasoning_effort or 'medium'}"
        f" | max_tokens: {state.max_tokens}"
        f" | temperature: {state.temperature} |"
    )
    output_path.write_text(format_summary_output(content, params_line), encoding="utf-8")

    show_summary(content, str(output_path))
    show_success(f"已保存到 {output_path}")

    logger.log_generation(
        transcript=transcript_path.name, template=template_name, industry=industry_name,
        safety_mode=current_safety_mode, model=state.model, thinking=state.thinking,
        temperature=state.temperature, max_tokens=state.max_tokens, safety_risks=safety_risks,
        token_usage=token_usage, attempt_count=attempt_count, final_status="success",
        output_path=str(output_path),
    )


from rich.panel import Panel  # noqa: E402
