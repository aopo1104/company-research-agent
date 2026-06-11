"""
================================================================================
seller_profile.py - 委托方公司信息配置
================================================================================
修改此文件以切换不同的委托方公司，无需修改各个 prompt 文件。

所有 prompt 文件通过以下方式引用：
    from .seller_profile import SELLER_NAME, SELLER_PRODUCTS_ZH, SELLER_CONTEXT_EN, SELLER_CONTEXT_ZH
"""

# ============================================================
# 基本信息
# ============================================================
SELLER_NAME_ZH = "乐歌股份"
SELLER_NAME_EN = "LoctekMotion"
SELLER_WEBSITE = "www.loctekmotion.com"
SELLER_DESCRIPTION_EN = "a Chinese ergonomic lifting product manufacturer"
SELLER_DESCRIPTION_ZH = "中国人体工学升降产品制造商"

# 销售代表姓名（用于开发信签名和自我介绍）
SELLER_REP_NAME = "Kimi"
SELLER_REP_TITLE = "Sales Manager"

# ============================================================
# 制造与市场定位
# ============================================================
SELLER_MANUFACTURING = "Multi-factory layout (China + Vietnam), supporting large-volume stable delivery"
SELLER_MANUFACTURING_ZH = "多工厂布局（中国+越南），支持大批量稳定交付"
SELLER_MARKET_ROLE_EN = "B2B product seller — sells to retailers, buyers, brand owners, and distributors; supports OEM/ODM and private-label"
SELLER_MARKET_ROLE_ZH = "B2B产品销售方——向零售商、采购商、品牌商、渠道商出售现有产品，支持贴牌(OEM/ODM)或自营品牌"
SELLER_CERTIFICATIONS = "UL, BIFMA, CE"

# ============================================================
# 产品线（中英文）
# ============================================================

# 品类枚举（与数据库 product_catalog.category ENUM 保持一致）
PRODUCT_CATEGORIES = {
    "linear_actuator": "线性驱动 / Linear Actuator",
    "tv_mount": "电视支架 / TV Mount",
    "electric_sofa": "电动沙发 / Electric Sofa",
    "electric_bed": "电动床 / Electric Bed",
    "chair": "椅子 / Chair",
    "monitor_stand": "显示器支架 / Monitor Stand",
    "standing_desk": "升降台 / Standing Desk",
    "other": "其它 / Other",
    "fitness_equipment": "健身器材 / Fitness Equipment",
    "meeting_pod": "会议舱 / Meeting Pod",
}

# 供 prompt 使用的品类列表字符串
PRODUCT_CATEGORIES_EN = ", ".join(PRODUCT_CATEGORIES.keys())

SELLER_PRODUCTS_EN = [
    "Standing Desk / Desk Frames（电动升降桌）",
    "TV Mount（电视支架）",
    "Electric Sofa（电动沙发）",
    "Electric Bed（电动床）",
    "Chair（办公椅/人体工学椅）",
    "Monitor Stand（显示器支架）",
    "Lifting Platform（升降台）",
    "Fitness Equipment（健身器材）",
    "Meeting Pod（会议舱）",
]

SELLER_PRODUCTS_ZH = "电动升降桌、电视支架、电动沙发、电动床、办公椅、显示器支架、升降台、健身器材、会议舱"

SELLER_PRODUCTS_SHORT_EN = "Standing Desk, TV Mount, Electric Sofa, Electric Bed, Chair, Monitor Stand, Lifting Platform, Fitness Equipment, Meeting Pod"

SELLER_PRODUCTS_LIST_EN = "\n".join(f"- {p}" for p in SELLER_PRODUCTS_EN)

# ============================================================
# 方案场景
# ============================================================
SELLER_SOLUTIONS = {
    "Office Solutions": "Standing Desk + Monitor Stand + Chair + Meeting Pod",
    "Home Solutions": "Electric Bed + Electric Sofa + TV Mount + Fitness Equipment",
    "Workspace Upgrade": "Lifting Platform + Standing Desk + Monitor Stand",
}

