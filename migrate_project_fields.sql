-- =====================================================
-- SQL Server 数据库迁移脚本
-- 为 project 表添加项目经理相关字段
-- 用于适配新的项目信息接口响应格式
-- =====================================================

USE [ai_doc_review];
GO

-- 检查字段是否存在，如果不存在则添加
-- 添加 epc_manager 字段（项目经理）
IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'project'
    AND COLUMN_NAME = 'epc_manager'
)
BEGIN
    PRINT '🔧 正在添加 epc_manager 字段...';
    ALTER TABLE [project] ADD [epc_manager] NVARCHAR(100) NULL;
    PRINT '✅ epc_manager 字段添加成功';
END
ELSE
BEGIN
    PRINT 'ℹ️ epc_manager 字段已存在';
END
GO

-- 添加 entrust_manager 字段（项目执行经理）
IF NOT EXISTS (
    SELECT 1
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'project'
    AND COLUMN_NAME = 'entrust_manager'
)
BEGIN
    PRINT '🔧 正在添加 entrust_manager 字段...';
    ALTER TABLE [project] ADD [entrust_manager] NVARCHAR(100) NULL;
    PRINT '✅ entrust_manager 字段添加成功';
END
ELSE
BEGIN
    PRINT 'ℹ️ entrust_manager 字段已存在';
END
GO

-- 验证字段添加结果
PRINT '🔍 验证字段添加结果...';
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'project'
AND COLUMN_NAME IN ('epc_manager', 'entrust_manager')
ORDER BY COLUMN_NAME;
GO

-- 查看当前表结构
PRINT '📋 当前 project 表结构:';
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    IS_NULLABLE,
    COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'project'
ORDER BY ORDINAL_POSITION;
GO

PRINT '🎉 数据库迁移完成！';
PRINT '📝 已为 project 表添加以下字段：';
PRINT '   - epc_manager: 项目经理 (NVARCHAR(100))';
PRINT '   - entrust_manager: 项目执行经理 (NVARCHAR(100))';
GO