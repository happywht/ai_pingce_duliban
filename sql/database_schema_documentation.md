# 总承包AI质量评测系统 - 数据库表结构文档

## 📋 数据库概览

**数据库名称**: `ai_doc_review`
**字符集**: `utf8mb4`
**排序规则**: `utf8mb4_unicode_ci`
**引擎**: `InnoDB`

---

## 🏗️ 表结构详情

### 1. `project` - 项目基础信息表

| 字段名 | 类型 | 是否可空 | 默认值 | 描述 | 索引 |
|--------|------|----------|--------|------|------|
| **id** | varchar(100) | NO | - | 项目ID (主键) | PRIMARY |
| project_code | varchar(100) | YES | NULL | 项目编码 | idx_project_code |
| project_name | varchar(255) | YES | NULL | 项目名称 | - |
| last_update | datetime | YES | CURRENT_TIMESTAMP | 最后更新时间 | - |
| rules_config | text | YES | NULL | 规则配置 | - |

**外键关系**: 无
**数据统计**: 22条记录
**功能说明**: 存储项目的基础信息，包括项目编码、名称等核心数据。

---

### 2. `project_evaluation` - 项目评测记录表

| 字段名 | 类型 | 是否可空 | 默认值 | 描述 | 索引 |
|--------|------|----------|--------|------|------|
| **id** | int(11) | NO | - | 记录ID (主键) | PRIMARY |
| project_id | varchar(100) | NO | - | 项目ID | idx_project_id, unique_project_task |
| task_id | varchar(100) | YES | DEFAULT_TASK | 任务ID (支持多任务隔离) | idx_task_id, unique_project_task |
| status | varchar(50) | YES | IDLE | 评测状态 | idx_status |
| rules_config | text | YES | NULL | 规则配置 | - |
| evaluation_result | longtext | YES | NULL | 评测结果 (JSON格式) | - |
| check_date | varchar(20) | YES | NULL | 检查日期 (YYYY-MM-DD) | idx_project_evaluation_check_date |
| check_person_name | varchar(100) | YES | NULL | 检查人员姓名 | idx_project_evaluation_check_person |
| **check_name** | varchar(100) | YES | NULL | 检查人员姓名 (任务信息) | idx_project_evaluation_check_name |
| created_at | datetime | YES | CURRENT_TIMESTAMP | 创建时间 | - |
| updated_at | datetime | YES | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 | - |

**外键关系**:
- `project_id` → `project.id` (CASCADE DELETE)

**索引详情**:
- `unique_project_task` (project_id, task_id) - 确保项目+任务唯一性
- `idx_project_id` (project_id) - 项目ID索引
- `idx_task_id` (task_id) - 任务ID索引
- `idx_status` (status) - 状态索引
- `idx_project_evaluation_check_date` (check_date) - 检查日期索引
- `idx_project_evaluation_check_person` (check_person_name) - 检查人员索引
- `idx_project_evaluation_check_name` (check_name) - 任务检查人员索引

**数据统计**: 2条记录
**功能说明**: 存储项目评测的核心数据，支持任务级数据隔离，完整的检查信息记录。

---

### 3. `project_file` - 项目文件表

| 字段名 | 类型 | 是否可空 | 默认值 | 描述 | 索引 |
|--------|------|----------|--------|------|------|
| **id** | int(11) | NO | - | 文件ID (主键) | PRIMARY |
| project_id | varchar(100) | NO | - | 项目ID | idx_project_file |
| task_id | varchar(100) | YES | DEFAULT_TASK | 任务ID (支持多任务隔离) | idx_project_file |
| category_id | varchar(100) | YES | NULL | 分类ID | idx_category |
| category_name | varchar(255) | YES | NULL | 分类名称 | - |
| file_name | varchar(255) | YES | NULL | 文件名称 | - |
| file_url | varchar(1000) | YES | NULL | 文件URL | - |
| file_type | varchar(50) | YES | NULL | 文件类型 | - |
| file_hash | varchar(64) | YES | NULL | 文件哈希值 | idx_file_hash |
| parsed_content | longtext | YES | NULL | 解析后的文件内容 | - |
| update_time | datetime | YES | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 | - |

**外键关系**:
- `project_id` → `project.id` (CASCADE DELETE)

**索引详情**:
- `idx_project_file` (project_id, task_id) - 项目+任务复合索引
- `idx_category` (category_id) - 分类ID索引
- `idx_file_hash` (file_hash) - 文件哈希索引

