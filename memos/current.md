# 当前工作备忘

> 最后更新：2025-01

## 当前重点

- Prompt 工程迭代：优化报告输出质量
- 合作机会分析需要更精准的匹配逻辑
- 社交媒体简报内容获取改进

## 近期完成

- ✅ seller_profile.py 抽离，所有 prompt 统一引用
- ✅ Enricher 性能优化（15s 超时、阈值 2、路径粒度、403 跳过）
- ✅ 推广分析从 briefing 移到 editor（避免简报阶段幻觉）
- ✅ DomainCircuitBreaker 路径粒度优化（跳过 locale 段）
- ✅ f-string 模板转义问题修复

## 正在进行

- 🟡 报告质量持续评估（不同行业目标公司测试）
- 🟡 社交媒体 include_raw_content 效果验证

## 待解决

- 💭 部分目标公司首页动态渲染抓不到内容（Grounding 阶段）
- 💭 Tavily extract 对某些网站失效率高
- 💭 PDF 中文字体渲染在某些系统上有问题
