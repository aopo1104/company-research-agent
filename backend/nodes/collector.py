"""
================================================================================
collector.py - 数据汇总阶段 (Stage 4)
================================================================================
统计4个研究类别收集的文档数量，为后续筛选准备数据

输入: company_data, industry_data, financial_data, news_data
      (来自4个并行研究节点)
输出: (同上) + 汇总统计消息

功能:
  1. 检查所有4个类别的数据是否存在
  2. 计数每个类别的文档数
  3. 生成统计消息，推送给前端

这是一个"断点"节点，主要用于:
  - 进度确认 (用户看到数据收集完成)
  - 错误检测 (发现哪个类别数据为空)
  - 日志记录 (统计信息)

典型输出:
  📦 为 Example Shoes Inc 收集研究数据:
  💰 Financial: 18 个文档
  📰 News: 22 个文档
  🏭 Industry: 19 个文档
  🏢 Company: 14 个文档
  ─────────────────────
  📊 总计: 73 个文档
"""

from langchain_core.messages import AIMessage

from ..classes import ResearchState


class Collector:
    """数据收集器 - 统计和汇总各类别的文档"""

    async def collect(self, state: ResearchState) -> ResearchState:
        """统计所有研究数据
        
        检查项:
          - financial_data: 财务相关文档
          - news_data: 新闻相关文档
          - industry_data: 行业相关文档
          - company_data: 公司相关文档
        
        Args:
            state: 工作流状态
            
        Returns:
            更新后的状态 (添加统计消息)
        """
        company = state.get('company', 'Unknown Company')
        msg = [f"📦 Collecting research data for {company}:"]
        
        # 检查各类别数据
        research_types = {
            'financial_data': '💰 Financial',
            'news_data': '📰 News',
            'industry_data': '🏭 Industry',
            'company_data': '🏢 Company'
        }
        
        for data_field, label in research_types.items():
            data = state.get(data_field, {})
            if data:
                msg.append(f"• {label}: {len(data)} documents collected")
            else:
                msg.append(f"• {label}: No data found")
        
        # 更新状态消息
        state.setdefault('messages', []).append(AIMessage(content="\n".join(msg)))
        
        return state

    async def run(self, state: ResearchState) -> ResearchState:
        """运行收集任务"""
        return await self.collect(state)
