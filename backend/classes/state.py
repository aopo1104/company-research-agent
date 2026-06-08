"""
================================================================================
state.py - LangGraph 工作流状态定义
================================================================================
定义了整个研究工作流的状态结构（TypedDict）
- InputState: 用户输入状态
- ResearchState: 工作流全过程状态（包含所有中间数据）
- job_status: 全局任务状态跟踪（用于WebSocket事件推送）

工作流的数据在各个节点间流转：
grounding → researchers → collector → curator → enricher → briefing → editor
"""

from typing import TypedDict, NotRequired, Required, Dict, List, Any
from collections import defaultdict
from datetime import datetime

# ============== 输入状态 ==============
# 定义用户提交的输入参数
class InputState(TypedDict, total=False):
    company: Required[str]
    company_url: NotRequired[str]
    hq_location: NotRequired[str]
    industry: NotRequired[str]
    job_id: NotRequired[str]

class InputState(TypedDict, total=False):
    """用户输入参数结构
    
    company: 公司名称（必需）
    company_url: 公司官网URL（可选）
    hq_location: 总部位置（可选）
    industry: 所在行业（可选）
    job_id: 任务ID（后端自动生成）
    """
    company: Required[str]
    company_url: NotRequired[str]
    hq_location: NotRequired[str]
    industry: NotRequired[str]
    job_id: NotRequired[str]

# ============== 研究状态（工作流全过程） ==============
# 从用户输入开始，经过8个阶段，最终生成报告
class ResearchState(InputState):
    """LangGraph工作流状态 - 包含所有中间和最终数据
    
    阶段1: grounding → site_scrape (官网页面)
    
    阶段2-3: researchers (3个并行节点) → company_data, news_data, social_media_data
                                         (~60个文档)
    
    阶段4: collector → (无新增字段，仅统计)
    
    阶段5: curator → curated_*_data, reference_titles, reference_info
                     (~40个文档，去重+评分筛选)
    
    阶段6: enricher → 为curated_*_data中的每个文档填充raw_content
                     (~35个文档，完整内容)
    
    阶段7: briefing → company_briefing, news_briefing, social_media_briefing
                     (3个类别的中文简报)
    
    阶段8: editor → report (最终Markdown报告)
    """
    # ---- 阶段1: 官网抓取 ----
    site_scrape: Dict[str, Any]              # {url: {raw_content, source, method, title}}
    
    # ---- 阶段2-3: 搜索文档（3个分析器） ----
    messages: List[Any]                      # 消息历史（LangChain）
    news_data: Dict[str, Any]                # 新闻数据文档 (~15个)
    company_data: Dict[str, Any]             # 公司数据文档 (~20个)
    social_media_data: Dict[str, Any]        # 社媒数据文档 (~20个)
    
    # ---- 阶段5: 筛选后的数据（curator） ----
    curated_news_data: Dict[str, Any]        # 筛选后新闻数据 (score≥0.4 或 官网, 最多30个)
    curated_company_data: Dict[str, Any]     # 筛选后公司数据 (同上)
    curated_social_media_data: Dict[str, Any] # 筛选后社媒数据 (同上)
    
    # ---- 引用信息（curator收集） ----
    references: List[str]                    # URL引用列表
    reference_titles: Dict[str, str]         # {url: page_title} - 用于[标题](url)格式
    reference_info: Dict[str, Any]           # {url: {source, score, category, ...}} - 完整元信息
    
    # ---- 阶段7: 生成的简报（3个类别） ----
    news_briefing: str                       # 新闻简报 (中文)
    company_briefing: str                    # 公司简报 (中文)
    social_media_briefing: str               # 社媒简报 (中文)
    
    # ---- 阶段8: 最终输出 ----
    briefings: Dict[str, Any]                # {category: briefing_text}
    report: str                              # 最终Markdown报告（流式生成）

# Global job status tracker - shared across application.py and backend nodes
job_status = defaultdict[Any, dict[str, str | list[Any] | None]](lambda: {
    "status": "pending",
    "result": None,
    "error": None,
    "debug_info": [],
    "company": None,
    "report": None,
    "last_update": datetime.now().isoformat(),
    "events": []  # Queue for events from parallel nodes
})