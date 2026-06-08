---
description: "安全重构代码"
---

# 安全重构

## 重构目标

**范围**：{{scope}}
**目的**：{{goal}}

## 安全原则

1. **不改变外部行为**：API 接口、SSE 事件格式、State 字段名不变
2. **渐进式**：每次只改一个文件/一个函数，验证后再继续
3. **保留功能**：不删除看似无用的代码，先确认其用途

## 重构检查清单

### 移动代码
- [ ] 更新所有 import 路径
- [ ] 确认 `__init__.py` 的 re-export 已更新
- [ ] 确认 `backend/prompts.py` 的统一导出无遗漏

### 重命名变量/函数
- [ ] 全局搜索旧名称，确认无遗漏引用
- [ ] 检查前端是否依赖该字段名

### 拆分文件
- [ ] 新建 `__init__.py` 导出公共接口
- [ ] 旧文件中保留兼容导入（如有外部引用）

### Prompt 重构
- [ ] 检查 f-string 的 `{{var}}` 转义完整
- [ ] `python -c "from backend.prompt_templates.XXX import YYY"` 验证导入
- [ ] 运行一次完整研究流程确认输出质量

## 验证方式

```bash
# 1. 导入验证
python -c "from backend.prompt_templates.queries import RESEARCHER_SYSTEM_MESSAGE; print('OK')"
python -c "from backend.prompt_templates.editor import COMPILE_CONTENT_PROMPT; print('OK')"
python -c "from backend.prompt_templates.seller_profile import SELLER_NAME_EN; print('OK')"

# 2. 启动验证
python application.py  # 无报错即可

# 3. 功能验证
# 通过前端或 curl 触发一次研究，检查报告完整性
```
