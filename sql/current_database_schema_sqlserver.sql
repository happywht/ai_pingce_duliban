-- 总承包AI质量评测系统 - SQL Server 数据库建表脚本
-- 数据库名称: ai_doc_review
-- 兼容: Microsoft SQL Server

-- 检查并创建数据库
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'ai_doc_review')
BEGIN
    CREATE DATABASE [ai_doc_review];
END
GO

USE [ai_doc_review];
GO

-- 删除已存在的表（按依赖关系倒序）
IF OBJECT_ID('project_file', 'U') IS NOT NULL DROP TABLE [project_file];
IF OBJECT_ID('project_evaluation', 'U') IS NOT NULL DROP TABLE [project_evaluation];
IF OBJECT_ID('evaluation_templates', 'U') IS NOT NULL DROP TABLE [evaluation_templates];
IF OBJECT_ID('document_categories', 'U') IS NOT NULL DROP TABLE [document_categories];
IF OBJECT_ID('project', 'U') IS NOT NULL DROP TABLE [project];
GO

-- 创建项目表
CREATE TABLE [project] (
    [id] NVARCHAR(100) NOT NULL,
    [project_code] NVARCHAR(100) NULL,
    [project_name] NVARCHAR(255) NULL,
    [epc_manager] NVARCHAR(100) NULL,  -- 项目经理
    [entrust_manager] NVARCHAR(100) NULL,  -- 项目执行经理
    [last_update] DATETIME DEFAULT (GETDATE()) NULL,
    CONSTRAINT [PK_project] PRIMARY KEY ([id])
);
GO

-- 创建项目表索引
CREATE NONCLUSTERED INDEX [idx_project_code] ON [project] ([project_code]);
GO

-- 创建项目评测表
CREATE TABLE [project_evaluation] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [project_id] NVARCHAR(100) NOT NULL,
    [task_id] NVARCHAR(100) DEFAULT 'DEFAULT_TASK' NULL,
    [status] NVARCHAR(50) DEFAULT 'IDLE' NULL,
    [rules_config] NVARCHAR(4000) NULL,
    [evaluation_result] NVARCHAR(8000) NULL,
    [check_date] NVARCHAR(20) NULL, -- 检查日期，格式: YYYY-MM-DD，来自文件信息接口
    [check_person_name] NVARCHAR(100) NULL, -- 检查人员姓名，来自文件信息接口
    [created_at] DATETIME DEFAULT (GETDATE()) NULL,
    [updated_at] DATETIME NULL,
    [check_name] NVARCHAR(100) NULL, -- 检查人员姓名，来自任务信息
    CONSTRAINT [PK_project_evaluation] PRIMARY KEY ([id]),
    CONSTRAINT [UQ_project_task] UNIQUE ([project_id], [task_id])
);
GO

-- 创建项目评测表索引
CREATE NONCLUSTERED INDEX [idx_project_id] ON [project_evaluation] ([project_id]);
CREATE NONCLUSTERED INDEX [idx_task_id] ON [project_evaluation] ([task_id]);
CREATE NONCLUSTERED INDEX [idx_status] ON [project_evaluation] ([status]);
CREATE NONCLUSTERED INDEX [idx_project_evaluation_check_date] ON [project_evaluation] ([check_date]);
CREATE NONCLUSTERED INDEX [idx_project_evaluation_check_person] ON [project_evaluation] ([check_person_name]);
GO

-- 创建项目文件表
CREATE TABLE [project_file] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [project_id] NVARCHAR(100) NOT NULL,
    [task_id] NVARCHAR(100) DEFAULT 'DEFAULT_TASK' NULL,
    [category_id] NVARCHAR(100) NULL,
    [category_name] NVARCHAR(255) NULL,
    [file_name] NVARCHAR(255) NULL,
    [file_url] NVARCHAR(1000) NULL,
    [file_type] NVARCHAR(50) NULL,
    [file_hash] NVARCHAR(64) NULL,
    [parsed_content] NVARCHAR(8000) NULL,
    [update_time] DATETIME DEFAULT (GETDATE()) NULL,
    CONSTRAINT [PK_project_file] PRIMARY KEY ([id])
);
GO

-- 创建项目文件表索引
CREATE NONCLUSTERED INDEX [idx_project_file] ON [project_file] ([project_id], [task_id]);
CREATE NONCLUSTERED INDEX [idx_category] ON [project_file] ([category_id]);
CREATE NONCLUSTERED INDEX [idx_file_hash] ON [project_file] ([file_hash]);
GO

-- 创建评测模板表
CREATE TABLE [evaluation_templates] (
    [id] NVARCHAR(100) NOT NULL,
    [template_name] NVARCHAR(255) NOT NULL,
    [template_type] NVARCHAR(50) DEFAULT 'custom' NOT NULL,
    [description] NVARCHAR(2000) NULL,
    [rules_config] NVARCHAR(4000) NULL,
    [is_active] BIT DEFAULT 1 NULL,
    [created_by] NVARCHAR(100) NULL,
    [created_at] DATETIME DEFAULT (GETDATE()) NULL,
    [updated_at] DATETIME NULL,
    CONSTRAINT [PK_evaluation_templates] PRIMARY KEY ([id])
);
GO

