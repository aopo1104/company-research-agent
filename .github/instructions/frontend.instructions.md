---
applyTo: "ui/**"
---

# 前端开发规则

## 技术栈

- React 18 + TypeScript (strict)
- Vite 6 构建
- Tailwind CSS（utility-first，不写自定义 CSS）
- Lucide React 图标库

## 架构

- `App.tsx`：主状态管理，SSE 连接，路由逻辑
- `components/`：纯展示组件，通过 props 接收数据
- `types/index.ts`：所有 TypeScript 类型定义
- `styles/index.ts`：共享的 Tailwind 类字符串常量

## SSE 通信

前端通过 `EventSource` 连接 `/research/{job_id}/stream`，接收事件：
- `research_init`：研究开始
- `progress`：节点进度更新
- `scrape_source`：enricher 阶段 URL 抓取状态
- `complete`：报告完成（含完整 Markdown）

错误重试逻辑：最多 12 次，失败后回退到轮询 `/research/{job_id}/report`。

## 规则

1. 所有组件使用函数式写法 + hooks
2. 状态提升到 App.tsx，子组件不直接调用 API
3. API base URL 从 `import.meta.env.VITE_API_URL` 读取
4. 表单数据结构必须与后端 `InputState` 保持一致
5. Markdown 渲染使用 `react-markdown` + `remark-gfm`
6. 不引入额外状态管理库（zustand/redux），当前规模不需要
