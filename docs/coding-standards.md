# 编码规范

## Python (后端)

### 风格

- Python 3.10+ 语法（match/case 可用但暂未使用）
- 类型注解：函数参数和返回值必须标注
- 格式化：遵循 PEP 8，行宽 120
- Import 顺序：stdlib → third-party → local

### 异步

```python
# ✅ 正确
async def fetch_data(url: str) -> str:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        return resp.text

# ❌ 错误：同步阻塞
def fetch_data(url: str) -> str:
    return requests.get(url).text
```

### 日志

```python
import logging
logger = logging.getLogger(__name__)

# ✅ 正确
logger.info(f"Processing {url}")
logger.warning(f"Timeout for {domain}")

# ❌ 错误
print(f"Processing {url}")
```

### Prompt 工程

```python
# ✅ 正确：从 seller_profile 引用，模板变量双转义
from .seller_profile import SELLER_NAME_EN, SELLER_CONTEXT_EN

PROMPT = f"""You are researching {{company}} for {SELLER_NAME_EN}.
{SELLER_CONTEXT_EN}
"""

# ❌ 错误：硬编码公司名，单花括号模板变量
PROMPT = f"""You are researching {company} for LoctekMotion."""
```

### 错误处理

```python
# ✅ 对外部服务做防御
try:
    result = await asyncio.wait_for(fetch(url), timeout=15)
except asyncio.TimeoutError:
    logger.warning(f"Timeout: {url}")
    result = None
except httpx.HTTPStatusError as e:
    if e.response.status_code in (403, 401):
        return None  # 不重试
    raise
```

## TypeScript (前端)

### 风格

- 函数式组件 + hooks
- Props 类型通过 interface 定义
- 严格模式（`strict: true`）
- 无 `any`

### 组件结构

```tsx
interface Props {
  data: ResearchReport;
  onAction: () => void;
}

export function MyComponent({ data, onAction }: Props) {
  // hooks
  // handlers
  // render
}
```

### 样式

- Tailwind utility class 优先
- 复用类抽到 `styles/index.ts` 为常量
- 不写内联 style 对象
- 不创建 CSS 文件

## 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| Python 文件 | snake_case | `scrape_engine.py` |
| Python 类 | PascalCase | `DomainCircuitBreaker` |
| Python 函数/变量 | snake_case | `get_research_data` |
| Python 常量 | UPPER_SNAKE | `SELLER_NAME_EN` |
| TS 组件 | PascalCase | `ResearchReport.tsx` |
| TS 函数 | camelCase | `handleSubmit` |
| TS 类型 | PascalCase | `ResearchState` |
| API 路径 | kebab-case | `/extract-company-info` |
