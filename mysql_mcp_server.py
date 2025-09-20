#!/usr/bin/env python3
"""
MySQL MCP服务器实现
用于连接和分析lotto_3d数据库
"""

import json
import os
import sys
from typing import Any, Dict

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import query_db


class MySQLMCPTool:
    """MySQL MCP工具类"""

    def __init__(self):
        """初始化工具"""
        self.connection = None
        self.config = {
            "host": "127.0.0.1",
            "port": 3306,
            "username": "root",
            "password": "sw63828",
            "database": "lotto_3d",
            "charset": "utf8mb4",
        }

    def connect_database(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        database: str = None,
    ) -> Dict[str, Any]:
        """
        连接到MySQL数据库

        Args:
            host: 数据库主机地址
            port: 数据库端口
            username: 数据库用户名
            password: 数据库密码
            database: 数据库名称

        Returns:
            连接结果字典
        """
        try:
            # 使用传入的参数或默认配置
            conn_config = {
                "host": host or self.config["host"],
                "port": port or self.config["port"],
                "user": username or self.config["username"],
                "password": password or self.config["password"],
                "database": database or self.config["database"],
                "charset": self.config["charset"],
            }

            # 测试连接
            result = query_db("SELECT 1 as connection_test")
            if result and result[0]["connection_test"] == 1:
                return {
                    "success": True,
                    "message": "数据库连接成功",
                    "connection_info": {
                        "host": conn_config["host"],
                        "port": conn_config["port"],
                        "database": conn_config["database"],
                    },
                }
            else:
                return {"success": False, "message": "数据库连接失败"}

        except Exception as e:
            return {"success": False, "message": f"数据库连接出错: {str(e)}"}

    def execute_query(self, query: str, parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行SQL查询

        Args:
            query: SQL查询语句
            parameters: 查询参数

        Returns:
            查询结果字典
        """
        try:
            result = query_db(query, parameters)
            return {"success": True, "data": result, "row_count": len(result) if result else 0}
        except Exception as e:
            return {"success": False, "message": f"查询执行出错: {str(e)}", "query": query}

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        获取表信息

        Args:
            table_name: 表名

        Returns:
            表信息字典
        """
        try:
            # 获取表结构
            columns = query_db(f"DESCRIBE `{table_name}`")

            # 获取表行数
            count_result = query_db(f"SELECT COUNT(*) as count FROM `{table_name}`")
            row_count = count_result[0]["count"] if count_result else 0

            return {
                "success": True,
                "table_name": table_name,
                "row_count": row_count,
                "columns": columns,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"获取表信息出错: {str(e)}",
                "table_name": table_name,
            }

    def analyze_database(self, analysis_type: str = "all") -> Dict[str, Any]:
        """
        分析数据库结构和数据

        Args:
            analysis_type: 分析类型 (structure, data, all)

        Returns:
            分析结果字典
        """
        try:
            result = {"success": True, "analysis_type": analysis_type}

            # 获取所有表名
            tables = query_db("SHOW TABLES")
            table_names = [list(table.values())[0] for table in tables]

            if analysis_type in ["structure", "all"]:
                # 分析表结构
                table_structures = {}
                for table_name in table_names:
                    columns = query_db(f"DESCRIBE `{table_name}`")
                    table_structures[table_name] = columns

                result["table_structures"] = table_structures

            if analysis_type in ["data", "all"]:
                # 分析表数据
                table_stats = {}
                for table_name in table_names:
                    # 获取表行数
                    count_result = query_db(f"SELECT COUNT(*) as count FROM `{table_name}`")
                    row_count = count_result[0]["count"] if count_result else 0

                    # 获取表的基本信息
                    table_stats[table_name] = {"row_count": row_count}

                result["table_stats"] = table_stats

            return result

        except Exception as e:
            return {
                "success": False,
                "message": f"数据库分析出错: {str(e)}",
                "analysis_type": analysis_type,
            }


def main():
    """主函数 - 演示MCP工具的使用"""
    print("=== MySQL MCP服务器演示 ===")

    # 创建MCP工具实例
    mcp_tool = MySQLMCPTool()

    # 测试数据库连接
    print("\n1. 测试数据库连接:")
    connect_result = mcp_tool.connect_database()
    print(json.dumps(connect_result, ensure_ascii=False, indent=2))

    # 执行简单查询
    print("\n2. 执行简单查询:")
    query_result = mcp_tool.execute_query("SELECT COUNT(*) as total FROM lottery_results")
    print(json.dumps(query_result, ensure_ascii=False, indent=2))

    # 获取表信息
    print("\n3. 获取表信息:")
    table_info = mcp_tool.get_table_info("lottery_results")
    print(json.dumps(table_info, ensure_ascii=False, indent=2))

    # 分析数据库结构
    print("\n4. 分析数据库结构:")
    structure_analysis = mcp_tool.analyze_database("structure")
    print(json.dumps(structure_analysis, ensure_ascii=False, indent=2))

    # 分析数据库数据
    print("\n5. 分析数据库数据:")
    data_analysis = mcp_tool.analyze_database("data")
    print(json.dumps(data_analysis, ensure_ascii=False, indent=2))

    print("\n=== MCP服务器演示完成 ===")


if __name__ == "__main__":
    main()
