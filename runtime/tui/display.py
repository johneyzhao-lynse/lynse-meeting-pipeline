from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console(stderr=False)


def show_banner() -> None:
    banner = Text()
    banner.append("Lynse Core TUI", style="bold cyan")
    banner.append("  — 输入 /help 查看命令，/quit 退出", style="dim")
    console.print(Panel(banner, border_style="cyan"))


def show_error(message: str) -> None:
    console.print(f"[bold red]错误:[/bold red] {message}")


def show_success(message: str) -> None:
    console.print(f"[bold green]✓[/bold green] {message}")


def show_info(message: str) -> None:
    console.print(f"[dim]→[/dim] {message}")


def show_config_table(state: dict[str, Any]) -> None:
    table = Table(title="当前配置", show_header=False, border_style="dim")
    table.add_column("键", style="cyan")
    table.add_column("值")
    display_keys = [
        "model", "base_url", "safety_mode", "temperature",
        "max_tokens", "thinking", "reasoning_effort", "confidence_threshold",
        "routing_mode", "dynamic_prompt",
    ]
    for key in display_keys:
        if key in state and state[key] is not None:
            table.add_row(key, str(state[key]))
    console.print(table)


def show_token_usage(usage: dict[str, int], cumulative: dict[str, int], call_count: int) -> None:
    table = Table(title="Token 消耗", border_style="green")
    table.add_column("", style="dim")
    table.add_column("本词调用", justify="right")
    table.add_column("会话累计", justify="right", style="bold")
    table.add_row(
        "Prompt tokens",
        str(usage.get("prompt_tokens", 0)),
        str(cumulative.get("prompt_tokens", 0)),
    )
    table.add_row(
        "Completion tokens",
        str(usage.get("completion_tokens", 0)),
        str(cumulative.get("completion_tokens", 0)),
    )
    table.add_row(
        "Total tokens",
        str(usage.get("total_tokens", 0)),
        str(cumulative.get("total_tokens", 0)),
    )
    table.add_row("API 调用次数", str(1), str(call_count))
    console.print(table)


def show_classification_result(result: dict[str, Any]) -> None:
    table = Table(title="分类结果", border_style="blue")
    table.add_column("字段", style="cyan")
    table.add_column("值")
    feature_summary = result.get("feature_summary", {})
    stage = feature_summary.get("classifier_stage", "rules")
    stage_display = {
        "rules": "规则引擎",
        "llm": "LLM 精排",
        "rules_llm_fallback": "规则引擎 (LLM 失败回退)",
        "llm_primary": "LLM 主路由",
        "llm_primary_fallback_to_rules": "LLM 主路由 (失败回退规则)",
        "shadow": "影子模式",
        "grayscale_llm": "灰度 (LLM)",
        "grayscale_rules": "灰度 (规则)",
        "grayscale_llm_fallback_to_rules": "灰度 (LLM 失败回退)",
    }.get(stage, stage)
    table.add_row("推荐模板", result.get("recommended_template", ""))
    table.add_row("推荐行业", str(result.get("recommended_industry_prompt") or "无"))
    industry_suggestion = feature_summary.get("industry_suggestion")
    if industry_suggestion:
        table.add_row("行业建议 (LLM)", industry_suggestion)
    table.add_row("置信度", f"{result.get('confidence', 0):.2%}")
    table.add_row("分类阶段", stage_display)
    routing_mode = result.get("routing_mode", "rules")
    if routing_mode != "rules":
        table.add_row("路由模式", routing_mode)
    table.add_row("场景标签", ", ".join(result.get("scene_labels", [])))
    table.add_row("意图标签", ", ".join(result.get("intent_labels", [])))
    table.add_row("是否回退", str(result.get("fallback_used", False)))
    if result.get("fallback_reason"):
        table.add_row("回退原因", result["fallback_reason"])
    table.add_row("匹配关键词", ", ".join(result.get("evidence_keywords", [])[:8]))
    console.print(table)

    shadow = result.get("shadow_comparison")
    if shadow:
        shadow_table = Table(title="影子对比", border_style="magenta")
        shadow_table.add_column("字段", style="cyan")
        shadow_table.add_column("规则结果", style="dim")
        shadow_table.add_column("LLM 结果", style="bold")
        rules_r = shadow.get("rules_result", {})
        llm_r = shadow.get("llm_result") or {}
        shadow_table.add_row("推荐模板", rules_r.get("recommended_template", ""), llm_r.get("recommended_template", ""))
        shadow_table.add_row("置信度", f"{rules_r.get('confidence', 0):.2%}", f"{llm_r.get('confidence', 0):.2%}" if llm_r else "N/A")
        agreed = shadow.get("agreed_template", True)
        agree_style = "green" if agreed else "red"
        shadow_table.add_row("模板一致", "", f"{'是' if agreed else '否'}", style=agree_style)
        console.print(shadow_table)

    ranking = result.get("candidate_ranking", {})
    if ranking.get("templates"):
        rank_table = Table(title="候选模板排名", border_style="dim")
        rank_table.add_column("排名", justify="right", style="dim")
        rank_table.add_column("模板", style="cyan")
        rank_table.add_column("分数", justify="right")
        rank_table.add_column("匹配关键词")
        for i, candidate in enumerate(ranking["templates"][:5], 1):
            rank_table.add_row(
                str(i),
                candidate["name"],
                f"{candidate['score']:.1f}",
                ", ".join(candidate.get("matched_keywords", [])[:5]),
            )
        console.print(rank_table)


def show_summary(content: str, output_path: str | None = None) -> None:
    md = Markdown(content)
    title = "生成总结"
    if output_path:
        title += f"  →  {output_path}"
    console.print(Panel(md, title=title, border_style="green"))


def show_list_section(title: str, items: list[str]) -> None:
    if not items:
        console.print(f"[dim]  ({title} 为空)[/dim]")
        return
    for item in items:
        console.print(f"  [cyan]•[/cyan] {item}")


def show_help() -> None:
    table = Table(title="可用命令", border_style="cyan", show_header=False)
    table.add_column("命令", style="bold cyan")
    table.add_column("说明")
    table.add_row("/run", "引导式执行完整流程（分类 → 选行业/模板 → 生成总结）")
    table.add_row("/run --dry-run", "同 /run 但只打印 payload，不调用 API")
    table.add_row("/classify", "对转写文本运行分类器，查看推荐模板和候选排名")
    table.add_row("/config", "查看/修改当前配置（model、safety-mode、temperature 等）")
    table.add_row("/think", "切换思维模式开关（enabled ↔ disabled）")
    table.add_row("/route [mode]", "查看/切换路由模式（rules, llm_primary, shadow, grayscale）")
    table.add_row("/dynamic", "切换动态提示词开关（ON ↔ OFF）")
    table.add_row("/model [name]", "查看预设模型列表，或切换模型（如: /model qwen）")
    table.add_row("/list [type]", "列出可用资源: transcripts, templates, industries")
    table.add_row("/help", "显示本帮助")
    table.add_row("/quit", "退出 TUI")
    console.print(table)
