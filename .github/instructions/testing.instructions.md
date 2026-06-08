---
applyTo: "tests/**,*_test.py,test_*"
---

# 测试规则

## 当前状态

> ⚠️ 项目当前没有自动化测试。以下为未来添加测试时的规范。

## 框架选择

- 单元测试：pytest + pytest-asyncio
- HTTP 测试：httpx AsyncClient (TestClient)
- Mock：unittest.mock / pytest-mock

## 测试策略

| 层 | 测试方式 |
|---|---|
| Prompt 模板 | 断言 f-string 渲染结果包含期望内容，无未替换 `{var}` |
| 爬虫 | Mock httpx response，验证 fallback 策略 |
| 熔断器 | 单测 DomainCircuitBreaker 状态转换 |
| API 端点 | httpx AsyncClient，mock LangGraph 调用 |
| LLM 节点 | Mock ChatOpenAI，验证结构化输出解析 |

## TODO

- [ ] 添加 prompt 渲染测试（防止遗漏 `{{` 转义）
- [ ] 添加 scrape_engine 单元测试
- [ ] 添加 API 集成测试
- [ ] CI 配置 (GitHub Actions)
