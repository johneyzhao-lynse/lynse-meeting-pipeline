from __future__ import annotations

import re

from .assets import load_industry_manifest, load_template_manifest
from .models import Candidate, CandidateRanking, TranscriptFeatures


SPEAKER_ID_PATTERNS = [
    re.compile(r"^\[[0-9:\- ]+\]\s*发言人(\d+)[:：]", re.MULTILINE),
    re.compile(r"^\s*发言人(\d+)[:：]", re.MULTILINE),
]
TIMESTAMP_SPEAKER_PATTERN = re.compile(r"^\[[0-9:\- ]+\]\s*发言人\d+[:：]")
PRODUCT_RELEASE_TERMS = ["版本", "提审", "上架", "发布", "更新", "渠道", "安卓", "华为", "功能评审"]
TEMPLATE_BOOSTS = {
    "product-analysis.md": {"产品": 2.0, "版本": 3.0, "发布": 2.0, "上架": 3.0, "渠道": 1.5, "订阅": 4.0, "续费": 4.0, "会员": 3.5},
    "requirements-review.md": {"评审": 3.0, "需求": 2.0, "版本": 2.5, "提审": 3.0, "上架": 2.5, "更新": 2.0, "订阅": 3.0, "续费": 3.0, "会员": 2.5},
    "general-meeting.md": {"会议": 1.0, "讨论": 1.0, "同步": 1.0},
    "government-project-bidding.md": {
        "城市设计": 8.0,
        "国际征集": 10.0,
        "方案征集": 9.0,
        "征集": 6.0,
        "招标": 5.0,
        "预审": 4.0,
        "竞征": 8.0,
        "任务书": 5.0,
        "答疑": 5.0,
        "成果提交": 6.0,
        "方案评审": 6.0,
        "主创": 4.0,
        "设计团队": 4.0,
        "自然资源局": 6.0,
    },
    "technical-interview-summary.md": {
        "面试": 18.0,
        "候选人": 14.0,
        "简历": 14.0,
        "技术岗": 8.0,
        "技术岗位": 8.0,
        "前端工程师": 8.0,
        "工作经历": 5.0,
        "项目经历": 5.0,
        "薪资": 16.0,
        "离职": 14.0,
        "HR": 16.0,
        "到岗": 12.0,
        "offer": 10.0,
        "base": 10.0,
        "项目奖": 10.0,
    },
    "sales-follow-up.md": {
        "销售": 6.0,
        "谈判": 7.0,
        "报价": 7.0,
        "收费": 8.0,
        "合作": 5.0,
        "洽谈": 6.0,
        "对接": 5.0,
        "商务": 5.0,
        "客户": 4.0,
        "采购": 5.0,
        "合同": 6.0,
        "回款": 6.0,
        "签单": 6.0,
        "交付": 5.0,
        "投标": 7.0,
        "比价": 7.0,
        "出口": 5.0,
        "结算": 5.0,
    },
    "channel-meeting.md": {
        "渠道": 10.0,
        "分销": 8.0,
        "入驻": 9.0,
        "佣金": 8.0,
        "年费": 7.0,
        "返利": 8.0,
        "账期": 7.0,
        "DRP": 10.0,
        "经销商": 8.0,
        "代理": 6.0,
    },
    "financial-survey-visit.md": {
        "银行": 12.0,
        "金融": 9.0,
        "调研": 7.0,
        "访问": 6.0,
        "尽调": 8.0,
        "结算": 9.0,
        "跨境": 9.0,
        "收汇": 10.0,
        "出海": 7.0,
        "银企": 10.0,
        "客户经理": 9.0,
        "外汇": 8.0,
        "补贴": 6.0,
        "资金": 7.0,
        "贷款": 7.0,
    },
    "commercial-estate-consulting-expert.md": {
        "城市更新": 10.0,
        "工业遗存": 12.0,
        "文商旅": 10.0,
        "商业地产": 9.0,
        "招商": 8.0,
        "改造": 6.0,
        "运营": 4.0,
        "存量": 7.0,
        "老厂房": 8.0,
        "EPC": 9.0,
        "咨询": 5.0,
        "勾地": 9.0,
        "投建营": 10.0,
        "首店": 7.0,
        "租金": 6.0,
    },
    "marketing-campaign-planning.md": {
        "营销": 8.0,
        "商业模式": 8.0,
        "冷启动": 8.0,
        "品牌": 4.0,
        "增长": 4.0,
        "剧场": 7.0,
        "沉浸式": 8.0,
        "推广": 4.0,
        "渠道": 3.0,
    },
}
INDUSTRY_BOOSTS = {
    "government-project-industry.md": {
        "政府": 4.0,
        "城市设计": 6.0,
        "国际征集": 8.0,
        "方案征集": 8.0,
        "征集": 5.0,
        "招标": 5.0,
        "预审": 4.0,
        "任务书": 4.0,
        "答疑": 4.0,
        "自然资源局": 8.0,
        "建管委": 6.0,
        "区政府": 6.0,
        "规划": 3.0,
    },
    "marketing-industry.md": {
        "营销": 6.0,
        "商业模式": 4.0,
        "冷启动": 5.0,
        "品牌": 4.0,
        "增长": 4.0,
        "投放": 4.0,
        "渠道": 3.0,
    },
    "insurance-industry.md": {
        "保险": 6.0,
        "理赔": 7.0,
        "保单": 6.0,
        "核保": 7.0,
        "赔付": 6.0,
        "保额": 5.0,
        "保费": 5.0,
        "健康告知": 7.0,
        "承保": 5.0,
    },
    "consulting-industry.md": {
        "咨询": 5.0,
        "访谈": 4.0,
        "洞察": 3.0,
        "调研": 4.0,
        "顾问": 4.0,
    },
    "construction-industry.md": {
        "工程": 5.0,
        "施工": 6.0,
        "整改": 5.0,
        "验收": 5.0,
        "总包": 5.0,
        "分包": 4.0,
        "监理": 5.0,
    },
    "real-estate-industry.md": {
        "房源": 6.0,
        "贷款": 4.0,
        "税费": 4.0,
        "成交": 5.0,
        "开盘": 5.0,
        "楼盘": 6.0,
        "户型": 5.0,
    },
    "investment-financing-industry.md": {
        "融资": 7.0,
        "估值": 6.0,
        "投资人": 7.0,
        "尽调": 7.0,
        "路演": 6.0,
        "BP": 5.0,
        "TS": 5.0,
        "Term Sheet": 5.0,
    },
    "education-training-industry.md": {
        "教育": 4.0,
        "培训": 4.0,
        "课程": 5.0,
        "学员": 5.0,
        "老师": 3.0,
        "教案": 4.0,
    },
    "legal-industry.md": {
        "法律": 6.0,
        "合同": 2.0,
        "仲裁": 8.0,
        "诉讼": 8.0,
        "律师": 7.0,
        "合规": 6.0,
        "条款": 3.0,
    },
    "financial-planning-industry.md": {
        "理财": 6.0,
        "收益": 4.0,
        "资产": 5.0,
        "基金": 5.0,
        "净值": 5.0,
        "定投": 5.0,
    },
    "it-internet-industry.md": {
        "产品": 2.0,
        "上架": 4.0,
        "提审": 4.0,
        "迭代": 4.0,
        "订阅": 5.0,
        "会员": 4.0,
        "续费": 5.0,
        "APP": 3.0,
        "商业化": 4.0,
        "智能体": 4.0,
        "Agent": 3.0,
        "SDK": 3.0,
        "API": 3.0,
        "AWS": 5.0,
        "京东": 5.0,
        "阿里云": 5.0,
        "火山引擎": 5.0,
    },
    "semiconductor-chip-industry.md": {
        "芯片": 7.0,
        "半导体": 7.0,
        "光互联": 8.0,
        "光模块": 7.0,
        "算力": 6.0,
        "GPU": 6.0,
        "制程": 6.0,
        "封装": 5.0,
        "晶圆": 6.0,
        "带宽": 4.0,
        "功耗": 4.0,
        "NVL": 7.0,
        "HBM": 7.0,
    },
    "cultural-tourism-industry.md": {
        "文旅": 7.0,
        "文创": 6.0,
        "剧场": 7.0,
        "剧本杀": 7.0,
        "沉浸式": 6.0,
        "工业遗存": 7.0,
        "老厂房": 6.0,
        "改造": 4.0,
        "招商": 4.0,
        "翻台率": 6.0,
        "客单价": 5.0,
        "商业地产": 6.0,
        "太古里": 8.0,
        "K11": 8.0,
        "第一太平戴维斯": 9.0,
        "戴德梁行": 9.0,
        "仲量联行": 9.0,
        "世邦魏理仕": 9.0,
        "高力国际": 9.0,
        "建筑设计事务所": 7.0,
        "gmp": 7.0,
        "赫尔佐格": 7.0,
        "Foster": 7.0,
        "福斯特": 7.0,
        "扎哈": 7.0,
        "BIG": 7.0,
        "SANAA": 7.0,
        "城市更新": 6.0,
        "EPC": 5.0,
    },
    "ecommerce-retail-industry.md": {
        "电商": 6.0,
        "零售": 5.0,
        "京东": 6.0,
        "天猫": 6.0,
        "拼多多": 6.0,
        "DRP": 7.0,
        "佣金": 5.0,
        "年费": 5.0,
        "返利": 5.0,
        "账期": 5.0,
        "入驻": 5.0,
        "结算": 4.0,
    },
}
INDUSTRY_IGNORED_SENSITIVE_TERMS = {
    "敏感",
    "台湾",
    "台独",
    "统独",
    "中华民国",
    "举报",
    "政治",
    "领导人",
    "习近平",
    "政党",
    "选举",
    "抗议",
    "游行",
    "维权",
    "自杀",
    "轻生",
    "自残",
    "割腕",
    "跳楼",
    "不想活",
    "不良词汇",
    "粗口",
    "脏话",
    "辱骂",
    "傻逼",
    "妈的",
    "操你",
}


