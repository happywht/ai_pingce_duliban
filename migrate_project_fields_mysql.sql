-- =====================================================
-- MySQL 数据库迁移脚本
-- 为 project 表添加项目经理相关字段
-- 用于适配新的项目信息接口响应格式
-- =====================================================

USE ai_doc_review;

-- 添加 epc_manager 字段（项目经理）
-- 使用 IF NOT EXISTS 避免重复添加
SET @dbname = DATABASE();
SET @tablename = 'project';
SET @columnname = 'epc_manager';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_schema = @dbname)
      AND (table_name = @tablename)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(100) COMMENT \'项目经理\'')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 添加 entrust_manager 字段（项目执行经理）
SET @columnname = 'entrust_manager';
SET @preparedStatement = (SELECT IF(
  (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE
      (table_schema = @dbname)
      AND (table_name = @tablename)
      AND (column_name = @columnname)
  ) > 0,
  'SELECT 1',
  CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(100) COMMENT \'项目执行经理\'')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- 验证字段添加结果
SELECT '🔍 验证字段添加结果...' as message;

SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = @dbname
  AND TABLE_NAME = @tablename
  AND COLUMN_NAME IN ('epc_manager', 'entrust_manager')
ORDER BY COLUMN_NAME;

-- 查看当前表结构
SELECT '📋 当前 project 表结构:' as message;

SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    COLUMN_DEFAULT,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = @dbname
  AND TABLE_NAME = @tablename
ORDER BY ORDINAL_POSITION;

SELECT '🎉 数据库迁移完成！' as message;
SELECT '📝 已为 project 表添加以下字段：' as message;
SELECT '   - epc_manager: 项目经理 (VARCHAR(100))' as message;
SELECT '   - entrust_manager: 项目执行经理 (VARCHAR(100))' as message;