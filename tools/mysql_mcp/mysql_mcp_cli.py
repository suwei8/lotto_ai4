#!/usr/bin/env python3
"""
MySQL MCP命令行工具
提供简单的命令行界面来使用MCP工具
"""

import argparse
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mysql_mcp_server import MySQLMCPTool


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="MySQL MCP工具命令行界面")
    parser.add_argument(
        "command", choices=["connect", "query", "table", "analyze"], help="要执行的命令"
    )
    parser.add_argument("--query", "-q", help="SQL查询语句")
    parser.add_argument("--table", "-t", help="表名")
    parser.add_argument(
        "--type", choices=["structure", "data", "all"], default="all", help="分析类型"
    )
    parser.add_argument("--format", choices=["json", "pretty"], default="pretty", help="输出格式")

    args = parser.parse_args()

    # 创建MCP工具实例
    mcp_tool = MySQLMCPTool()

    # 执行相应命令
    if args.command == "connect":
        result = mcp_tool.connect_database()
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("数据库连接测试:")
            print(f"  状态: {'成功' if result['success'] else '失败'}")
            if result["success"]:
                print(f"  主机: {result['connection_info']['host']}")
                print(f"  端口: {result['connection_info']['port']}")
                print(f"  数据库: {result['connection_info']['database']}")
            else:
                print(f"  错误: {result['message']}")

    elif args.command == "query":
        if not args.query:
            print("错误: 执行查询命令需要提供--query参数")
            sys.exit(1)

        result = mcp_tool.execute_query(args.query)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("查询结果:")
            print(f"  状态: {'成功' if result['success'] else '失败'}")
            if result["success"]:
                print(f"  行数: {result['row_count']}")
                print("  数据:")
                for row in result["data"]:
                    print(f"    {row}")
            else:
                print(f"  错误: {result['message']}")

    elif args.command == "table":
        if not args.table:
            print("错误: 获取表信息命令需要提供--table参数")
            sys.exit(1)

        result = mcp_tool.get_table_info(args.table)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"表 '{args.table}' 信息:")
            print(f"  状态: {'成功' if result['success'] else '失败'}")
            if result["success"]:
                print(f"  行数: {result['row_count']}")
                print("  字段结构:")
                for col in result["columns"]:
                    print(
                        f"    {col['Field']}: {col['Type']} ({'NULL' if col['Null'] == 'YES' else 'NOT NULL'})"
                    )
            else:
                print(f"  错误: {result['message']}")

    elif args.command == "analyze":
        result = mcp_tool.analyze_database(args.type)
        if args.format == "json":
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"数据库分析 ({args.type}):")
            print(f"  状态: {'成功' if result['success'] else '失败'}")
            if result["success"]:
                if "table_structures" in result:
                    print("  表结构:")
                    for table_name, columns in result["table_structures"].items():
                        print(f"    {table_name}: {len(columns)} 个字段")

                if "table_stats" in result:
                    print("  表统计:")
                    for table_name, stats in result["table_stats"].items():
                        print(f"    {table_name}: {stats['row_count']} 行")
            else:
                print(f"  错误: {result['message']}")


if __name__ == "__main__":
    main()
