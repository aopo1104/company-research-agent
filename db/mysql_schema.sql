-- 公司研究平台 MySQL 初始化 Schema
-- 使用前请先创建数据库: CREATE DATABASE IF NOT EXISTS company_research DEFAULT CHARSET utf8mb4;

CREATE TABLE IF NOT EXISTS companies (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id VARCHAR(36) NOT NULL COMMENT '研究任务ID',
  company_url VARCHAR(2048) NULL COMMENT '公司网址',
  company_name VARCHAR(255) NULL COMMENT '公司名称',
  industry VARCHAR(255) NULL COMMENT '行业',
  hq_location VARCHAR(255) NULL COMMENT '总部位置',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_job_id (job_id),
  INDEX idx_company_name (company_name),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='查询时记录的公司信息';

CREATE TABLE IF NOT EXISTS research_reports (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id VARCHAR(36) NOT NULL COMMENT '研究任务ID',
  company_name VARCHAR(255) NULL COMMENT '公司名称',
  report_content LONGTEXT NOT NULL COMMENT '最终研究报告(Markdown)',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_job_id (job_id),
  INDEX idx_company_name (company_name),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='研究完成后的最终报告';

CREATE TABLE IF NOT EXISTS outreach_emails (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  job_id VARCHAR(36) NULL COMMENT '关联的研究任务ID(可选)',
  company_name VARCHAR(255) NULL COMMENT '公司名称',
  subject VARCHAR(1000) NULL COMMENT '邮件主题',
  body LONGTEXT NOT NULL COMMENT '邮件正文',
  email_json JSON NULL COMMENT 'LLM返回的完整JSON',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_job_id (job_id),
  INDEX idx_company_name (company_name),
  INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生成的开发信';
