# TODO 清单

## 高优先级

- [ ] 添加 prompt 渲染单元测试（防止 f-string 转义遗漏）
- [ ] Grounding 阶段对 SPA 网站的 fallback 方案
- [ ] 报告输出质量评估框架（自动打分）

## 中优先级

- [ ] GitHub Actions CI 配置（lint + import 检查）
- [ ] scrape_engine 单元测试
- [ ] API 集成测试（mock LLM 响应）
- [ ] PDF 中文字体兼容性修复
- [ ] 社交媒体研究节点效果评估

## 低优先级

- [ ] 多语言报告支持优化（当前 /translate 端点）
- [ ] 研究历史记录 UI（MongoDB 已存储）
- [ ] 批量研究功能（一次输入多个公司 URL）
- [ ] 管道执行时间可视化（各阶段耗时 dashboard）
- [ ] Prompt 版本管理（记录修改历史与效果对比）

## 技术债

- [ ] `backend/prompts.py` 仅做 re-export，考虑废弃，直接从 `prompt_templates/` 导入
- [ ] `job_status` 全局 dict 无清理机制，长期运行会内存泄漏
- [ ] 前端 App.tsx 状态逻辑过重，考虑拆分 hooks
- [ ] requirements.txt 未 pin 版本号
