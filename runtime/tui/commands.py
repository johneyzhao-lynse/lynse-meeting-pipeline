from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from prompt_toolkit import prompt as pt_prompt

from .display import (
    console,
    show_classification_result,
    show_config_table,
    show_error,
    show_help,
    show_info,
    show_list_section,
    show_success,
)
from .logger import SessionLogger
from .state import SessionState
from .wizard import run_wizard

from runtime.assets import (
    INDUSTRY_DIR,
    TEMPLATE_DIR,
    TRANSCRIPT_DIR,
    available_files,
    available_transcripts,
    read_text,
    resolve_file,
)
from runtime.classifier.pipeline import classify_transcript
import json as json_module

from runtime.agent.config import load_model_pair_config
from runtime.reasoning import normalize_reasoning_effort


def _load_model_profiles(root: Path) -> dict[str, dict]:
    config_path = root / "config" / "agent.local.json"
    if not config_path.exists():
        return {}
    data = json_module.loads(config_path.read_text(encoding="utf-8"))
    return dict(data.get("models", {}))


CommandFn = Callable[[str, SessionState, SessionLogger, Path], None]


def cmd_model(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    profiles = _load_model_profiles(root)
    name = args.strip()

    if not name:
        if not profiles:
            show_info("未配置模型预设。在 config/agent.local.json 的 'models' 字段中添加。")
            show_info(f"当前模型: {state.model}")
            return
        console.print("\n[bold]可用模型预设:[/bold]")
        for key, profile in profiles.items():
            marker = " [dim](当前)[/dim]" if profile["model"] == state.model else ""
            console.print(f"  [cyan]•[/cyan] {key}  →  {profile['model']}{marker}")
        show_info("用法: /model <预设名>  (例如: /model qwen)")
        return

    if name not in profiles:
        show_error(f"未知模型预设: {name}，可用: {', '.join(profiles.keys())}")
        return

    profile = profiles[name]
    old_model = state.model
    state.model = profile["model"]
    state.base_url = profile.get("base_url", state.base_url)
    if profile.get("api_key"):
        state.api_key = profile["api_key"]
    logger.log_config_change("model", old_model, state.model)
    show_success(f"模型切换: {old_model} → {state.model}  [{name}]")


def cmd_run(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    dry_run = "--dry-run" in args
    run_wizard(state, logger, root, dry_run=dry_run)


def cmd_classify(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    logger.log_command("/classify", args=args)

    transcript_name = args.strip()
    if not transcript_name:
        transcripts = available_transcripts(TRANSCRIPT_DIR)
        if not transcripts:
            show_error("没有找到转写文本文件")
            return
        from prompt_toolkit.completion import WordCompleter
        completer = WordCompleter(transcripts, sentence=True)
        console.print("[bold]可用转写文本:[/bold]")
        for t in transcripts:
            console.print(f"  [cyan]•[/cyan] {t}")
        try:
            transcript_name = pt_prompt(
                "选择转写文本: ",
                completer=completer,
                complete_while_typing=True,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            return

    if not transcript_name:
        show_error("请指定转写文本文件名")
        return

    try:
        path = resolve_file(TRANSCRIPT_DIR, transcript_name)
    except FileNotFoundError:
        show_error(f"文件不存在: {transcript_name}")
        return

    show_info(f"正在分类: {path.name}")
    model_pair = load_model_pair_config(root=root)
    routing_mode = getattr(state, "routing_mode", model_pair.router.routing_mode)
    result = classify_transcript(
        read_text(path),
        confidence_threshold=state.confidence_threshold,
        reasoning_config=model_pair.classifier,
        routing_mode=routing_mode,
    )
    result_dict = result.as_dict()
    logger.log_classification(path.name, result_dict, config_snapshot=state.as_dict())
    show_classification_result(result_dict)
    show_success("分类完成")


def cmd_think(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    old = state.thinking
    if old == "enabled":
        state.thinking = "disabled"
    else:
        state.thinking = "enabled"
    logger.log_config_change("thinking", old, state.thinking)
    icon = "ON" if state.thinking == "enabled" else "OFF"
    show_success(f"思维模式 [{icon}]: {old} → {state.thinking}")


ROUTING_MODE_LABELS = {
    "rules": "规则优先 + LLM 兜底 (默认)",
    "llm_primary": "LLM 主路由",
    "shadow": "影子模式 (同时跑规则和 LLM)",
    "grayscale": "灰度模式 (按比例分配)",
}


def cmd_route(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    mode = args.strip()
    if not mode:
        console.print("\n[bold]可用路由模式:[/bold]")
        for key, label in ROUTING_MODE_LABELS.items():
            marker = " [dim](当前)[/dim]" if key == state.routing_mode else ""
            console.print(f"  [cyan]•[/cyan] {key}  →  {label}{marker}")
        show_info("用法: /route <模式>  (例如: /route llm_primary)")
        return
    if mode not in ROUTING_MODE_LABELS:
        show_error(f"未知路由模式: {mode}，可选: {', '.join(ROUTING_MODE_LABELS.keys())}")
        return
    old = state.routing_mode
    state.routing_mode = mode
    logger.log_config_change("routing_mode", old, mode)
    show_success(f"路由模式: {old} → {mode}  ({ROUTING_MODE_LABELS[mode]})")


def cmd_dynamic(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    old = state.dynamic_prompt
    state.dynamic_prompt = not old
    logger.log_config_change("dynamic_prompt", str(old), str(state.dynamic_prompt))
    icon = "ON" if state.dynamic_prompt else "OFF"
    show_success(f"动态提示词 [{icon}]: {old} → {state.dynamic_prompt}")


def cmd_config(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    show_config_table(state.as_dict())

    parts = args.strip().split(maxsplit=1)
    if not parts:
        show_info("用法: /config <key> <value>  (例如: /config safety_mode strict)")
        show_info("可修改的键: model, base_url, safety_mode, temperature, max_tokens, thinking, reasoning_effort, confidence_threshold, routing_mode, dynamic_prompt")
        return

    key = parts[0]
    new_value = parts[1] if len(parts) > 1 else ""

    if not new_value:
        show_error("请提供新值")
        return

    if not hasattr(state, key):
        show_error(f"未知配置项: {key}")
        return

    old_value = getattr(state, key)
    try:
        if key == "reasoning_effort":
            new_value = normalize_reasoning_effort(new_value)
        elif isinstance(old_value, bool):
            new_value = new_value.lower() in ("true", "1", "yes")
        elif isinstance(old_value, float):
            new_value = float(new_value)
        elif isinstance(old_value, int):
            new_value = int(new_value)
    except (ValueError, TypeError):
        show_error(f"无效值: {new_value}")
        return

    setattr(state, key, new_value)
    logger.log_config_change(key, old_value, new_value)
    show_success(f"{key}: {old_value} → {new_value}")


def cmd_list(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    subcommand = args.strip()

    if not subcommand or subcommand == "transcripts":
        transcripts = available_transcripts(TRANSCRIPT_DIR)
        console.print(f"\n[bold]转写文本[/bold] ({len(transcripts)} 个):")
        show_list_section("transcripts", transcripts)

    if not subcommand or subcommand == "templates":
        templates = available_files(TEMPLATE_DIR)
        console.print(f"\n[bold]总结模板[/bold] ({len(templates)} 个):")
        show_list_section("templates", templates)

    if not subcommand or subcommand == "industries":
        industries = available_files(INDUSTRY_DIR)
        console.print(f"\n[bold]行业提示词[/bold] ({len(industries)} 个):")
        show_list_section("industries", industries)

    if subcommand and subcommand not in ("transcripts", "templates", "industries"):
        show_error(f"未知列表类型: {subcommand}，可选: transcripts, templates, industries")


def cmd_help(args: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    show_help()


COMMANDS: dict[str, CommandFn] = {
    "/run": cmd_run,
    "/classify": cmd_classify,
    "/config": cmd_config,
    "/think": cmd_think,
    "/route": cmd_route,
    "/dynamic": cmd_dynamic,
    "/model": cmd_model,
    "/list": cmd_list,
    "/help": cmd_help,
}

ALIASES: dict[str, str] = {
    "/r": "/run",
    "/c": "/classify",
    "/cfg": "/config",
    "/t": "/think",
    "/m": "/model",
    "/ls": "/list",
    "/h": "/help",
    "/?": "/help",
}


def dispatch(line: str, state: SessionState, logger: SessionLogger, root: Path) -> None:
    stripped = line.strip()
    if not stripped:
        return

    parts = stripped.split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    resolved = ALIASES.get(cmd, cmd)
    handler = COMMANDS.get(resolved)

    if handler is None:
        show_error(f"未知命令: {cmd}，输入 /help 查看可用命令")
        logger.log("command_error", data={"command": cmd, "error": "unknown_command"})
        return

    try:
        handler(args, state, logger, root)
    except Exception as exc:
        show_error(f"命令执行失败: {exc}")
        logger.log("command_error", data={"command": cmd, "error": str(exc)})
