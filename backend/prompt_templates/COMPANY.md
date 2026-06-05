# LoctekMotion 公司简介（权威来源）

> **维护说明**：本文件是 LoctekMotion 公司信息的**唯一权威来源**。  
> 代码中的变量定义位于 `seller_profile.py`，从此文件派生，二者需保持一致。  
> 所有 Prompt 和 LLM 调用均从 `seller_profile.py` 读取公司上下文，不得在其他文件中重复硬编码。

---

## 1. 公司身份

| 字段 | 内容 |
|------|------|
| 中文名称 | 乐歌股份 |
| 英文名称 | LoctekMotion |
| 官网 | www.loctekmotion.com |
| 定位 | 中国人体工学升降产品制造商 |
| 制造能力 | 多工厂布局（中国 + 越南），支持大批量稳定交付 |
| 市场角色 | B2B 产品销售方——向零售商、采购商、品牌商、渠道商出售现有产品，支持贴牌(OEM/ODM)或自营品牌 |

---

## 2. 主营品类（权威列表，不可随意扩展）

| # | 英文名称 | 中文名称 | 备注 |
|---|----------|----------|------|
| 1 | Standing Desk / Desk Frames | 电动升降桌 / 桌架 | ★ 核心品类，含线性驱动 |
| 2 | TV Mount | 电视支架 | |
| 3 | Electric Sofa | 电动沙发 | |
| 4 | Electric Bed | 电动床 | |
| 5 | Chair | 办公椅 / 人体工学椅 | |
| 6 | Monitor Stand | 显示器支架 | |
| 7 | Lifting Platform | 升降台 | |
| 8 | Fitness Equipment | 健身器材 | |
| 9 | Meeting Pod | 会议舱 | |

---

## 3. 方案场景（可由品类自由组合）

| 场景 | 典型品类组合 |
|------|-------------|
| Office Solutions | Standing Desk + Monitor Stand + Chair + Meeting Pod |
| Home Solutions | Electric Bed + Electric Sofa + TV Mount + Fitness Equipment |
| Workspace Upgrade | Lifting Platform + Standing Desk + Monitor Stand |

> 以上仅为示例，任何品类的合理组合均可构成方案。

---

## 4. 核心价值主张

1. **人体工学与健康办公** — 产品围绕"动态办公"设计
2. **快速安装，质量认证** — 通过 UL / BIFMA / CE 等国际认证
3. **保修完善，稳定交付** — 自有工厂保障产能与品控
4. **外观与配置定制** — 针对已下单客户提供样品 / 批量定制需求

---

## 5. 销售边界（硬性约束）

LoctekMotion **只做产品销售**，以下合作类型不在系统推广范围内：

| 禁止类型 | 说明 |
|----------|------|
| ❌ 技术授权 / 技术嵌入 | 不提供驱动/控制系统的技术方案输出 |
| ❌ 联合研发 / 智能化集成 | 不参与客户产品的技术研发 |
| ❌ 非产品交付类合作 | 一切需要"提供技术能力"而非"交付产品"的请求 |

**判断准则**：目标客户的受众是否有购买/使用上述主营品类产品的真实需求？

- ✅ 有 → 构建 `marketablePlans`
- ❌ 否 → 返回 `marketablePlans: []`，注明不匹配原因，不得强行构造方案

---

## 6. 代码映射

本文件的信息在代码中对应 `backend/prompt_templates/seller_profile.py` 的以下变量：

| 变量 | 用途 |
|------|------|
| `SELLER_NAME_ZH` / `SELLER_NAME_EN` | 公司名称 |
| `SELLER_WEBSITE` | 官网 |
| `SELLER_PRODUCTS_EN` / `SELLER_PRODUCTS_ZH` | 产品列表 |
| `SELLER_CONTEXT_EN` | 英文研究查询上下文（queries.py 使用）|
| `SELLER_CONTEXT_ZH` | 中文编辑上下文（editor.py 使用）|
| `SELLER_INTRO_EN` | 开发信中的公司介绍（email_outreach.py 使用）|
| `SELLER_ONE_LINER_EN` | 快速研究单行描述（quick_research.py 使用）|
