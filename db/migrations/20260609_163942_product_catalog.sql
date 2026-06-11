-- ============================================================
-- 产品目录表（供开发信推荐产品使用）
-- 创建时间: 2026-06-09 16:39:42
-- ============================================================
use company_research


CREATE TABLE IF NOT EXISTS product_catalog (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  sku VARCHAR(100) NOT NULL COMMENT '产品SKU/型号',
  category ENUM(
    'linear_actuator',
    'tv_mount',
    'electric_sofa',
    'electric_bed',
    'chair',
    'monitor_stand',
    'standing_desk',
    'other',
    'fitness_equipment',
    'meeting_pod'
  ) NOT NULL COMMENT '品类',
  product_name VARCHAR(255) NOT NULL COMMENT '产品名称(英文)',
  product_name_zh VARCHAR(255) NULL COMMENT '产品名称(中文)',
  image_url VARCHAR(2048) NULL COMMENT '产品图片链接',
  tier ENUM('low', 'mid', 'high') NOT NULL DEFAULT 'mid' COMMENT '产品定位: low=经济型, mid=中档, high=高端',
  advantages TEXT NULL COMMENT '产品优势/卖点(英文)',
  available_colors VARCHAR(500) NULL COMMENT '可选颜色，逗号分隔',
  is_active TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否在售',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_sku (sku),
  INDEX idx_category (category),
  INDEX idx_tier (tier),
  INDEX idx_active_category (is_active, category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品目录-供开发信推荐使用';

-- ============================================================
-- 插入产品数据
-- ============================================================
INSERT INTO product_catalog (sku, category, product_name, image_url, tier, advantages, available_colors) VALUES
(
  'LPD101',
  'meeting_pod',
  'LPD101 Meeting Pod',
  'https://e.loctek.com/file-center/export-file/local-obs/016/2c2874425e964aba82352b615c683636',
  'low',
  'Flexible layout – combine or separate pods to fit your space\nEasy installation – lightweight, modular, and mobile\nComfortable – built-in desk, lighting, ventilation, and seating',
  NULL
),
(
  'ET223Q',
  'linear_actuator',
  'ET223Q Linear Actuator Desk Frame',
  'https://e.loctek.com/file-service/image/preview/627dbbc723ee20407003e89d',
  'high',
  'Strong stability for large desktops\nSmooth and quiet lifting performance\nMultiple frame designs for different price levels and markets',
  NULL
),
(
  'ET156-C',
  'linear_actuator',
  'ET156-C Smart Standing Desk',
  'https://e.loctek.com/file-center/export-file/local-obs/404/76bf7364d5264ef3bc52369dc8920862',
  'mid',
  '4 Programmable Height Presets\nUSB Charging Port\nEmbedded Drawer\nTempered Glass for a Safer Sleeker Workspace with Strict Testing Standards',
  NULL
)
ON DUPLICATE KEY UPDATE
  category = VALUES(category),
  product_name = VALUES(product_name),
  image_url = VALUES(image_url),
  tier = VALUES(tier),
  advantages = VALUES(advantages),
  available_colors = VALUES(available_colors);
