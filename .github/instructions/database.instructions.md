---
applyTo: "backend/services/mongodb.py"
---

# 数据库规则

## MongoDB（可选组件）

- 数据库名：`tavily_research`
- 集合：`jobs`（任务状态）、`reports`（最终报告）
- 连接串：环境变量 `MONGODB_URI`
- 无 MongoDB 时系统正常运行，数据仅存于内存 `job_status` dict

## 规则

1. 所有 MongoDB 操作必须 try/except，缺失连接不应导致管道失败
2. 写入使用 `w='majority'`、`retryWrites=True`
3. TLS 连接使用 `certifi` 证书
4. 不要在 MongoDB 中存储敏感密钥
5. 文档 ID 使用 `job_id`（UUID4 字符串）
