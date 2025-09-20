#!/usr/bin/env python3
"""
数据库分析脚本
用于连接和分析lotto_3d数据库
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings
from db.connection import query_db


def test_connection():
    """测试数据库连接"""
    try:
        # 简单查询测试连接
        result = query_db("SELECT 1 as connection_test")
        print("✓ 数据库连接成功!")
        print(f"测试查询结果: {result}")
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def get_table_info():
    """获取数据库表信息"""
    try:
        # 查询所有表名
        tables = query_db("SHOW TABLES")
        print("\n数据库中的表:")
        table_names = []
        for table in tables:
            table_name = list(table.values())[0]
            table_names.append(table_name)
            print(f"  - {table_name}")

        # 获取每个表的行数
        print("\n各表数据行数:")
        for table_name in table_names:
            count_result = query_db(f"SELECT COUNT(*) as count FROM `{table_name}`")
            count = count_result[0]["count"] if count_result else 0
            print(f"  - {table_name}: {count} 行")

        return table_names
    except Exception as e:
        print(f"获取表信息时出错: {e}")
        return []


def analyze_lottery_results():
    """分析lottery_results表"""
    try:
        # 获取最新几期的数据
        latest_results = query_db("SELECT * FROM lottery_results ORDER BY issue_name DESC LIMIT 5")
        print("\n最新的5期开奖数据:")
        for result in latest_results:
            print(
                f"  期号: {result['issue_name']}, 开奖号码: {result['open_code']}, "
                f"和值: {result['sum']}, 跨度: {result['span']}"
            )

        # 获取总期数
        count_result = query_db("SELECT COUNT(*) as total FROM lottery_results")
        total = count_result[0]["total"] if count_result else 0
        print(f"\n总期数: {total}")

        # 获取开奖时间范围
        time_range = query_db(
            "SELECT MIN(open_time) as earliest, MAX(open_time) as latest FROM lottery_results"
        )
        if time_range:
            print(f"开奖时间范围: {time_range[0]['earliest']} 到 {time_range[0]['latest']}")

    except Exception as e:
        print(f"分析开奖数据时出错: {e}")


def analyze_expert_data():
    """分析专家数据"""
    try:
        # 获取专家数量
        expert_count = query_db("SELECT COUNT(*) as count FROM expert_info")
        count = expert_count[0]["count"] if expert_count else 0
        print(f"\n专家总数: {count}")

        # 获取专家预测数据统计
        prediction_stats = query_db(
            "SELECT COUNT(*) as total_predictions, COUNT(DISTINCT user_id) as experts_made_predictions "
            "FROM expert_predictions"
        )
        if prediction_stats:
            print(f"预测数据总条数: {prediction_stats[0]['total_predictions']}")
            print(f"发布过预测的专家数: {prediction_stats[0]['experts_made_predictions']}")

        # 获取热门玩法
        playtype_stats = query_db(
            "SELECT playtype_id, COUNT(*) as count FROM expert_predictions "
            "GROUP BY playtype_id ORDER BY count DESC LIMIT 5"
        )
        print("\n热门玩法 (预测次数最多的前5种):")
        for stat in playtype_stats:
            print(f"  玩法ID {stat['playtype_id']}: {stat['count']} 次预测")

    except Exception as e:
        print(f"分析专家数据时出错: {e}")


def main():
    """主函数"""
    print("=== Lotto 3D 数据库分析工具 ===")

    # 加载设置
    try:
        settings = get_settings()
        print(f"数据库URL: {settings.database.url}")
    except Exception as e:
        print(f"加载配置时出错: {e}")
        return

    # 测试连接
    if not test_connection():
        return

    # 获取表信息
    tables = get_table_info()

    # 分析主要数据表
    if "lottery_results" in tables:
        analyze_lottery_results()

    if "expert_info" in tables and "expert_predictions" in tables:
        analyze_expert_data()

    print("\n=== 分析完成 ===")


if __name__ == "__main__":
    main()
