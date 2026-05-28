# 公司研究智能体 - 完整工作流详解

## 📋 目录
1. [整体架构](#整体架构)
2. [阶段1: 官网抓取 (Grounding)](#阶段1-官网抓取-grounding)
3. [阶段2: 搜索查询生成 (Query Generation)](#阶段2-搜索查询生成-query-generation)
4. [阶段3: 文档搜集 (Parallel Search)](#阶段3-文档搜集-parallel-search)
5. [阶段4: 数据汇总 (Collection)](#阶段4-数据汇总-collection)
6. [阶段5: 内容筛选 (Curation)](#阶段5-内容筛选-curation)
7. [阶段6: 内容充实 (Enrichment)](#阶段6-内容充实-enrichment)
8. [阶段7: 简报生成 (Briefing)](#阶段7-简报生成-briefing)
9. [阶段8: 报告编译 (Editor)](#阶段8-报告编译-editor)

---

## 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│ 用户输入: 公司名 + 官网URL + 行业 + 总部位置                  │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │  Grounding Node        │  ← 阶段1: 官网抓取
        │  (grounding.py)        │
        └────────┬───────────────┘
                 │ [官网raw_content]
                 ▼
    ┌─────────────────────────────────────────┐
    │ 4个研究节点并行运行                       │  ← 阶段2-3: 搜索+收集
    ├─────────────────────────────────────────┤
    │ ① CompanyAnalyzer  (company.py)        │   生成4条查询
    │    └─ 搜索: 产品、历史、团队、战略       │   ← Tavily搜索
    │                                         │
    │ ② IndustryAnalyzer  (industry.py)      │   生成4条查询
    │    └─ 搜索: 市场、竞争、趋势、挑战      │   ← Tavily搜索
    │                                         │
    │ ③ FinancialAnalyst  (financial.py)     │   生成4条查询
    │    └─ 搜索: 融资、估值、收入、利润      │   ← Tavily搜索
    │                                         │
    │ ④ NewsScanner  (news.py)               │   生成4条查询
    │    └─ 搜索: 公告、合作、奖项、新闻      │   ← Tavily搜索
    └────────┬──────────────────────────────┘
             │ [4类别各多个文档]
             ▼
    ┌────────────────────┐
    │ Collector          │  ← 阶段4: 汇总统计
    │ (collector.py)     │
    └────────┬───────────┘
             │ [统计信息]
             ▼
    ┌────────────────────┐
    │ Curator            │  ← 阶段5: 评分筛选
    │ (curator.py)       │     (Tavily score ≥ 0.4)
    └────────┬───────────┘
             │ [筛选后的文档]
             ▼
    ┌────────────────────┐
    │ Enricher           │  ← 阶段6: 获取完整内容
    │ (enricher.py)      │     (Tavily extract)
    └────────┬───────────┘
             │ [含raw_content的文档]
             ▼
    ┌────────────────────┐
    │ Briefing           │  ← 阶段7: 生成4份简报
    │ (briefing.py)      │     (Azure GPT-4o)
    └────────┬───────────┘
             │ [4个类别的简报]
             ▼
    ┌────────────────────┐
    │ Editor             │  ← 阶段8: 汇编+清理
    │ (editor.py)        │     (Azure GPT-4o)
    └────────┬───────────┘
             │
             ▼
    ┌─────────────────────┐
    │ 最终Markdown报告    │
    │ (PDF生成可选)        │
    └─────────────────────┘
```

---

## 阶段1: 官网抓取 (Grounding)

**文件**: `backend/nodes/grounding.py`  
**服务**: Tavily Web Crawler  
**输入**: 公司URL (可选)  
**输出**: 官网页面的 raw_content

### 工作流程

```python
# 如果用户提供了公司官网URL
if url := state.get('company_url'):
    site_extraction = await tavily_client.crawl(
        url=url,
        instructions="Find any pages that help understand the company's 
                     business, products, services, and relevant information",
        max_depth=1,              # 仅抓取1层深度
        max_breadth=50,           # 最多50个页面
        extract_depth="advanced"  # 获取完整内容
    )
```

### 具体例子 - 男鞋电商网站

**输入URL**: `https://example-men-shoes.com`

**Tavily抓取过程**:
```
1. 访问首页 (https://example-men-shoes.com/)
   └─ 识别链接: /about, /products, /services, /contact
   
2. 抓取关联页面 (max_breadth=50限制):
   ✓ /about           → raw_content: "我们是中国领先的男鞋电商平台，成立于2015年..."
   ✓ /products        → raw_content: "产品分类：跑步鞋、篮球鞋、休闲鞋..."
   ✓ /services        → raw_content: "我们提供: 免费配送、7天退货、专业咨询..."
   ✓ /contact         → raw_content: "服务热线：400-123-456 邮箱: support@..."
   ✓ /company-history → raw_content: "公司历史: 2015年成立，2018年融资500万..."
   
3. 提取raw_content存储为:
```

### 状态更新

```python
state['site_scrape'] = {
    'https://example-men-shoes.com/': {
        'raw_content': '首页内容文本...',
        'source': 'company_website'
    },
    'https://example-men-shoes.com/about': {
        'raw_content': '关于我们页面文本...',
        'source': 'company_website'
    },
    'https://example-men-shoes.com/products': {
        'raw_content': '产品分类和描述...',
        'source': 'company_website'
    }
    # ...共可能50个页面
}
```

### 输出事件

前端收到的事件:
```javascript
{
  "type": "crawl_start",
  "url": "https://example-men-shoes.com",
  "message": "正在抓取官网..."
}
↓
{
  "type": "crawl_success",
  "pages_found": 5,
  "message": "成功抓取5个页面"
}
```

---

## 阶段2: 搜索查询生成 (Query Generation)

**文件**: `backend/nodes/researchers/base.py`  
**服务**: Azure OpenAI GPT-4o  
**输入**: 公司信息 + Prompt模板  
**输出**: 4条搜索查询

### 4个研究节点的Prompt

每个研究节点使用不同的Prompt，指导GPT-4o生成针对性的搜索查询。

#### ① 公司分析器 (CompanyAnalyzer)

**Prompt**:
```
生成关于 {company} 的公司基础信息查询，例如：
- 核心产品和服务
- 公司历史和重要事件
- 领导团队
- 商业模式和战略

重要指南：
- 仅关注 {company} 特定信息
- 查询简洁有力
- 生成确切4条搜索查询（每行一条，无破折号）
```

**具体例子 - 男鞋电商公司**:

如果 company="Example Shoes Inc", industry="在线零售", hq_location="浙江杭州"

GPT-4o 生成:
```
Example Shoes Inc core business products
Example Shoes Inc company history founding
Example Shoes Inc leadership team founders
Example Shoes Inc business model e-commerce
```

**工作流程**:
```python
chain = prompt_template | azure_llm  # LCEL链

async for chunk in chain.astream({
    "company": "Example Shoes Inc",
    "industry": "在线零售",
    "hq_location": "杭州",
    "task_prompt": COMPANY_ANALYZER_QUERY_PROMPT,
    "format_guidelines": "..."
}):
    # 流式接收GPT输出
    current_query += chunk.content
    
    # 按行分割查询
    if '\n' in current_query:
        parts = current_query.split('\n')
        for query in parts[:-1]:
            queries.append(query.strip())
            # 发送query_generated事件给前端
```

#### ② 行业分析器 (IndustryAnalyzer)

**Prompt**:
```
生成关于 {company} 所在 {industry} 行业的查询，例如：
- 市场地位
- 竞争对手
- {industry} 行业趋势和挑战
- 市场规模和增长
```

**例子输出**:
```
online shoe retail market size 2026
shoe e-commerce competitors market share
footwear industry growth trends
shoe retail market challenges opportunities
```

#### ③ 财务分析器 (FinancialAnalyst)

**Prompt**:
```
生成关于 {company} 财务分析的查询，例如：
- 融资历史和估值
- 财务报表和关键指标
- 收入和利润来源
```

**例子输出**:
```
Example Shoes Inc funding rounds investment
Example Shoes Inc revenue financial metrics
Example Shoes Inc company valuation
Example Shoes Inc profit margins earnings
```

#### ④ 新闻扫描器 (NewsScanner)

**Prompt**:
```
生成关于 {company} 最近新闻的查询，例如：
- 最近公司公告
- 新闻稿
- 新的合作伙伴关系
```

**例子输出**:
```
Example Shoes Inc press release 2026
Example Shoes Inc partnership announcement
Example Shoes Inc news latest
Example Shoes Inc awards recognition
```

### 状态更新

```python
state['company_queries'] = [
    'Example Shoes Inc core business products',
    'Example Shoes Inc company history founding',
    'Example Shoes Inc leadership team founders',
    'Example Shoes Inc business model e-commerce'
]

state['industry_queries'] = [
    'online shoe retail market size 2026',
    'shoe e-commerce competitors market share',
    # ...
]

state['financial_queries'] = [...]
state['news_queries'] = [...]
```

### 前端显示

UI中的"Generated Research Queries"展开后显示:
```
┌─ Company Queries
│  • Example Shoes Inc core business products
│  • Example Shoes Inc company history founding
│  • Example Shoes Inc leadership team founders
│  • Example Shoes Inc business model e-commerce
│
├─ Industry Queries
│  • online shoe retail market size 2026
│  • shoe e-commerce competitors market share
│  • ...
│
├─ Financial Queries
│  • ...
│
└─ News Queries
   • ...
```

---

## 阶段3: 文档搜集 (Parallel Search)

**文件**: `backend/nodes/researchers/base.py`  
**服务**: Tavily Search API  
**输入**: 16条搜索查询（4个研究节点 × 4条/节点）  
**输出**: 每个查询对应的搜索结果（文档）

### 并行搜索过程

```python
async def search_documents(self, state, queries):
    search_params = {
        "search_depth": "basic",
        "include_raw_content": False,
        "max_results": 5,          # 每条查询最多5个结果
        "topic": "news"            # 可选: news或finance主题
    }
    
    # 并行执行所有搜索任务
    search_tasks = [
        tavily_client.search(query, **search_params) 
        for query in queries
    ]
    
    results = await asyncio.gather(*search_tasks)  # 并行执行
```

### 具体例子

**搜索查询1**: "Example Shoes Inc core business products"

**Tavily返回**:
```json
{
  "results": [
    {
      "title": "Example Shoes Inc - 官方网站",
      "url": "https://example-shoes.com/products",
      "content": "我们专注于高端男鞋零售，产品包括...",
      "score": 0.92  ← Tavily相关性评分
    },
    {
      "title": "Example Shoes评测 - 产品质量如何？",
      "url": "https://review-site.com/example-shoes",
      "content": "作为消费者，我评测了他们的产品...",
      "score": 0.78
    },
    {
      "title": "男鞋市场新玩家",
      "url": "https://news-site.com/new-players",
      "content": "Example Shoes Inc是最新进入者...",
      "score": 0.65
    },
    # 最多5条结果
  ]
}
```

**搜索查询2**: "online shoe retail market size 2026"

**Tavily返回**:
```json
{
  "results": [
    {
      "title": "全球在线男鞋市场2026年规模预测",
      "url": "https://market-research.com/shoe-market",
      "content": "根据IDC数据，2026年在线男鞋市场...",
      "score": 0.88
    },
    # ...
  ]
}
```

### 文档规范化

```python
def _process_search_result(self, result, query):
    """将Tavily结果转换为标准格式"""
    return {
        "title": result.get("title", ""),
        "content": result.get("content", ""),
        "query": query,                    # 记录是哪个查询找到的
        "url": result.get("url"),
        "source": "web_search",
        "score": result.get("score", 0.0)  # Tavily相关性评分
    }
```

### 最终汇总

```python
merged_docs = {
    'https://example-shoes.com/products': {
        'title': 'Example Shoes Inc - 官方网站',
        'content': '我们专注于高端男鞋零售...',
        'query': 'Example Shoes Inc core business products',
        'url': 'https://example-shoes.com/products',
        'source': 'web_search',
        'score': 0.92
    },
    'https://review-site.com/example-shoes': {
        'title': 'Example Shoes评测 - 产品质量如何？',
        'content': '作为消费者，我评测了他们的产品...',
        'score': 0.78
    },
    # ... 共可能80条文档 (16条查询 × 5条/查询)
}

state['company_data'] = merged_docs['company相关的文档']
state['industry_data'] = merged_docs['industry相关的文档']
state['financial_data'] = merged_docs['financial相关的文档']
state['news_data'] = merged_docs['news相关的文档']
```

### 前端显示事件

```javascript
{
  "type": "search_started",
  "total_queries": 16,
  "message": "搜索16条查询..."
}
↓
{
  "type": "search_complete",
  "total_documents": 73,
  "queries_processed": 16,
  "message": "找到73个文档"
}
```

---

## 阶段4: 数据汇总 (Collection)

**文件**: `backend/nodes/collector.py`  
**输入**: 4类别的文档集合  
**输出**: 统计摘要

### 工作流程

```python
async def collect(self, state):
    msg = []
    research_types = {
        'financial_data': '💰 Financial',
        'news_data': '📰 News',
        'industry_data': '🏭 Industry',
        'company_data': '🏢 Company'
    }
    
    for data_field, label in research_types.items():
        data = state.get(data_field, {})
        doc_count = len(data)
        msg.append(f"• {label}: {doc_count} 个文档收集完成")
```

### 输出例子

```
📦 为 Example Shoes Inc 收集研究数据：
• 💰 Financial: 18 个文档收集完成
• 📰 News: 22 个文档收集完成
• 🏭 Industry: 19 个文档收集完成
• 🏢 Company: 14 个文档收集完成
```

### 实际意义

这个阶段只是一个"断点"，用来：
1. 检查所有文档是否正确收集
2. 为用户显示进度统计
3. 为下一阶段（Curator）准备数据

---

## 阶段5: 内容筛选 (Curation)

**文件**: `backend/nodes/curator.py`  
**服务**: 纯逻辑（使用Tavily评分）  
**输入**: 73个文档  
**输出**: 筛选后的文档（≥0.4分 或 官网来源）

### 相关性评分规则

```python
def evaluate_documents(self, docs):
    """基于Tavily评分筛选文档"""
    evaluated_docs = []
    
    for doc in docs:
        tavily_score = float(doc.get('score', 0))
        is_company_website = doc.get('source') == 'company_website'
        
        # 两个条件任选其一
        if tavily_score >= 0.4 or is_company_website:
            evaluated_docs.append({
                **doc,
                "evaluation": {
                    "overall_score": tavily_score,
                    "reason": "company_website" if is_company_website else f"score_{tavily_score:.2f}"
                }
            })
```

### 男鞋网站的具体筛选例子

**输入文档 (样本)**:

```
1. 官方网站 - "Example Shoes产品系列"
   score: 0.15 (低分但官网来源)
   Decision: ✅ 保留 (source='company_website')

2. 专业评测 - "2026年最佳男鞋评测"
   score: 0.87 (高相关性)
   Decision: ✅ 保留 (score ≥ 0.4)

3. 财经新闻 - "Example Shoes融资1000万"
   score: 0.76 (高相关性)
   Decision: ✅ 保留 (score ≥ 0.4)

4. 随机页面 - "男鞋品牌大全"
   score: 0.22 (低相关性，不是官网)
   Decision: ❌ 舍弃 (score < 0.4)

5. 竞争对手页面 - "Nike vs 其他品牌"
   score: 0.35 (接近阈值但未达到，不是官网)
   Decision: ❌ 舍弃 (score < 0.4 且非官网)

6. 行业报告 - "2026男鞋零售市场趋势"
   score: 0.68 (高相关性)
   Decision: ✅ 保留 (score ≥ 0.4)
```

### 筛选结果

```python
state['curated_company_data'] = {
    # 18 → 12 个文档保留
}

state['curated_financial_data'] = {
    # 22 → 18 个文档保留
}

state['curated_industry_data'] = {
    # 19 → 14 个文档保留
}

state['curated_news_data'] = {
    # 14 → 11 个文档保留
}

# 总计: 73 → 55 个文档保留 (75%通过率)
```

### 分类统计输出

```
🔍 为 Example Shoes Inc 筛选研究数据
💰 Financial: 找到22个文档
  ✓ 保留18个相关文档
📰 News: 找到14个文档
  ✓ 保留11个相关文档
🏭 Industry: 找到19个文档
  ✓ 保留14个相关文档
🏢 Company: 找到18个文档
  ✓ 保留12个相关文档
```

---

## 阶段6: 内容充实 (Enrichment)

**文件**: `backend/nodes/enricher.py`  
**服务**: Tavily Extract API  
**输入**: 55个筛选后的文档 (仅有URL和摘要)  
**输出**: 55个文档的完整 raw_content

### 工作流程

```python
async def fetch_raw_content(self, urls):
    """并行获取所有URL的完整内容"""
    
    # 分批处理 (每批20个)
    batches = [urls[i:i+20] for i in range(0, len(urls), 20)]
    
    # 每批最多3个并发
    semaphore = asyncio.Semaphore(3)
    
    async def process_batch(batch_urls):
        async with semaphore:
            tasks = [
                tavily_client.extract(url) 
                for url in batch_urls
            ]
            results = await asyncio.gather(*tasks)
            return results
    
    # 执行所有批次
    all_results = await asyncio.gather(
        *[process_batch(batch) for batch in batches]
    )
```

### 具体例子

**输入** (来自Stage 5):
```python
curated_company_data = {
    'https://example-shoes.com/products': {
        'title': 'Example Shoes 产品系列',
        'content': '我们提供多种男鞋...',  # 摘要 (200字)
        'score': 0.92
        # 注意: 这里没有 raw_content
    }
}
```

**Tavily Extract处理**:
```
for url in ['https://example-shoes.com/products', ...]:
    result = await tavily_client.extract(url)
    # 返回完整的页面内容
```

**输出** (Stage 6后):
```python
curated_company_data = {
    'https://example-shoes.com/products': {
        'title': 'Example Shoes 产品系列',
        'content': '...',
        'score': 0.92,
        'raw_content': '''
        首页: Example Shoes 男鞋专家
        
        ### 产品分类
        1. 跑步鞋
           - 缓震技术: 采用顶级缓震材料
           - 材质: 进口透气网面
           - 价格: 399-899元
        
        2. 篮球鞋
           - 支撑强度: 高支撑
           - 防滑底: 专业防滑设计
           - 价格: 599-1299元
        
        ### 公司简介
        Example Shoes Inc成立于2015年，总部位于杭州。我们是中国领先的
        在线男鞋零售商，专注于为消费者提供高质量、高性价比的男鞋产品。
        
        ### 服务优势
        - 免费配送 (满99元)
        - 7天无理由退货
        - 专业鞋类顾问咨询
        - 官方授权品牌
        
        ### 联系方式
        服务热线: 400-123-456
        工作时间: 09:00-18:00
        '''  # 完整内容 (3000字+)
    }
}
```

### 处理统计

```
📚 为 Example Shoes Inc 充实已筛选的数据:
• 充实 12 个公司文档...
  ✓ 已获取完整内容 12/12
• 充实 18 个财务文档...
  ✓ 已获取完整内容 18/18
• 充实 14 个行业文档...
  ✓ 已获取完整内容 14/14
• 充实 11 个新闻文档...
  ✓ 已获取完整内容 11/11
```

---

## 阶段7: 简报生成 (Briefing)

**文件**: `backend/nodes/briefing.py`  
**服务**: Azure OpenAI GPT-4o  
**输入**: 55个充实后的文档 (含raw_content)  
**输出**: 4份简报 (Company/Industry/Financial/News)

### 工作流程

对于每个类别（Company/Industry/Financial/News），执行：

```python
async def generate_category_briefing(self, docs, category, context):
    """生成特定类别的简报"""
    
    # 准备文档
    prepared_docs = self._prepare_documents(docs)
    
    # 调用GPT-4o
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert researcher..."),
        ("user", f"Generate a {category} briefing based on:\n{prepared_docs}")
    ])
    
    chain = prompt | azure_llm
    
    # 流式输出
    async for chunk in chain.astream(input_data):
        yield chunk  # 实时流给前端
    
    # 存储完整简报
    state[f'{category}_briefing'] = full_response
```

### 4份简报详解

#### **① 公司简报** (company_briefing)

**Prompt**:
```
创建 Example Shoes Inc（在线零售公司，位于杭州）的聚焦且全面的公司简报

结构：
### Core Product/Service
* 列举不同产品/功能
* 仅包含已验证的技术能力

### Leadership Team
* 列举关键领导
* 包含职位和专长

### Target Market
* 列举特定目标受众
* 列举已验证的使用案例
* 列举已确认的客户/合作伙伴

### Key Differentiators
* 列举独特特性
* 列举已证明的优势

### Business Model
* 讨论产品/服务定价
* 列举分销渠道

重要：仅用bullet点，不要提及"找不到信息"
```

**GPT-4o输出例子**:
```markdown
### Core Product/Service
* 男鞋零售平台 - 提供500+款男鞋SKU
* 自有品牌系列 - 专业运动鞋和休闲鞋
* 电商平台 - Web和移动应用（iOS/Android）
* 物流配送 - 自建物流体系

### Leadership Team
* 张三 - CEO兼创始人（前Amazon物流经理）
* 李四 - COO（前沃尔玛供应链负责人）
* 王五 - 产品总监（Google产品经理出身）

### Target Market
* 一二线城市25-45岁男性消费者
* 使用案例：日常运动、职业工作、休闲生活
* 客户包括：企业团购、体育队、运动俱乐部

### Key Differentiators
* 价格优势 - 比竞争对手平均便宜15%
* 品质保证 - 100%正品承诺
* 服务速度 - 浙江地区24小时配送

### Business Model
* 产品定价：399-1299元不等
* 利润空间：20-30%毛利率
* 分销渠道：直营电商、线下加盟店、B2B企业采购
```

#### **② 行业简报** (industry_briefing)

**Prompt**:
```
为 Example Shoes Inc 创建所在行业的聚焦且全面的行业简报

结构：
### Market Overview
* Example Shoes Inc 的确切市场细分
* 市场规模（含年份）
* 增长率

### Direct Competition
* 命名的直接竞争对手
* 具体竞争产品
* 市场地位

### Competitive Advantages
* 独特的技术特性
* 已证明的优势

### Market Challenges
* 特定的已验证挑战
```

**GPT-4o输出例子**:
```markdown
### Market Overview
* 市场细分：中国在线男鞋零售市场
* 市场规模：2026年估计达500亿元
* 增长率：年均增长18%（2020-2026）

### Direct Competition
* Nike官方商城 - 全球领先运动品牌
* 李宁官方旗舰店 - 本土头部品牌
* 虎扑运动 - 细分品类垂直平台
* 抖音小店 - 社交电商新玩家

### Competitive Advantages
* 本土化优势：快速响应中国市场
* 价格优势：中端品牌更好的性价比
* 物流优势：浙江地理位置优势

### Market Challenges
* 品牌认知度低 - 与Nike、李宁有巨大差距
* 供应链复杂 - 供应商管理难度大
* 售后体系不完善 - 线下门店覆盖有限
* 社交电商冲击 - 来自TikTok、小红书的竞争
```

#### **③ 财务简报** (financial_briefing)

**Prompt**:
```
为 Example Shoes Inc 创建聚焦且全面的财务简报

结构：
### Funding & Investment
* 总融资额（含日期）
* 每轮融资（含日期）
* 命名的投资者

### Revenue Model
* 产品/服务定价

重要：包含具体数字，不要范围数值
```

**GPT-4o输出例子**:
```markdown
### Funding & Investment
* 总融资额：1800万美元
* A轮融资：2018年5月，500万美元（红杉资本领投）
* B轮融资：2020年3月，800万美元（老虎基金、红杉资本跟投）
* C轮融资：2022年9月，500万美元（高瓴资本）
* 投资者：红杉资本、老虎基金、高瓴资本、真格基金

### Revenue Model
* 产品定价：399-899元（跑步鞋）、599-1299元（篮球鞋）
* 毛利率：25-30%
* 主要收入来源：电商直营（70%）、加盟门店（20%）、B2B批发（10%）
```

#### **④ 新闻简报** (news_briefing)

**Prompt**:
```
为 Example Shoes Inc 创建聚焦且全面的新闻简报

结构（不使用###标题）：
### Major Announcements
* 产品/服务发布
* 新举措

### Partnerships
* 整合
* 合作

### Recognition
* 奖项
* 新闻报道

排序：最新→最旧
```

**GPT-4o输出例子**:
```markdown
### Major Announcements
* 2026年5月：推出新品系列"耐久跑"，采用新型缓震材料
* 2026年3月：正式宣布冲刺IPO，目标融资2亿美元
* 2025年11月：官方应用突破100万下载量

### Partnerships
* 与抖音电商达成独家合作，推出限量联名款
* 与运动科学研究所合作开发新产品
* 与国家体育总局建立赞助关系

### Recognition
* 获得2026年"中国优秀电商品牌"奖
* 入选"福布斯中国创业30U30"
* 被评为"年度最具创新零售企业"
```

### 前端显示

用户可以在UI的"Curation/Extraction"部分展开查看4份简报，每份都在实时流式输出。

---

## 阶段8: 报告编译 (Editor)

**文件**: `backend/nodes/editor.py`  
**服务**: Azure OpenAI GPT-4o (2阶段编辑)  
**输入**: 4份简报 (Company/Industry/Financial/News)  
**输出**: 最终Markdown报告

### 工作流程

#### **第1阶段：内容汇编 (Compile)**

**Prompt**:
```
你是专业的研究报告编辑。正在汇编关于 Example Shoes Inc 的综合研究报告。

已有的简报：
{company_briefing}
{industry_briefing}
{financial_briefing}
{news_briefing}

创建关于 Example Shoes Inc（在线零售公司，杭州）的深入、综合、详尽的报告，
该报告：

1. 将所有部分的信息整合为连贯的叙述（非简单拼接）
2. 保留每个部分的重要细节
3. 逻辑组织信息，移除过渡性评论
4. 使用清晰的部分标题和结构

返回格式 (严格遵循):

# Example Shoes Inc Research Report

## Company Overview
### Core Product/Service
...

### Leadership Team
...

## Industry Overview
### Market Overview
...

## Financial Overview
### Funding & Investment
...

## News
* 产品公告
* 合作事项
* 获奖情况

返回干净的markdown格式。不要解释或评论。
```

**GPT-4o第1阶段输出** (样本):
```markdown
# Example Shoes Inc Research Report

## Company Overview

Example Shoes Inc 是一家专注于男鞋零售的在线电商平台，成立于2015年，
总部位于浙江杭州。公司致力于为城市男性消费者提供高质量、高性价比的
男鞋产品，包括运动鞋、篮球鞋和休闲鞋等多个品类。

### Core Product/Service
* 男鞋零售平台 - 提供500+款男鞋SKU
* 自有品牌系列 - 专业运动鞋和休闲鞋
* 电商平台 - Web和移动应用（iOS/Android）
* 物流配送 - 自建物流体系

### Leadership Team
* 张三 - CEO兼创始人（前Amazon物流经理）
* 李四 - COO（前沃尔玛供应链负责人）
* 王五 - 产品总监（Google产品经理出身）

### Target Market
* 一二线城市25-45岁男性消费者
* 使用案例：日常运动、职业工作、休闲生活

### Key Differentiators
* 价格优势 - 比竞争对手平均便宜15%
* 品质保证 - 100%正品承诺
* 服务速度 - 浙江地区24小时配送

### Business Model
* 产品定价：399-1299元不等
* 分销渠道：直营电商、线下加盟店、B2B企业采购

## Industry Overview

中国在线男鞋零售市场正处于高速增长期，2026年市场规模估计达500亿元，
年均增长率为18%。该领域竞争激烈，包括全球领先品牌（Nike）、本土头部
品牌（李宁）以及新兴平台（虎扑、抖音小店）等多个参与者。

### Market Overview
* 市场细分：中国在线男鞋零售市场
* 市场规模：2026年估计达500亿元
* 增长率：年均增长18%（2020-2026）

### Direct Competition
* Nike官方商城 - 全球领先运动品牌
* 李宁官方旗舰店 - 本土头部品牌
* 虎扑运动 - 细分品类垂直平台
* 抖音小店 - 社交电商新玩家

### Competitive Advantages
* 本土化优势：快速响应中国市场
* 价格优势：中端品牌更好的性价比
* 物流优势：浙江地理位置优势

### Market Challenges
* 品牌认知度低
* 供应链管理复杂
* 售后体系不完善
* 社交电商冲击

## Financial Overview

### Funding & Investment
* 总融资额：1800万美元
* A轮融资：2018年5月，500万美元（红杉资本领投）
* B轮融资：2020年3月，800万美元（老虎基金、红杉资本跟投）
* C轮融资：2022年9月，500万美元（高瓴资本）

### Revenue Model
* 产品定价：399-1299元不等
* 毛利率：25-30%
* 主要收入来源：电商直营（70%）、加盟门店（20%）、B2B批发（10%）

## News

* 2026年5月：推出新品系列"耐久跑"，采用新型缓震材料
* 2026年3月：正式宣布冲刺IPO，目标融资2亿美元
* 与抖音电商达成独家合作
* 获得"中国优秀电商品牌"奖

## References

[Reference 1] 来源1...
[Reference 2] 来源2...
```

#### **第2阶段：内容清理 (Content Sweep)**

**Prompt**:
```
你是markdown格式专家。给定一份关于 Example Shoes Inc 的报告。

当前报告：
{content}

执行以下操作：
1. 删除冗余/重复信息
2. 删除与公司无关的信息
3. 删除内容不足的部分
4. 删除元评论（如"以下是新闻..."）

严格执行此文档结构：

# Example Shoes Inc Research Report

## Company Overview
[含### 小节]

## Industry Overview
[含### 小节]

## Financial Overview
[含### 小节]

## News
[仅bullet点 *，不使用###]

## References
[MLA格式，原样保留]

关键规则：
1. 文档必须以"# {company} Research Report"开头
2. 仅使用这些## 标题，按此顺序
3. 仅在Company/Industry/Financial中使用### 小节
4. News section 仅使用bullet点
5. 不要修改References格式
6. 不要使用代码块 (```)
7. 最多一个空行在部分之间

返回打磨后的报告。不要解释。
```

**GPT-4o第2阶段输出** (最终):
```markdown
# Example Shoes Inc Research Report

## Company Overview

Example Shoes Inc是一家专注于男鞋零售的在线电商平台，成立于2015年，
总部位于浙江杭州。

### Core Product/Service
* 男鞋零售平台 - 提供500+款男鞋SKU
* 自有品牌系列 - 专业运动鞋和休闲鞋
* 电商平台 - Web和移动应用
* 自建物流配送体系

### Leadership
* 张三 - CEO兼创始人（前Amazon物流经理）
* 李四 - COO（前沃尔玛供应链负责人）
* 王五 - 产品总监（Google产品经理出身）

### Business Model
* 定价：399-1299元
* 渠道：直营电商（70%）、加盟门店（20%）、B2B批发（10%）
* 毛利率：25-30%

## Industry Overview

中国在线男鞋零售市场正处于高速增长期，2026年市场规模预计500亿元，
年均增长率18%。

### Market Size
* 2026年市场规模：500亿元
* 增长率：18%年均增长（2020-2026）

### Competition
* Nike官方商城 - 全球领先
* 李宁官方旗舰店 - 本土头部
* 虎扑运动 - 垂直平台
* 抖音小店 - 社交电商

### Challenges
* 品牌认知度低
* 供应链管理复杂
* 售后体系不完善
* 社交电商竞争

## Financial Overview

### Funding History
* 总融资：1800万美元
* A轮（2018年5月）：500万美元 - 红杉资本领投
* B轮（2020年3月）：800万美元 - 老虎基金、红杉资本
* C轮（2022年9月）：500万美元 - 高瓴资本

### Revenue
* 主要产品定价：399-1299元
* 毛利率：25-30%

## News

* 2026年5月：推出新品系列"耐久跑"
* 2026年3月：宣布冲刺IPO，融资目标2亿美元
* 与抖音电商达成独家合作
* 获得"中国优秀电商品牌"奖

## References

[1] Tavily Search Result. "Example Shoes Market Analysis". https://example.com/report1

[2] Company Official Website. "About Example Shoes Inc". https://example-shoes.com/about

[3] Industry Report. "China Footwear Market 2026". https://market-research.com/report
```

### 前端最终展示

用户在UI看到最终报告，可以：
- 复制全部内容
- 下载为PDF
- 分享链接

---

## 📊 完整流程时间线

```
┌─ T0: 用户提交请求
│  输入: Company="Example Shoes Inc", URL="https://example-shoes.com", 
│        Industry="Online Retail", HQ="Hangzhou"
│
├─ T1: 阶段1 - 官网抓取 (1-2秒)
│  └─ 完成: 抓取5个官网页面
│
├─ T2: 阶段2 - 查询生成 (3-5秒)
│  └─ 完成: 生成16条搜索查询
│
├─ T3: 阶段3 - 文档搜集 (8-12秒)
│  └─ 完成: 收集73个文档
│
├─ T4: 阶段4 - 数据汇总 (1秒)
│  └─ 完成: 统计4类别文档
│
├─ T5: 阶段5 - 内容筛选 (2秒)
│  └─ 完成: 73 → 55个文档
│
├─ T6: 阶段6 - 内容充实 (15-20秒)
│  └─ 完成: 获取所有文档完整内容
│
├─ T7: 阶段7 - 简报生成 (30-40秒)
│  └─ 完成: 生成4份简报（流式输出）
│
├─ T8: 阶段8 - 报告编译 (20-30秒)
│  └─ 完成: 最终Markdown报告（流式输出）
│
└─ T9: 完成！(总耗时: 80-110秒)
```

---

## 🔑 关键数据流

```
官网页面 (5个)
    ↓ [raw_content]
    ↓
[Stage 1] 
    ↓
16条搜索查询
    ↓ [并行执行Tavily搜索]
    ↓
73个文档 (含score, content)
    ↓ [按score≥0.4 或 官网来源筛选]
    ↓
55个文档
    ↓ [Tavily extract获取完整内容]
    ↓
55个文档 (含raw_content)
    ↓ [按类别分组]
    ↓
4个类别的充实文档集合
    ↓ [Azure GPT-4o生成4份简报]
    ↓
4份简报 (Company/Industry/Financial/News)
    ↓ [Azure GPT-4o汇编+清理]
    ↓
最终Markdown报告
```

---

## ✅ 总结

该智能体通过以下步骤自动化公司研究报告生成：

1. **Grounding** - 快速获取官网基础信息
2. **Query Generation** - 用LLM生成针对性搜索查询
3. **Parallel Search** - 并行执行Tavily搜索，高效收集信息
4. **Collection** - 汇总统计所有数据
5. **Curation** - 基于Tavily评分（≥0.4）智能筛选内容
6. **Enrichment** - 获取所有筛选文档的完整内容
7. **Briefing** - 用LLM为4个类别生成结构化简报
8. **Editor** - 用LLM汇编简报为最终专业报告

整个流程充分利用了：
- **LLM能力** (Azure GPT-4o) - 生成查询、简报、报告
- **搜索能力** (Tavily API) - 信息收集和评分
- **异步并行** (asyncio) - 高效处理多任务
- **流式输出** (SSE) - 实时用户反馈

最终产出一份结构清晰、信息完整、格式规范的Markdown公司研究报告。