-- 创建文档分类表
CREATE TABLE [document_categories] (
    [id] INT IDENTITY(1,1) NOT NULL,
    [category_id] NVARCHAR(100) NOT NULL,
    [category_name] NVARCHAR(255) NOT NULL,
    [parent_category_id] NVARCHAR(100) NULL,
    [description] NVARCHAR(1000) NULL,
    [sort_order] INT DEFAULT 0 NULL,
    [is_active] BIT DEFAULT 1 NULL,
    [created_at] DATETIME DEFAULT (GETDATE()) NULL,
    CONSTRAINT [PK_document_categories] PRIMARY KEY ([id]),
    CONSTRAINT [UQ_category_id] UNIQUE ([category_id])
);
GO

-- 创建外键约束
ALTER TABLE [project_evaluation] WITH CHECK ADD CONSTRAINT [FK_project_evaluation_project]
    FOREIGN KEY([project_id]) REFERENCES [project] ([id]) ON DELETE CASCADE;
ALTER TABLE [project_evaluation] CHECK CONSTRAINT [FK_project_evaluation_project];
GO

ALTER TABLE [project_file] WITH CHECK ADD CONSTRAINT [FK_project_file_project]
    FOREIGN KEY([project_id]) REFERENCES [project] ([id]) ON DELETE CASCADE;
ALTER TABLE [project_file] CHECK CONSTRAINT [FK_project_file_project];
GO

-- 创建自动更新 updated_at 字段的触发器
CREATE TRIGGER [trg_project_evaluation_updated_at]
ON [project_evaluation]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE([status]) OR UPDATE([rules_config]) OR UPDATE([evaluation_result])
    BEGIN
        UPDATE pe
        SET [updated_at] = GETDATE()
        FROM [project_evaluation] pe
        INNER JOIN inserted i ON pe.[id] = i.[id];
    END
END
GO

CREATE TRIGGER [trg_evaluation_templates_updated_at]
ON [evaluation_templates]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE([template_name]) OR UPDATE([template_type]) OR UPDATE([description]) OR UPDATE([rules_config])
    BEGIN
        UPDATE et
        SET [updated_at] = GETDATE()
        FROM [evaluation_templates] et
        INNER JOIN inserted i ON et.[id] = i.[id];
    END
END
GO

-- 创建项目表的更新时间触发器
CREATE TRIGGER [trg_project_last_update]
ON [project]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE([project_code]) OR UPDATE([project_name]) OR UPDATE([rules_config])
    BEGIN
        UPDATE p
        SET [last_update] = GETDATE()
        FROM [project] p
        INNER JOIN inserted i ON p.[id] = i.[id];
    END
END
GO

-- 创建项目文件表的更新时间触发器
CREATE TRIGGER [trg_project_file_update_time]
ON [project_file]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    IF UPDATE([file_name]) OR UPDATE([file_url]) OR UPDATE([parsed_content])
    BEGIN
        UPDATE pf
        SET [update_time] = GETDATE()
        FROM [project_file] pf
        INNER JOIN inserted i ON pf.[id] = i.[id];
    END
END
GO

-- 插入默认的文档分类数据
IF NOT EXISTS (SELECT 1 FROM [document_categories] WHERE [category_id] = 'civil')
BEGIN
    INSERT INTO [document_categories] ([category_id], [category_name], [parent_category_id], [sort_order], [is_active])
    VALUES
    ('civil', '土木工程', NULL, 1, 1),
    ('structure', '结构工程', 'civil', 2, 1),
    ('architectural', '建筑学', 'civil', 3, 1),
    ('municipal', '市政工程', 'civil', 4, 1),
    ('mechanical', '机电工程', NULL, 5, 1),
    ('electrical', '电气工程', 'mechanical', 6, 1),
    ('hvac', '暖通空调', 'mechanical', 7, 1),
    ('plumbing', '给排水', 'mechanical', 8, 1);
END
GO

-- 插入默认的评测模板
IF NOT EXISTS (SELECT 1 FROM [evaluation_templates] WHERE [id] = 'template_default')
BEGIN
    INSERT INTO [evaluation_templates] ([id], [template_name], [template_type], [description], [rules_config], [is_active])
    VALUES
    ('template_default', '默认模板', 'default', '默认的文档质量评测模板',
    '[
        {
            "id": "completeness",
            "name": "完整性检查",
            "description": "检查文档是否包含必要的章节和内容",
            "weight": 25,
            "enabled": true
        },
        {
            "id": "consistency",
            "name": "一致性检查",
            "description": "检查文档内部及与其他文档的一致性",
            "weight": 20,
            "enabled": true
        },
        {
            "id": "accuracy",
            "name": "准确性检查",
            "description": "检查技术参数、计算的准确性",
            "weight": 30,
            "enabled": true
        },
        {
            "id": "compliance",
            "name": "合规性检查",
            "description": "检查是否符合相关规范和标准",
            "weight": 25,
            "enabled": true
        }
    ]', 1);
END
GO

PRINT 'SQL Server 数据库表创建完成！';
PRINT '数据库名称: ai_doc_review';
PRINT '创建的表: project, project_evaluation, project_file, evaluation_templates, document_categories';
PRINT '包含索引、外键约束、触发器和默认数据';