def extract_features(transcript: str) -> TranscriptFeatures:
    normalized = _strip_exported_title(transcript.strip())
    char_count = len(normalized)
    speaker_ids: set[str] = set()
    for pattern in SPEAKER_ID_PATTERNS:
        speaker_ids.update(pattern.findall(normalized))
    speaker_count = max(1, len(speaker_ids))

    vocabulary = set()
    for item in load_template_manifest().templates:
        vocabulary.update(item.keywords)
    for item in load_industry_manifest().industries:
        vocabulary.update(item.keywords)

    keyword_hits: dict[str, int] = {}
    key_windows: list[str] = []
    for keyword in sorted(vocabulary, key=len, reverse=True):
        hits = normalized.count(keyword)
        if hits:
            keyword_hits[keyword] = hits
            if len(key_windows) < 5:
                index = normalized.find(keyword)
                start = max(0, index - 20)
                end = min(len(normalized), index + len(keyword) + 20)
                key_windows.append(normalized[start:end])

    return TranscriptFeatures(
        transcript=normalized,
        char_count=char_count,
        speaker_count=speaker_count,
        keyword_hits=keyword_hits,
        head_snippet=normalized[:800],
        tail_snippet=normalized[-400:] if len(normalized) > 400 else normalized,
        key_windows=key_windows,
    )


