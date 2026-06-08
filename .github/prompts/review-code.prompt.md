---
description: "审查代码变更"
---

# 代码审查

## 审查目标

**文件/PR**：{{target}}

## 审查要点

### 安全性
- 是否有硬编码的密钥或 API key？
- 用户输入是否做了验证？
- httpx 请求是否设置了合理的 timeout？

### Prompt 工程
- 是否从 `seller_profile.py` 引用公司信息（而非硬编码）？
- f-string 中 `{company}` 等模板变量是否双转义为 `{{company}}`？
- briefing prompt 是否包含不该有的推理指令？（推广分析只在 editor）

### 性能
- enricher 中的 HTTP 请求是否有超时保护？
- 是否引入了不必要的串行等待？
- 大列表处理是否使用了 `asyncio.gather`？

### 兼容性
- SSE 事件格式是否保持不变？
- `ResearchState` 字段名是否变动？（会影响前端）
- 新增依赖是否已添加到 `requirements.txt`？

## 输出格式

按严重程度列出问题：🔴 必须修复 / 🟡 建议改进 / 🟢 无问题
