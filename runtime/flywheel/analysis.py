from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from .models import AnalysisRecord, FeedbackRecord


ANALYSIS_SYSTEM_PROMPT = """你是总结质量飞轮分析助手。

你的任务不是直接生成最终用户总结，而是分析失败样本、用户反馈和人工评审，提炼可执行的提示词、模板、路由或评测集改进建议。

输出必须聚焦：
1. 高频缺失字段或行业关注点。
2. 结构、事实、语气、行动项方面的具体问题。
3. 可落地的提示词优化建议。
4. 适合加入回归评测集的检查点。

避免泛泛建议，不要复述完整转写文本，不要编造未出现的行业规则。
"""


def build_reasoning_analysis_messages(
    *,
    samples: list[dict[str, str]],
    feedbacks: list[FeedbackRecord],
    analysis_goal: str,
) -> list[dict[str, str]]:
    payload = {
        "analysis_goal": analysis_goal,
        "samples": samples,
        "feedbacks": [item.as_dict() for item in feedbacks],
        "required_output": {
            "findings": "列出具体问题和证据摘要",
            "recommended_prompt_changes": "列出可直接沉淀到提示词或模板的规则",
            "evaluation_candidates": "列出适合进入回归评测集的检查点",
        },
    }
    return [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, indent=2)},
    ]


def write_analysis_record(
    directory: Path,
    *,
    sample_ids: list[str],
    reasoning_model: str,
    analysis_goal: str,
    findings: list[str],
    recommended_prompt_changes: list[str],
    review_status: str = "pending",
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    analysis_id = f"analysis-{timestamp}"
    record = AnalysisRecord(
        analysis_id=analysis_id,
        sample_ids=sample_ids,
        reasoning_model=reasoning_model,
        analysis_goal=analysis_goal,
        findings=findings,
        recommended_prompt_changes=recommended_prompt_changes,
        review_status=review_status,
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{analysis_id}.json"
    path.write_text(json.dumps(record.as_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
