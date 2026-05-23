from __future__ import annotations

from dataclasses import dataclass

TEMPLATE_MEETING_TYPE: dict[str, str] = {
    "product-analysis.md": "产品周会",
    "requirements-review.md": "需求评审会",
    "technical-interview-summary.md": "面试",
    "interview-insights.md": "面试",
    "consulting-interview.md": "面试",
    "user-research-interview.md": "面试",
    "sales-follow-up.md": "销售会议",
    "channel-meeting.md": "渠道会议",
    "customer-communication.md": "客户谈判",
    "marketing-campaign-planning.md": "推广策划会",
    "project-weekly-meeting.md": "项目推进会",
    "project-progress-meeting.md": "项目推进会",
    "retrospective-meeting.md": "复盘会",
    "high-fidelity-minutes.md": "管理层例会",
    "general-meeting.md": "管理层例会",
    "government-project-bidding.md": "战略会议",
    "government-project-report.md": "战略会议",
    "fundraising-roadshow.md": "合作洽谈会",
    "investor-meeting.md": "合作洽谈会",
    "investment-review.md": "财务会议",
    "legal-consultation.md": "法务合规",
    "contract-review-communication.md": "法务合规",
    "architectural-design-review.md": "技术评审会",
    "insurance-claim-communication.md": "客户谈判",
    "insurance-customer-needs.md": "客户谈判",
    "financial-planning-customer-communication.md": "客户谈判",
    "real-estate-customer-communication.md": "客户谈判",
    "real-estate-project-meeting.md": "销售会议",
    "real-estate-transaction-follow-up.md": "销售会议",
    "property-service-communication.md": "客户谈判",
    "construction-project-meeting.md": "销售会议",
    "consulting-project-meeting.md": "战略会议",
    "education-training-communication.md": "其他",
    "classroom-teaching.md": "其他",
    "podcast-content.md": "其他",
    "two-person-call.md": "管理层例会",
    "financial-survey-visit.md": "银企访谈",
    "commercial-estate-consulting-expert.md": "商业地产顾问会",
}

MEETING_TYPE_TO_CATEGORY: dict[str, str] = {
    # 产品类
    "产品周会": "产品类", "需求评审会": "产品类", "技术评审会": "产品类",
    "每日站会": "产品类", "架构与设计评审": "产品类", "Bug/缺陷排查会": "产品类",
    # 销售类
    "销售会议": "销售类", "合作洽谈会": "销售类", "客户谈判": "销售类",
    "渠道会议": "销售类", "银企访谈": "销售类",
    "客诉与售后跟进会": "销售类", "供应商评审会": "销售类", "商业地产顾问会": "销售类",
    # 人力类
    "面试": "人力类",
    "1对1沟通": "人力类", "全员大会": "人力类",
    "团队分享会/技术沙龙": "人力类", "绩效面谈": "人力类",
    # 营销类
    "推广策划会": "营销类",
    "用户调研/访谈": "营销类", "运营数据分析会": "营销类", "头脑风暴会": "营销类",
    # 项目类
    "项目推进会": "项目类", "复盘会": "项目类",
    "项目启动会": "项目类", "跨部门协调会": "项目类", "事故复盘/根因分析": "项目类",
    # 管理类
    "管理层例会": "管理类",
    # 战略类
    "战略会议": "战略类", "董事会/股东会": "战略类",
    # 财务类
    "财务会议": "财务类", "预算审计会": "财务类",
    # 法务类
    "法务合规": "法务类",
    # 其他
    "其他": "其他",
}

MEETING_TYPE_TO_MODE: dict[str, str] = {
    # 产品类
    "产品周会": "同步型", "需求评审会": "评估型", "技术评审会": "评估型",
    "每日站会": "同步型", "架构与设计评审": "评估型", "Bug/缺陷排查会": "评估型",
    # 销售类
    "销售会议": "谈判型", "合作洽谈会": "谈判型", "客户谈判": "谈判型",
    "渠道会议": "谈判型", "银企访谈": "评估型",
    "客诉与售后跟进会": "谈判型", "供应商评审会": "评估型", "商业地产顾问会": "评估型",
    # 人力类
    "面试": "评估型", "1对1沟通": "同步型", "全员大会": "同步型",
    "团队分享会/技术沙龙": "同步型", "绩效面谈": "评估型",
    # 营销类
    "推广策划会": "决策型", "用户调研/访谈": "评估型",
    "运营数据分析会": "同步型", "头脑风暴会": "决策型",
    # 项目类
    "项目推进会": "同步型", "复盘会": "评估型",
    "项目启动会": "决策型", "跨部门协调会": "同步型", "事故复盘/根因分析": "评估型",
    # 管理类
    "管理层例会": "同步型",
    # 战略类
    "战略会议": "决策型", "董事会/股东会": "决策型",
    # 财务类
    "财务会议": "同步型", "预算审计会": "评估型",
    # 法务类
    "法务合规": "评估型",
    # 其他
    "其他": "同步型",
}


@dataclass(frozen=True)
class MeetingInfo:
    meeting_type: str
    meeting_category: str
    meeting_mode: str

    def as_dict(self) -> dict[str, str]:
        return {
            "meeting_type": self.meeting_type,
            "meeting_category": self.meeting_category,
            "meeting_mode": self.meeting_mode,
        }


def get_meeting_type(template_name: str) -> str:
    return TEMPLATE_MEETING_TYPE.get(template_name, "其他")


def get_meeting_info(template_name: str) -> MeetingInfo:
    meeting_type = get_meeting_type(template_name)
    return MeetingInfo(
        meeting_type=meeting_type,
        meeting_category=MEETING_TYPE_TO_CATEGORY.get(meeting_type, "其他"),
        meeting_mode=MEETING_TYPE_TO_MODE.get(meeting_type, "同步型"),
    )
