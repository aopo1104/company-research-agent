"""
================================================================================
company.py - 公司分析节点 (Stage 2-3: 公司信息研究)
================================================================================
从官网和网络搜索收集关于目标公司的详细信息

功能流程:
  1. 生成4条公司相关查询 (使用Azure GPT-4o)
  2. 从官网数据开始 (Stage 1已爬取)
  3. 执行Tavily并行搜索 (最多20个文档)
  4. 合并官网 + 搜索结果
  5. 输出 company_data 到 state

搜索焦点:
  - 核心产品/服务、目标市场
  - 企业性质（制造商/分销商/品牌）
  - 自产能力、工厂信息
  - 销售渠道、中国采购记录
  - 公司背景、最新动态

数据流:
  Input: company, industry, hq_location (从用户输入)
  Process: QueryGen → ParallelSearch → Merge
  Output: company_data = {url → {title, content, score, source}}
"""

from typing import Any

from langchain_core.messages import AIMessage

from ...classes import ResearchState
from ...prompts import COMPANY_ANALYZER_QUERY_PROMPT
from .base import BaseResearcher


class CompanyAnalyzer(BaseResearcher):
    """公司分析器 - 收集公司基本信息、产品、销售渠道等"""
    
    def __init__(self) -> None:
        """初始化公司分析器"""
        super().__init__()
        self.analyst_type = "company_analyzer"

    async def analyze(self, state: ResearchState):
        """执行公司分析主流程
        
        步骤:
          1️⃣ 生成查询: Azure GPT-4o生成4条针对性查询
                    (产品/服务、企业性质、销售渠道、中国采购等)
          2️⃣ 准备数据: 从 site_scrape 获取官网爬取的初始数据
          3️⃣ 执行搜索: 用Tavily并行搜索4条查询 (共~20个文档)
          4️⃣ 合并数据: 官网数据 + 搜索结果
          5️⃣ 保存结果: 设置 state['company_data']
          6️⃣ 发送事件: 实时推送进度到前端
        
        Args:
            state: 工作流状态，包含company/industry/hq_location
            
        Yields:
            事件对象: query_generating, query_generated, search_started, search_complete, analysis_complete
        """
        company = state.get('company', 'Unknown Company')
        
        # ========== 第1步: 生成查询 ==========
        # 使用 COMPANY_ANALYZER_QUERY_PROMPT 生成4条查询
        # 这些查询涵盖: 产品信息、企业性质、销售渠道、中国采购等
        queries = []
        async for event in self.generate_queries(state, COMPANY_ANALYZER_QUERY_PROMPT):
            yield event
            if event.get("type") == "queries_complete":
                queries = event.get("queries", [])
        
        # ========== 第2步: 记录生成的查询 ==========
        # 向用户/日志显示生成了哪些查询
        subqueries_msg = "🔍 Subqueries for company analysis:\n" + "\n".join([f"• {query}" for query in queries])
        state.setdefault('messages', []).append(AIMessage(content=subqueries_msg))
        
        # ========== 第3步: 准备初始数据 ==========
        # 从 Stage 1 (grounding) 中获取已爬取的官网数据
        # site_scrape = {url → {raw_content, source, method, title}}
        company_data = dict[str, Any](state.get('site_scrape', {}))
        
        # ========== 第4步: 执行并行搜索 ==========
        # 使用 Tavily 搜索4条查询
        # 每条查询返回~5个结果，共~20个文档
        # base.py 中 search_documents() 处理并行搜索和聚合
        documents = {}
        async for event in self.search_documents(state, queries):
            yield event
            if event.get("type") == "search_complete":
                documents = event.get("merged_docs", {})
        
        # ========== 第5步: 合并数据 ==========
        # 官网数据 + Tavily搜索结果
        # 注意: 如果同URL出现在两处，搜索结果会覆盖官网数据
        company_data.update(documents)
        
        # ========== 第6步: 更新 state ==========
        # 保存最终结果到 state['company_data']
        # 这个数据将被传递给 Stage 5 (curator) 进行筛选和去重
        completion_msg = f"🏢 Company Analyzer found {len(company_data)} documents for {company}"
        state.setdefault('messages', []).append(AIMessage(content=completion_msg))
        state['company_data'] = company_data
        
        # ========== 第7步: 发送完成事件 ==========
        # 告知下游节点数据已准备好
        yield {"type": "analysis_complete", "data_type": "company_data", "count": len(company_data)}
        yield {'message': [completion_msg], 'company_data': company_data}

    async def run(self, state: ResearchState):
        """运行公司分析 (LangGraph 入口)
        
        这是 LangGraph 调用的主入口，负责:
          - 遍历所有分析事件并转发
          - 收集最终结果
          - 确保 state 正确更新
        
        Args:
            state: 工作流状态
            
        Yields:
            所有来自 analyze() 的事件 + 最终结果
        """
        result = None
        async for event in self.analyze(state):
            yield event
            # 捕获包含最终结果的事件
            if "message" in event or "company_data" in event:
                result = event
        yield result or {} 