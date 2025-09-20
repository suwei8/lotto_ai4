#!/usr/bin/env python3
"""
详细数据库分析脚本
用于深入分析lotto_3d数据库的结构和数据
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import query_db


def analyze_table_structure():
    """分析表结构"""
    print("=== 数据库表结构分析 ===")

    # 获取所有表名
    tables = query_db("SHOW TABLES")
    table_names = [list(table.values())[0] for table in tables]

    for table_name in table_names:
        print(f"\n表名: {table_name}")
        # 获取表结构
        columns = query_db(f"DESCRIBE `{table_name}`")
        print("  字段结构:")
        for col in columns:
            print(
                f"    {col['Field']}: {col['Type']} ({'NULL' if col['Null'] == 'YES' else 'NOT NULL'})"
            )
            if col["Key"]:
                print(f"      键: {col['Key']}")
            if col["Default"] is not None:
                print(f"      默认值: {col['Default']}")


def analyze_lottery_results_detailed():
    """详细分析开奖数据"""
    print("\n=== 开奖数据详细分析 ===")

    # 和值统计
    sum_stats = query_db(
        "SELECT MIN(sum) as min_sum, MAX(sum) as max_sum, AVG(sum) as avg_sum FROM lottery_results"
    )
    if sum_stats:
        print(f"和值范围: {sum_stats[0]['min_sum']} - {sum_stats[0]['max_sum']}")
        print(f"平均和值: {sum_stats[0]['avg_sum']:.2f}")

    # 跨度统计
    span_stats = query_db(
        "SELECT MIN(span) as min_span, MAX(span) as max_span, AVG(span) as avg_span FROM lottery_results"
    )
    if span_stats:
        print(f"跨度范围: {span_stats[0]['min_span']} - {span_stats[0]['max_span']}")
        print(f"平均跨度: {span_stats[0]['avg_span']:.2f}")

    # 开奖号码分布
    print("\n开奖号码分布:")
    for position in range(3):  # 福彩3D有3个号码
        numbers = query_db(
            f"SELECT SUBSTRING_INDEX(SUBSTRING_INDEX(open_code, ',', {position+1}), ',', -1) as num, "
            f"COUNT(*) as count FROM lottery_results GROUP BY num ORDER BY num"
        )
        print(f"  第{position+1}位号码:")
        for num in numbers:
            print(f"    号码 {num['num']}: {num['count']} 次")


def analyze_expert_predictions():
    """分析专家预测数据"""
    print("\n=== 专家预测数据分析 ===")

    # 预测准确率统计
    accuracy_stats = query_db(
        """
        SELECT 
            COUNT(*) as total_predictions,
            SUM(CASE WHEN e.hit_count > 0 THEN 1 ELSE 0 END) as correct_predictions,
            AVG(e.hit_count) as avg_hits
        FROM expert_hit_stat e
    """
    )

    if accuracy_stats:
        total = accuracy_stats[0]["total_predictions"]
        correct = accuracy_stats[0]["correct_predictions"]
        avg_hits = accuracy_stats[0]["avg_hits"]
        accuracy = (correct / total * 100) if total > 0 else 0
        print(f"总预测次数: {total}")
        print(f"命中预测次数: {correct}")
        print(f"预测准确率: {accuracy:.2f}%")
        print(f"平均命中数: {avg_hits:.2f}")

    # 专家表现排行
    expert_ranking = query_db(
        """
        SELECT 
            e.user_id,
            ei.nick_name,
            COUNT(*) as prediction_count,
            SUM(e.hit_count) as total_hits,
            AVG(e.hit_count) as avg_hits
        FROM expert_hit_stat e
        JOIN expert_info ei ON e.user_id = ei.user_id
        GROUP BY e.user_id, ei.nick_name
        ORDER BY total_hits DESC
        LIMIT 10
    """
    )

    print("\n专家命中排行 (前10名):")
    for i, expert in enumerate(expert_ranking, 1):
        print(f"  {i}. {expert['nick_name']} (ID: {expert['user_id']})")
        print(
            f"     预测次数: {expert['prediction_count']}, 总命中: {expert['total_hits']}, 平均命中: {expert['avg_hits']:.2f}"
        )


def analyze_playtype():
    """分析玩法类型"""
    print("\n=== 玩法类型分析 ===")

    # 获取所有玩法
    playtypes = query_db("SELECT * FROM playtype_dict")
    print("玩法类型:")
    for playtype in playtypes:
        print(f"  ID {playtype['playtype_id']}: {playtype['playtype_name']}")

    # 各玩法的预测分布
    playtype_distribution = query_db(
        """
        SELECT 
            p.playtype_id,
            pd.playtype_name,
            COUNT(*) as prediction_count
        FROM expert_predictions p
        JOIN playtype_dict pd ON p.playtype_id = pd.playtype_id
        GROUP BY p.playtype_id, pd.playtype_name
        ORDER BY prediction_count DESC
    """
    )

    print("\n各玩法预测分布:")
    for playtype in playtype_distribution:
        print(
            f" {playtype['playtype_name']} (ID: {playtype['playtype_id']}): {playtype['prediction_count']} 次预测"
        )


def analyze_red_val_list():
    """分析红球权重数据"""
    print("\n=== 红球权重数据分析 ===")

    # 红球权重数据统计
    red_val_stats = query_db(
        """
        SELECT 
            COUNT(*) as total_records,
            COUNT(DISTINCT user_id) as experts_count,
            COUNT(DISTINCT issue_name) as issues_count
        FROM red_val_list_v2
    """
    )

    if red_val_stats:
        stats = red_val_stats[0]
        print(f"红球权重数据记录数: {stats['total_records']}")
        print(f"涉及专家数: {stats['experts_count']}")
        print(f"涉及期数: {stats['issues_count']}")

    # 权重类型分布
    type_distribution = query_db(
        """
        SELECT 
            type,
            COUNT(*) as count
        FROM red_val_list_v2
        WHERE type IS NOT NULL
        GROUP BY type
        ORDER BY type
    """
    )

    print("\n权重类型分布:")
    type_names = {
        1: "命中率",
        2: "当前红连",
        3: "历史最高红连",
        4: "综合排名",
        5: "当前连黑",
        6: "历史最高连黑",
    }

    for item in type_distribution:
        type_name = type_names.get(item["type"], f"未知类型({item['type']})")
        print(f"  {type_name}: {item['count']} 条记录")


def main():
    """主函数"""
    print("=== Lotto 3D 数据库详细分析工具 ===")

    try:
        # 测试连接
        query_db("SELECT 1 as connection_test")
        print("✓ 数据库连接成功!")

        # 执行各项分析
        analyze_table_structure()
        analyze_lottery_results_detailed()
        analyze_expert_predictions()
        analyze_playtype()
        analyze_red_val_list()

        print("\n=== 详细分析完成 ===")

    except Exception as e:
        print(f"✗ 分析过程中出错: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
