from __future__ import annotations

SCENE_INSTRUCTIONS: dict[str, dict] = {
    "会议协作": {
        "target_audience": "参会人员、未参会但需了解进展的同事、团队负责人",
        "output_guidance": "突出共识和分歧，明确待办和截止时间",
        "special_requirements": [
            "区分已确认事实与待确认信息",
            "行动项需标注负责人和截止时间",
        ],
    },
    "客户沟通": {
        "target_audience": "客户关系负责人、销售团队、客服团队",
        "output_guidance": "区分己方和客户陈述，关注客户关切和承诺事项",
        "special_requirements": [
            "区分己方和客户陈述，标注信息来源",
            "注意客户关切和待确认信息",
            "标注所有承诺和交付时间节点",
        ],
    },
    "技术讨论": {
        "target_audience": "技术团队、架构师、项目负责人",
        "output_guidance": "关注技术决策理由和架构影响，保留关键技术细节",
        "special_requirements": [
            "保留技术术语和版本号",
            "标注技术决策及其理由",
            "记录性能指标和约束条件",
        ],
    },
    "管理决策": {
        "target_audience": "管理层、决策参与者、执行负责人",
        "output_guidance": "突出决策项和负责人，说明决策背景和依据",
        "special_requirements": [
            "每个决策项标注决策人和执行时间",
            "记录反对意见和权衡考量",
        ],
    },
    "销售服务": {
        "target_audience": "销售团队、客户成功团队、业务负责人",
        "output_guidance": "提取客户需求、异议和处理方案，跟踪后续行动",
        "special_requirements": [
            "标注客户异议和应对策略",
            "记录报价和优惠信息",
            "明确跟进计划和责任人",
        ],
    },
    "招聘面试": {
        "target_audience": "招聘团队、用人经理、HR",
        "output_guidance": "结构化记录候选人表现和评估结论",
        "special_requirements": [
            "按维度（技术、沟通、文化匹配等）评估候选人",
            "记录关键问答和候选人原话",
            "给出明确的录用建议",
        ],
    },
    "学习培训": {
        "target_audience": "学员、培训负责人、知识管理者",
        "output_guidance": "提炼核心知识点和操作步骤，形成可复习的资料",
        "special_requirements": [
            "提取核心概念和定义",
            "整理操作步骤和注意事项",
            "标注延伸学习资源",
        ],
    },
    "内容创作": {
        "target_audience": "内容团队、品牌负责人",
        "output_guidance": "提取创意方向、内容框架和关键表达",
        "special_requirements": [
            "记录创意灵感和参考素材",
            "整理内容框架和发布计划",
        ],
    },
    "访谈调研": {
        "target_audience": "调研团队、产品经理、研究人员",
        "output_guidance": "保留受访者的核心观点和原话，提炼关键洞察",
        "special_requirements": [
            "保留受访者精彩原话",
            "按主题整理问答",
            "提炼3个最核心的洞察",
        ],
    },
    "项目推进": {
        "target_audience": "项目经理、团队成员、利益相关方",
        "output_guidance": "聚焦进度、风险和阻塞项，明确下一步行动",
        "special_requirements": [
            "标注当前进度和里程碑状态",
            "记录风险和阻塞项",
            "明确下一步行动和负责人",
        ],
    },
    "政府项目": {
        "target_audience": "项目团队、合规负责人、管理层",
        "output_guidance": "严格记录流程节点和合规要求，避免主观评价",
        "special_requirements": [
            "严格记录流程节点和时间线",
            "标注合规和审批要求",
            "避免主观评价和推测性内容",
        ],
    },
}


def get_scene_instruction(scene_label: str) -> dict | None:
    return SCENE_INSTRUCTIONS.get(scene_label)


def get_all_scene_labels() -> list[str]:
    return sorted(SCENE_INSTRUCTIONS.keys())
