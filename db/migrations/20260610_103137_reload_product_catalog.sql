-- ============================================================
-- Reload product_catalog data
-- Created at: 2026-06-10 10:31:37
-- ============================================================

USE company_research;

-- 1) Clear existing data but keep table structure
TRUNCATE TABLE product_catalog;

-- 2) Re-import product data from catalog file
INSERT INTO product_catalog (
  sku,
  category,
  product_name,
  image_url,
  tier,
  advantages,
  available_colors
) VALUES
(
  'LPD101',
  'meeting_pod',
  'LPD101 Meeting Pod',
  'https://df-api.loctek.com/temp/2026/6/2054106295172861952.png',
  'low',
  'Flexible layout - combine or separate pods to fit your space\nEasy installation - lightweight, modular, and mobile\nComfortable - built-in desk, lighting, ventilation, and seating',
  NULL
),
(
  'MPD114-SR-EWT',
  'meeting_pod',
  'MPD114-SR-EWT',
  'https://df-api.loctek.com/temp/2026/6/2029502124974276608.png',
  'mid',
  'Sound insulation up to 30.4 dB - class A (ISO 23351-1)\nFactory-direct pricing\nModular design - installed by two people in about 40 minutes',
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
  'ET156E',
  'linear_actuator',
  'ET156E',
  'https://e.loctek.com/file-service/image/preview/6540bd487dd6c44ab276d56c',
  'low',
  'More competitive price without losing\nproduct quality.\n2-Stage column design ensures\nsmooth and precise electric lifting\nability.\nThe six-button handset can flexibly\nadjust the height of your desk.\nDesigned for maximum structural\nintegrity, our frame features double\nsteel tubing that ensures stability even\nat its highest height.\nSingle motor technology enables\npowerful yet smooth height\nadjustments.',
  NULL
),
(
  'ET262',
  'linear_actuator',
  'ET262',
  'https://e.loctek.com/file-service/image/preview/654c70977dd6c44ab2775616',
  'mid',
  'More competitive price without losing\nproduct quality.\n2-Stage column design ensures\nsmooth and precise electric lifting\nability.\nThe six-button handset can flexibly\nadjust the height of your desk.\nDual-Motor system enables a faster\nand more stable adjustment,larger\nloading capacity.',
  NULL
),
(
  'DLB507',
  'monitor_stand',
  'DLB507',
  'https://e.loctek.com/file-center/export-file/local-obs/190/30155bc60f8543c99364826b8e443fd7',
  'low',
  'Sleeve-Type Quick-Mount System\nQuick replacement\n36mm Diameter Sleeve',
  NULL
),
(
  'DLB511',
  'monitor_stand',
  'DLB511',
  'https://df-api.loctek.com/temp/2026/6/2062456535122866176.gif',
  'mid',
  'Sleeve-Type Quick-Mount System\nOne-Finger Adjustment\nSpring-Assisted VESA Tilt\nPatented Quick-Adjust Base\nMulti-Plane Cable Management\nTool-Free VESA Plate',
  NULL
),
(
  'DLB996',
  'monitor_stand',
  'DLB996',
  'https://e.loctek.com/file-center/export-file/local-obs/1bc/98d5f8f95e7e47acbf30791d55a516d5',
  'high',
  'Sleeve-Type Quick-Mount System\n45mm Extra-Wide Sleeve\nVisual Adjustment\nTool-free Adjustment\nSpring-Assisted VESA Panel',
  NULL
);
