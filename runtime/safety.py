from __future__ import annotations

import re


SAFETY_RISK_PATTERNS: dict[str, list[str]] = {
    "cn_political_sensitive": [
        r"台湾.{0,12}(政治|独立|选举|统独|主权|台独)",
        r"(台湾|台独|统独|中华民国)",
        r"(中国)?国家领导人",
        r"习近平",
        r"李强",
        r"赵乐际",
        r"王沪宁",
        r"蔡奇",
        r"丁薛祥",
        r"李希",
    ],
    "self_harm_guidance": [
        r"自杀.{0,12}(方法|教程|步骤|怎么|如何|引导|诱导)",
        r"轻生.{0,12}(方法|教程|步骤|怎么|如何|引导|诱导)",
        r"自残.{0,12}(方法|教程|步骤|怎么|如何|引导|诱导)",
        r"(割腕|跳楼|不想活)",
    ],
    "abusive_or_profane": [
        r"粗口",
        r"脏话",
        r"辱骂",
        r"傻逼",
        r"妈的",
        r"操你",
        r"滚蛋",
        r"垃圾",
    ],
    "harmful_or_illicit_terms": [
        r"不良词汇",
        r"黄赌毒",
        r"毒品",
        r"诈骗",
        r"洗钱",
        r"违法犯罪",
    ],
    "privacy": [
        r"\b1[3-9]\d{9}\b",
        r"\b\d{17}[\dXx]\b",
        r"身份证",
        r"手机号",
        r"住址",
        r"银行卡",
    ],
}

SAFETY_SYSTEM_CONSTRAINT = """## 中立摘要安全约束

本次任务是对录音转写文本进行中立、合规、非操作性的会议纪要或业务总结。遇到中国政治敏感信息、台湾政治相关内容、自伤自杀引导、不良词汇、粗口辱骂或隐私信息等敏感片段时，必须遵守：

1. 保留与业务总结有关的事实含义，但不要复述刺激性原话、动员性话术、违法操作细节、自伤方法细节或可执行步骤。
2. 将敏感片段概括为安全、合规、舆情、隐私或内容治理风险，并说明其对业务讨论、产品上线、审核通过或后续行动的影响。
3. 不站队、不煽动、不扩写政治立场，不生成宣传、动员、规避审核、违法、自伤或伤害他人的建议。
4. 如果原文包含高风险内容，只做高层概述和风险标注；信息不足时写“待确认”。
5. 输出仍应遵循用户总结模板，除非 strict 模式要求使用更保守的固定结构。
"""

STRICT_SYSTEM_CONSTRAINT = """## Strict 模式固定输出结构

当前处于 strict 模式时，必须使用以下固定结构输出 Markdown，不要沿用用户模板中的其他结构，也不要省略“安全与合规风险”板块：

## 会议概览
## 关键讨论
## 已确认事项
## 待确认事项
## 安全与合规风险
## 后续行动

在“安全与合规风险”中仅输出“概括 + 风险类型 + 对业务总结的影响”，不要输出敏感原话或操作性细节。
"""

STRICT_USER_TEMPLATE = """# Strict 模式用户总结模板

请只使用以下 Markdown 结构输出：

## 会议概览

用 2-4 条要点概括本次会议的核心主题、重要结论和当前状态。

## 关键讨论

按议题整理主要讨论内容，保留事实、观点、依据和待补充信息。

## 已确认事项

整理已经明确的共识、决策、时间节点和阶段性判断。

## 待确认事项

列出尚未明确、需要补充材料、需要进一步沟通或等待决策的信息。

## 安全与合规风险

仅输出敏感内容的概括、风险类型及其对业务总结、产品上线、平台审核或后续行动的影响；不要复述敏感原话或操作性细节。

## 后续行动

使用待办清单格式提取任务、负责人、截止时间、状态和优先级。
"""

STRICT_FINAL_INSTRUCTION = """# Strict 模式最终输出要求

请检查最终 Markdown 是否严格包含并只包含以下一级板块：

## 会议概览
## 关键讨论
## 已确认事项
## 待确认事项
## 安全与合规风险
## 后续行动

不得将“安全与合规风险”合并到其他板块。
"""

SAFETY_USER_BOUNDARY_TEMPLATE = """# 敏感内容处理边界

本次任务是会议纪要或业务总结，不是生成敏感内容、行动方案、宣传话术或规避审核方法。

本地预检识别到的风险标签：{risk_labels}

请将相关内容按业务含义进行中立概括，并优先归入安全、合规、舆情、隐私或内容治理风险。不要复述政治敏感、自伤引导、不良词汇、粗口辱骂或攻击性细节。
"""

REFUSAL_MARKERS = [
    "无法处理",
    "不能处理",
    "无法总结",
    "不能总结",
    "我不能",
    "我无法",
    "抱歉",
    "sorry",
    "cannot assist",
    "can't assist",
]

SENSITIVE_EXAMPLE_PATTERNS = [
    (
        r"（如[“\"']?台湾[”\"']?、[“\"']?自杀[”\"']?、[“\"']?习近平[”\"']?等）",
        "（如政治公共议题、自伤等敏感内容）",
    ),
    (
        r"如[“\"']?台湾[”\"']?、[“\"']?自杀[”\"']?、[“\"']?习近平[”\"']?等",
        "如政治公共议题、自伤等敏感内容",
    ),
]


def detect_safety_risks(text: str) -> list[str]:
    risks: list[str] = []
    for label, patterns in SAFETY_RISK_PATTERNS.items():
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            risks.append(label)
    return risks


def should_apply_safety_constraints(safety_mode: str, risks: list[str]) -> bool:
    if safety_mode == "off":
        return False
    if safety_mode == "reactive":
        return False
    if safety_mode == "strict":
        return True
    return bool(risks)


def needs_strict_retry(content: str) -> bool:
    stripped = content.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if any(marker.lower() in lowered for marker in REFUSAL_MARKERS):
        return True
    return "##" not in stripped and "- " not in stripped


def sanitize_sensitive_output(content: str) -> str:
    sanitized = content
    for pattern, replacement in SENSITIVE_EXAMPLE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized
