-- 总承包AI质量评测系统 - 数据库建表脚本
-- 数据库名称: ai_doc_review
-- 生成时间: 2025-12-04 16:58:19
-- 字符集: utf8mb4
-- 排序规则: utf8mb4_unicode_ci

-- 创建数据库
CREATE DATABASE IF NOT EXISTS `ai_doc_review` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `ai_doc_review`;

-- 禁用外键检查
SET FOREIGN_KEY_CHECKS = 0;

-- 删除已存在的表
DROP TABLE IF EXISTS `project_file`;
DROP TABLE IF EXISTS `project_evaluation`;
DROP TABLE IF EXISTS `evaluation_templates`;
DROP TABLE IF EXISTS `document_categories`;
DROP TABLE IF EXISTS `project`;

-- 创建项目表
CREATE TABLE `project` (
  `id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `project_code` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `project_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_update` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `rules_config` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `idx_project_code` (`project_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建项目评测表
CREATE TABLE `project_evaluation` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `project_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `task_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'DEFAULT_TASK',
  `status` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT 'IDLE',
  `rules_config` text COLLATE utf8mb4_unicode_ci,
  `evaluation_result` longtext COLLATE utf8mb4_unicode_ci,
  `check_date` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '检查日期，格式: YYYY-MM-DD，来自文件信息接口',
  `check_person_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '检查人员姓名，来自文件信息接口',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `check_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '检查人员姓名，来自任务信息',
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_project_task` (`project_id`,`task_id`),
  KEY `idx_project_id` (`project_id`),
  KEY `idx_task_id` (`task_id`),
  KEY `idx_status` (`status`),
  KEY `idx_project_evaluation_check_date` (`check_date`),
  KEY `idx_project_evaluation_check_person` (`check_person_name`),
  CONSTRAINT `project_evaluation_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `project` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建项目文件表
CREATE TABLE `project_file` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `project_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `task_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'DEFAULT_TASK',
  `category_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_url` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `parsed_content` longtext COLLATE utf8mb4_unicode_ci,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_project_file` (`project_id`,`task_id`),
  KEY `idx_category` (`category_id`),
  KEY `idx_file_hash` (`file_hash`),
  CONSTRAINT `project_file_ibfk_1` FOREIGN KEY (`project_id`) REFERENCES `project` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=188 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建评测模板表
CREATE TABLE `evaluation_templates` (
  `id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `template_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `template_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'custom',
  `description` text COLLATE utf8mb4_unicode_ci,
  `rules_config` text COLLATE utf8mb4_unicode_ci,
  `is_active` tinyint(1) DEFAULT '1',
  `created_by` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 创建文档分类表
CREATE TABLE `document_categories` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `category_id` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category_name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `parent_category_id` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `sort_order` int(11) DEFAULT '0',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `category_id` (`category_id`)
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 重新启用外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 插入默认数据
INSERT IGNORE INTO `document_categories`
(`category_id`, `category_name`, `parent_category_id`, `description`, `sort_order`, `is_active`, `created_at`) VALUES
('cat_001', '施工方案', '', '施工组织设计、专项施工方案等', 1, 1, NOW()),
('cat_002', '技术资料', '', '技术交底、图纸会审、变更洽商等', 2, 1, NOW()),
('cat_003', '质量资料', '', '质量保证资料、检验批、验收记录等', 3, 1, NOW()),
('cat_004', '安全资料', '', '安全方案、检查记录、教育培训等', 4, 1, NOW()),
('cat_005', '合同资料', '', '合同文件、分包协议、签证变更等', 5, 1, NOW()),
('cat_006', '进度资料', '', '进度计划、实际进度记录等', 6, 1, NOW()),
('cat_007', '成本资料', '', '造价文件、成本控制、结算资料等', 7, 1, NOW()),
('cat_008', '其他资料', '', '其他相关文件资料', 8, 1, NOW());

INSERT IGNORE INTO `evaluation_templates`
(`id`, `template_name`, `template_type`, `description`, `is_active`, `created_at`, `updated_at`) VALUES
('basic_template', '基础质量评测模板', 'basic', '适用于一般总承包项目的基础质量评测，包含主要检查项', 1, NOW(), NOW()),
('advanced_template', '全面质量评测模板', 'advanced', '适用于复杂项目的全面质量评测，检查项更详细全面', 1, NOW(), NOW()),
('safety_template', '安全生产评测模板', 'safety', '专门用于安全生产管理的评测模板', 1, NOW(), NOW());

-- 完成提示
SELECT 'Database schema recreated successfully!' as status;