def _strip_exported_title(text: str) -> str:
    lines = text.splitlines()
    non_empty_indexes = [index for index, line in enumerate(lines) if line.strip()]
    if len(non_empty_indexes) < 2:
        return text
    first_index, second_index = non_empty_indexes[0], non_empty_indexes[1]
    if first_index == 0 and TIMESTAMP_SPEAKER_PATTERN.match(lines[second_index].strip()):
        return "\n".join(lines[second_index:]).strip()
    return text


def _score_candidate(keywords: list[str], feature_hits: dict[str, int]) -> Candidate:
    score = 0.0
    matched: list[str] = []
    for keyword in keywords:
        hits = feature_hits.get(keyword, 0)
        if hits:
            score += hits * max(1.0, len(keyword) / 2)
            matched.append(keyword)
    return Candidate(name="", score=score, matched_keywords=matched)


def _boosted_score(name: str, transcript: str, feature_hits: dict[str, int]) -> Candidate:
    item = _score_candidate(TEMPLATE_BOOSTS.get(name, {}).keys(), feature_hits)
    score = 0.0
    matched: list[str] = []
    for keyword, weight in TEMPLATE_BOOSTS.get(name, {}).items():
        hits = feature_hits.get(keyword, 0)
        if hits:
            score += hits * weight
            matched.append(keyword)
    if name in {"product-analysis.md", "requirements-review.md"} and any(term in transcript for term in PRODUCT_RELEASE_TERMS):
        score += 4.0
        matched.extend([term for term in PRODUCT_RELEASE_TERMS if term in transcript][:3])
    return Candidate(name=name, score=score, matched_keywords=matched)


