# MySQL MCP工具使用说明

## 概述

MySQL MCP工具是一套用于连接和分析lotto_3d数据库的工具集。它提供了数据库连接、查询执行、表信息获取和数据库分析等功能。

## 工具组件

### 1. 配置文件 (`mysql_mcp_config.json`)

包含数据库连接配置和工具定义：

```json
{
  "connection": {
    "host": "127.0.0.1",
    "port": 3306,
    "username": "root",
    "password": "sw63828",
    "database": "lotto_3d",
    "charset": "utf8mb4"
  }
}
```

### 2. 核心工具类 (`mysql_mcp_server.py`)

实现了以下功能：

1. **connect_database**: 连接数据库
2. **execute_query**: 执行SQL查询
3. **get_table_info**: 获取表信息
4. **analyze_database**: 分析数据库

## 使用方法

### 1. 连接数据库

```python
from mysql_mcp_server import MySQLMCPTool

mcp_tool = MySQLMCPTool()
result = mcp_tool.connect_database()
```

### 2. 执行查询

```python
# 简单查询
result = mcp_tool.execute_query("SELECT COUNT(*) as total FROM lottery_results")

# 带参数查询
result = mcp_tool.execute_query(
    "SELECT * FROM lottery_results WHERE issue_name = :issue", 
    {"issue": "2025253"}
)
```

### 3. 获取表信息

```python
# 获取表结构和行数
result = mcp_tool.get_table_info("lottery_results")
```

### 4. 分析数据库

```python
# 分析表结构
structure_result = mcp_tool.analyze_database("structure")

# 分析表数据
data_result = mcp_tool.analyze_database("data")

# 全面分析
full_result = mcp_tool.analyze_database("all")
```

## 数据库结构

### 主要数据表

1. **lottery_results**: 开奖结果表
   - 存储历史开奖数据
   - 包含期号、开奖号码、和值、跨度等信息

2. **expert_info**: 专家信息表
   - 存储专家ID和昵称

3. **expert_predictions**: 专家预测表
   - 存储专家的预测数据

4. **expert_hit_stat**: 专家命中统计表
   - 存储专家预测的命中统计信息

5. **playtype_dict**: 玩法字典表
   - 存储各种玩法的定义

6. **red_val_list_v2**: 红球权重表
   - 存储号码权重和统计信息

## 数据分析示例

### 开奖数据统计

- 总期数: 8期
- 和值范围: 10-25
- 跨度范围: 2-9

### 专家表现

- 专家总数: 1500人
- 预测准确率: 约31.43%
- 表现最佳专家: 蛋蛋 (命中率64%)

### 玩法分布

- 共23种玩法
- 最热门玩法: 定位4*4*4系列

## 运行演示

执行以下命令查看工具演示：

```bash
python3 mysql_mcp_server.py
```

## 扩展使用

可以根据需要扩展工具功能：

1. 添加新的查询模板
2. 实现更复杂的数据分析功能
3. 增加数据导出功能
4. 添加数据可视化功能

## 注意事项

1. 确保数据库服务正在运行
2. 检查连接配置是否正确
3. 注意SQL注入风险，使用参数化查询
4. 大数据量查询时注意性能优化