**数据统计**: 187条记录
**功能说明**: 存储项目相关文件信息，支持任务级文件隔离，包含文件分类、哈希值等元数据。

---

### 4. `evaluation_templates` - 评测模板表

| 字段名 | 类型 | 是否可空 | 默认值 | 描述 | 索引 |
|--------|------|----------|--------|------|------|
| **id** | varchar(100) | NO | - | 模板ID (主键) | PRIMARY |
| template_name | varchar(255) | NO | - | 模板名称 | - |
| template_type | varchar(50) | NO | custom | 模板类型 | - |
| description | text | YES | NULL | 模板描述 | - |
| rules_config | text | YES | NULL | 规则配置 | - |
| is_active | tinyint(1) | YES | 1 | 是否启用 | - |
| created_by | varchar(100) | YES | NULL | 创建者 | - |
| created_at | datetime | YES | CURRENT_TIMESTAMP | 创建时间 | - |
| updated_at | datetime | YES | CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 | - |

**外键关系**: 无
**数据统计**: 0条记录 (系统表)
**功能说明**: 存储评测模板配置，支持不同类型的评测模板。

---

### 5. `document_categories` - 文档分类表

| 字段名 | 类型 | 是否可空 | 默认值 | 描述 | 索引 |
|--------|------|----------|--------|------|------|
| **id** | int(11) | NO | - | 分类ID (主键) | PRIMARY |
| category_id | varchar(100) | NO | - | 分类编码 (唯一) | category_id |
| category_name | varchar(255) | NO | - | 分类名称 | - |
| parent_category_id | varchar(100) | YES | NULL | 父分类ID | - |
| description | text | YES | NULL | 分类描述 | - |
| sort_order | int(11) | YES | 0 | 排序顺序 | - |
| is_active | tinyint(1) | YES | 1 | 是否启用 | - |
| created_at | datetime | YES | CURRENT_TIMESTAMP | 创建时间 | - |

**外键关系**: 无
**数据统计**: 0条记录 (系统表)
**功能说明**: 存储文档分类体系，支持层级分类结构。

---

## 🔗 表关系图

```
project (项目)
├── project_evaluation (1:N) - 评测记录
│   └── 通过 project_id 关联
├── project_file (1:N) - 项目文件
│   └── 通过 project_id 关联
└── task_id 隔离机制
    ├── project_evaluation.task_id
    └── project_file.task_id

evaluation_templates (独立)
document_categories (独立)
```

---

## 📊 数据统计总览

| 表名 | 记录数 | 说明 |
|------|--------|------|
| project | 22 | 活跃项目数量 |
| project_evaluation | 2 | 评测记录数 (2个不同任务) |
| project_file | 187 | 文件总数 |
| evaluation_templates | 0 | 系统模板 (预设) |
| document_categories | 0 | 系统分类 (预设) |

**总计**: 211条记录

---

## 🚀 核心特性

### 1. 任务级数据隔离
- **task_id机制**: 每个项目可以有多个独立的评测任务
- **数据安全**: 不同任务的数据完全隔离，避免互相干扰
- **并发支持**: 支持多个评测任务并行进行

### 2. 完整的人员信息
- **check_name**: 来自任务信息的检查人员
- **check_person_name**: 来自文件信息接口的人员
- **check_date**: 检查日期记录

### 3. 高性能索引设计
- **复合索引**: 针对常用查询组合优化
- **唯一约束**: 防止重复数据
- **外键约束**: 保证数据完整性

### 4. 灵活的配置系统
- **JSON存储**: evaluation_result 支持复杂的评测结果数据
- **规则配置**: rules_config 字段支持动态规则调整
- **模板系统**: evaluation_templates 支持多种评测模板

---

## 📝 使用建议

### 查询优化
1. **按项目查询**: 使用 `project_id` 索引
2. **按任务查询**: 使用 `task_id` 索引
3. **按状态查询**: 使用 `status` 索引
4. **文件去重**: 使用 `file_hash` 索引

### 数据一致性
1. **外键约束**: 自动保证关联数据完整性
2. **唯一约束**: 防止重复的评测记录
3. **级联删除**: 删除项目时自动清理相关数据

### 扩展性考虑
1. **字符集**: 使用 utf8mb4 支持完整Unicode字符
2. **时间戳**: 自动维护创建和更新时间
3. **JSON字段**: 支持灵活的数据结构扩展

---

**文档版本**: v1.0
**生成时间**: 2025-12-04
**数据库名**: ai_doc_review