def _boosted_industry_score(name: str, feature_hits: dict[str, int]) -> Candidate:
    score = 0.0
    matched: list[str] = []
    for keyword, weight in INDUSTRY_BOOSTS.get(name, {}).items():
        hits = feature_hits.get(keyword, 0)
        if hits:
            score += hits * weight
            matched.append(keyword)
    return Candidate(name=name, score=score, matched_keywords=matched)


def rank_candidates(features: TranscriptFeatures) -> CandidateRanking:
    template_candidates: list[Candidate] = []
    for item in load_template_manifest().templates:
        scored = _score_candidate(item.keywords, features.keyword_hits)
        boosted = _boosted_score(item.name, features.transcript, features.keyword_hits)
        bonus = 0.0
        if "客户沟通" in item.scene_labels and features.speaker_count >= 2:
            bonus += 0.4
        if "学习培训" in item.scene_labels and any(word in features.transcript for word in ["课程", "老师", "学员", "讲"]):
            bonus += 0.6
        if item.name == "general-meeting.md" and any(term in features.transcript for term in PRODUCT_RELEASE_TERMS):
            bonus -= 1.0
        template_candidates.append(
            Candidate(
                name=item.name,
                score=scored.score + boosted.score + bonus,
                matched_keywords=list(dict.fromkeys(scored.matched_keywords + boosted.matched_keywords)),
            )
        )

    industry_candidates: list[Candidate] = []
    for item in load_industry_manifest().industries:
        scored = _score_candidate(item.keywords, features.keyword_hits)
        boosted = _boosted_industry_score(item.name, features.keyword_hits)
        filtered_keywords = [
            keyword
            for keyword in list(dict.fromkeys(scored.matched_keywords + boosted.matched_keywords))
            if keyword not in INDUSTRY_IGNORED_SENSITIVE_TERMS
        ]
        industry_candidates.append(
            Candidate(
                name=item.name,
                score=boosted.score + sum(
                    features.keyword_hits.get(keyword, 0) * max(1.0, len(keyword) / 2)
                    for keyword in filtered_keywords
                ),
                matched_keywords=filtered_keywords,
            )
        )

    template_candidates.sort(key=lambda item: (-item.score, item.name))
    industry_candidates.sort(key=lambda item: (-item.score, item.name))

    fallback_name = "general-meeting.md"
    top_templates = template_candidates[:5]
    if all(candidate.name != fallback_name for candidate in top_templates):
        fallback = next(item for item in template_candidates if item.name == fallback_name)
        top_templates.append(fallback)

    top_industries = [item for item in industry_candidates if item.score >= 2.0][:3]
    return CandidateRanking(templates=top_templates, industries=top_industries)