# ============================================================
# 核心价值主张
# ============================================================
SELLER_VALUE_PROPS_EN = [
    "Ergonomic & healthy workspace — products designed around dynamic working",
    f"Quality certified — {SELLER_CERTIFICATIONS} international certifications",
    "Own-factory production — reliable capacity and quality control",
    "Appearance & configuration customization for OEM/ODM orders",
]

SELLER_VALUE_PROPS_ZH = [
    "人体工学与健康办公——产品围绕「动态办公」设计",
    f"快速安装，质量认证——通过 {SELLER_CERTIFICATIONS} 等国际认证",
    "保修完善，稳定交付——自有工厂保障产能与品控",
    "外观与配置定制——针对已下单客户提供样品/批量定制需求",
]

# ============================================================
# 销售边界（硬性约束）
# ============================================================
SELLER_BOUNDARY_NOTE_EN = (
    f"{SELLER_NAME_EN} ONLY sells physical products. "
    "The following cooperation types are OUT OF SCOPE: "
    "technology licensing/embedding, joint R&D/smart integration, "
    "any request requiring 'providing technical capabilities' rather than 'delivering products'."
)

SELLER_BOUNDARY_NOTE_ZH = (
    f"{SELLER_NAME_ZH}只做产品销售。"
    "以下合作类型不在推广范围：技术授权/技术嵌入、联合研发/智能化集成、"
    "一切需要「提供技术能力」而非「交付产品」的合作。"
)

# ============================================================
# 复合字符串（供各 prompt 直接引用）
# ============================================================

# 用于 queries.py 的单行英文上下文
SELLER_CONTEXT_EN = (
    f"【Seller Context】You are conducting this research on behalf of {SELLER_NAME_EN} "
    f"({SELLER_NAME_ZH}, {SELLER_WEBSITE}), {SELLER_DESCRIPTION_EN}.\n"
    f"Manufacturing: {SELLER_MANUFACTURING}. Market role: {SELLER_MARKET_ROLE_EN}.\n"
    f"{SELLER_NAME_EN}'s product categories: {SELLER_PRODUCTS_SHORT_EN}.\n"
    f"Certifications: {SELLER_CERTIFICATIONS}.\n"
    f"{SELLER_BOUNDARY_NOTE_EN}\n"
    f"Your research goal: Identify whether {{company}}'s audience has a real need for any of these products, "
    f"find sales channels, discover pain points, and uncover promotion opportunities for {SELLER_NAME_EN} to sell TO or THROUGH {{company}}."
)

# 用于 editor.py 的中文背景说明
SELLER_CONTEXT_ZH = (
    f"**委托方背景**：本报告由{SELLER_NAME_ZH}（{SELLER_NAME_EN}，{SELLER_WEBSITE}）委托生成。\n"
    f"{SELLER_NAME_ZH}是{SELLER_DESCRIPTION_ZH}，{SELLER_MANUFACTURING_ZH}。\n"
    f"市场角色：{SELLER_MARKET_ROLE_ZH}。\n"
    f"产品线包括：{SELLER_PRODUCTS_ZH}。\n"
    f"质量认证：{SELLER_CERTIFICATIONS}。\n"
    f"{SELLER_BOUNDARY_NOTE_ZH}"
)

# 用于 email_outreach.py 的英文身份说明
SELLER_INTRO_EN = (
    f"{SELLER_NAME_EN} ({SELLER_NAME_ZH}, {SELLER_WEBSITE}) is {SELLER_DESCRIPTION_EN}.\n"
    f"Manufacturing: {SELLER_MANUFACTURING}.\n"
    f"Certifications: {SELLER_CERTIFICATIONS}.\n"
    f"Products:\n{SELLER_PRODUCTS_LIST_EN}"
)

# 用于 quick_research.py 的英文单行描述
SELLER_ONE_LINER_EN = (
    f"{SELLER_NAME_EN} ({SELLER_NAME_ZH}), {SELLER_DESCRIPTION_EN}. "
    f"{SELLER_NAME_EN} sells: "
    + ", ".join(
        p.split("（")[0].strip()  # 取英文部分
        for p in SELLER_PRODUCTS_EN
    )
    + "."
)
