# 架构决策记录

## D001: seller_profile.py 集中管理委托方信息

**日期**：2025-01  
**状态**：已实施  
**背景**：乐歌公司信息散落在各个 prompt 文件中，切换委托方需要改多处。  
**决策**：新建 `backend/prompt_templates/seller_profile.py`，所有 prompt 文件通过 import 引用。  
**影响**：切换客户只需修改一个文件；prompt 文件改用 f-string。  

---

## D002: 推广分析仅在 Editor 阶段生成

**日期**：2025-01  
**状态**：已实施  
**背景**：Briefing 阶段的 prompt 如果包含"推广机会分析"引导，LLM 会在缺乏综合信息时编造内容。  
**决策**：Briefing 只做信息提取（严禁推测），推广/合作分析放在 Editor 编译阶段，由 LLM 综合 5 份简报后统一生成。  
**影响**：报告质量提升，减少幻觉；Editor prompt 中新增专门章节引导。  

---

## D003: DomainCircuitBreaker 路径粒度设计

**日期**：2025-01  
**状态**：已实施  
**背景**：按 domain 整体熔断粒度太粗（一个路径失败导致整站不可访问），按完整路径粒度太细（无法阻止同类请求）。  
**决策**：按 `domain + 首个有意义路径段` 分组，跳过 locale 段（nl/be/en/fr/de/es 等）。  
**示例**：`www.bol.com/nl/nl/p/desk/123` → key = `www.bol.com/p`  
**影响**：同类产品页熔断后不再尝试，不影响其他路径。  

---

## D004: Enricher 超时与跳过策略

**日期**：2025-01  
**状态**：已实施  
**背景**：Enricher 是管道最慢阶段（30-60s），部分网站超时或 403 浪费大量时间。  
**决策**：  
- Tavily extract 超时 15s（asyncio.wait_for）
- 熔断阈值 failure_threshold=2
- 403/401 不走 enhanced-static 重试  
**影响**：Enricher 阶段平均耗时减少约 30%。  

---

## D005: 不引入 Playwright/Selenium

**日期**：2025-01  
**状态**：决定不做  
**背景**：部分 SPA 网站 httpx 抓不到内容。  
**决策**：暂不引入浏览器自动化，因为：1）部署复杂度大增；2）速度慢；3）Tavily extract 已能覆盖大部分场景。  
**后续**：如果 Grounding 失败率过高，再评估引入无头浏览器。  
