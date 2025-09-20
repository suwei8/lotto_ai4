from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")
from itertools import permutations

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes
from utils.ui import issue_picker, playtype_picker, render_open_info
from utils.numbers import parse_tokens


def _normalize_combo(tokens: List[str]) -> str:
    return "".join(sorted(tokens))


def _digits_from_tokens(tokens: List[str]) -> List[int]:
    digits: List[int] = []
    for token in tokens:
        for char in token:
            if char.isdigit():
                digits.append(int(char))
    return digits


st.header("NumberAnalysis - 号码组合分析")

selected_issue = issue_picker(
    "number_analysis_issue",
    mode="single",
    label="选择期号",
)
if not selected_issue:
    st.stop()

render_open_info(selected_issue, key="number_analysis_open", show_metrics=False)

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtypes["id"] = playtypes["playtype_id"].astype(str)
playtype_map = dict(zip(playtypes["id"], playtypes["playtype_name"].astype(str)))
default_playtype = next(
    (pid for pid, name in playtype_map.items() if name == "三胆"),
    playtypes["id"].iloc[0],
)
selected_playtype = playtype_picker(
    "number_analysis_playtype",
    mode="single",
    label="选择玩法",
    include=playtypes["id"].tolist(),
    default=default_playtype,
)
if not selected_playtype:
    st.stop()

sql = """
    SELECT user_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue_name
      AND playtype_id = :playtype_id
"""
params = {"issue_name": selected_issue, "playtype_id": int(selected_playtype)}

try:
    rows = cached_query(query_db, sql, params=params, ttl=120)
except Exception as exc:
    st.warning(f"查询推荐数据失败：{exc}")
    rows = []

if not rows:
    st.info("当前条件下未获取到推荐数据。")
    st.stop()

raw_df = pd.DataFrame(rows)
raw_df["tokens"] = raw_df["numbers"].apply(parse_tokens)
raw_df["combo_key"] = raw_df["tokens"].apply(_normalize_combo)

combo_df = (
    raw_df.groupby("combo_key")
    .agg(
        count=("user_id", "nunique"),
        sample_numbers=("numbers", "first"),
        tokens=("tokens", "first"),
    )
    .reset_index()
)
combo_df["digits"] = combo_df["tokens"].apply(_digits_from_tokens)
combo_df["sum_digits"] = combo_df["digits"].apply(sum)
combo_df["span"] = combo_df["digits"].apply(
    lambda values: max(values) - min(values) if values else 0
)
combo_df["odd_count"] = combo_df["digits"].apply(
    lambda values: sum(1 for v in values if v % 2 == 1)
)
combo_df["even_count"] = combo_df["digits"].apply(
    lambda values: sum(1 for v in values if v % 2 == 0)
)
combo_df["odd_even_ratio"] = combo_df.apply(
    lambda row: f"{row['odd_count']}:{row['even_count']}", axis=1
)
combo_df["big_count"] = combo_df["digits"].apply(
    lambda values: sum(1 for v in values if v >= 5)
)
combo_df["small_count"] = combo_df["digits"].apply(
    lambda values: sum(1 for v in values if v < 5)
)
combo_df["big_small_ratio"] = combo_df.apply(
    lambda row: f"{row['big_count']}:{row['small_count']}", axis=1
)
combo_df.sort_values(by="count", ascending=False, inplace=True)
combo_df.reset_index(drop=True, inplace=True)

count_min = int(combo_df["count"].min())
count_max = int(combo_df["count"].max())
selected_count = st.slider(
    "出现次数范围",
    min_value=count_min,
    max_value=count_max,
    value=(count_min, count_max),
)

digits_options = [str(i) for i in range(10)]
sum_options = sorted(combo_df["sum_digits"].unique().tolist())
span_options = sorted(combo_df["span"].unique().tolist())
odd_even_options = sorted(combo_df["odd_even_ratio"].unique().tolist())
big_small_options = sorted(combo_df["big_small_ratio"].unique().tolist())

with st.expander("过滤器", expanded=False):
    row1 = st.columns(3)
    with row1[0]:
        excluded_digits = st.multiselect(
            "排除包含以下数字", options=digits_options, key="filter_excluded_digits"
        )
    with row1[1]:
        excluded_sums = st.multiselect(
            "排除包含以下和值", options=sum_options, key="filter_excluded_sums"
        )
    with row1[2]:
        excluded_spans = st.multiselect(
            "排除包含以下跨度", options=span_options, key="filter_excluded_spans"
        )

    row2 = st.columns(3)
    with row2[0]:
        excluded_odd_even = st.multiselect(
            "排除包含以下奇偶比", options=odd_even_options, key="filter_excluded_odd_even"
        )
    with row2[1]:
        excluded_big_small = st.multiselect(
            "排除含以下大小比", options=big_small_options, key="filter_excluded_big_small"
        )
    with row2[2]:
        include_digits = st.multiselect(
            "筛选包含以下数字", options=digits_options, key="filter_include_digits"
        )

filtered_df = combo_df[
    combo_df["count"].between(selected_count[0], selected_count[1])
].copy()

if excluded_digits:
    excluded_set = set(excluded_digits)
    filtered_df = filtered_df[
        ~filtered_df["digits"].apply(
            lambda digits: bool(excluded_set.intersection({str(d) for d in digits}))
        )
    ]

if include_digits:
    include_set = set(include_digits)
    filtered_df = filtered_df[
        filtered_df["digits"].apply(
            lambda digits: include_set.issubset({str(d) for d in digits})
        )
    ]

if excluded_sums:
    filtered_df = filtered_df[~filtered_df["sum_digits"].isin(excluded_sums)]

if excluded_spans:
    filtered_df = filtered_df[~filtered_df["span"].isin(excluded_spans)]

if excluded_odd_even:
    filtered_df = filtered_df[
        ~filtered_df["odd_even_ratio"].isin(excluded_odd_even)
    ]

if excluded_big_small:
    filtered_df = filtered_df[
        ~filtered_df["big_small_ratio"].isin(excluded_big_small)
    ]

summary_table = filtered_df[["combo_key", "count"]].copy()
summary_table.rename(columns={"combo_key": "号码组合", "count": "出现次数"}, inplace=True)

st.subheader(f"组合统计（共 {len(summary_table)} 个）")
if summary_table.empty:
    st.info("当前过滤条件下无组合可展示。")
else:
    st.dataframe(summary_table, width="stretch")

if not summary_table.empty:
    search_term = st.text_input("🔍 查找特定号码组合")
    if search_term:
        query = search_term.strip()
        if query:
            matches = summary_table[
                summary_table["号码组合"].str.contains(query, regex=False)
            ]
            if matches.empty:
                st.info("未找到匹配的组合。")
            else:
                st.dataframe(matches, width="stretch")

    bet_code_text = ",".join(summary_table["号码组合"].tolist())
    bet_count = len(summary_table)

    st.markdown("### ✏️ 投注号码（可复制）")
    col_group, col_direct = st.columns(2)
    with col_group:
        group_multiplier = st.number_input(
            "组选倍数",
            min_value=0,
            value=1,
            step=1,
            key="number_analysis_group_multiplier",
        )
    with col_direct:
        direct_multiplier = st.number_input(
            "直选倍数",
            min_value=0,
            value=1,
            step=1,
            key="number_analysis_direct_multiplier",
        )

    group_count = bet_count * group_multiplier
    direct_count = bet_count * direct_multiplier
    total_count = group_count + direct_count
    cost = total_count * 2
    bonus = group_multiplier * 280 + direct_multiplier * 1700
    profit = bonus - cost

    st.text_area(
        "投注内容",
        f"{bet_code_text} 共{bet_count}注，组选{group_multiplier}倍，直选{direct_multiplier}倍 {cost}元",
        height=80,
    )
    st.markdown(
        f"**投注注数：{total_count} 注（组选 {group_count} 注 + 直选 {direct_count} 注）**"
    )
    st.markdown(f"**投注成本：{cost} 元**")
    st.markdown(
        f"**奖金合计：{bonus} 元（假设组选与直选各命中1注）**"
    )
    st.markdown(
        f"**纯收益：{'盈利' if profit >= 0 else '亏损'} {abs(profit)} 元**"
    )

    with st.expander("🎯 号码组合全排列转换（适用于组选）", expanded=False):
        enable_permutation = st.checkbox(
            "启用全排列（如123 → 123,132,213,231,312,321）",
            value=True,
            key="number_analysis_enable_permutation",
        )
        if enable_permutation:
            permuted_numbers = set()
            for code in summary_table["号码组合"].tolist():
                for perm in permutations(code):
                    permuted_numbers.add("".join(perm))

            permuted_numbers = sorted(permuted_numbers)
            perm_count = len(permuted_numbers)
            perm_text = ",".join(permuted_numbers)

            col_perm_group, col_perm_direct = st.columns(2)
            with col_perm_group:
                perm_group_multiplier = st.number_input(
                    "组选倍数（排列模块）",
                    min_value=0,
                    value=1,
                    step=1,
                    key="number_analysis_perm_group_multiplier",
                )
            with col_perm_direct:
                perm_direct_multiplier = st.number_input(
                    "直选倍数（排列模块）",
                    min_value=0,
                    value=1,
                    step=1,
                    key="number_analysis_perm_direct_multiplier",
                )

            perm_group_count = perm_count * perm_group_multiplier
            perm_direct_count = perm_count * perm_direct_multiplier
            perm_total_count = perm_group_count + perm_direct_count
            perm_cost = perm_total_count * 2
            perm_bonus = perm_group_multiplier * 280 + perm_direct_multiplier * 1700
            perm_profit = perm_bonus - perm_cost

            st.text_area(
                "排列后的投注号码",
                f"{perm_text} 共{perm_count}注，组选{perm_group_multiplier}倍，直选{perm_direct_multiplier}倍 {perm_cost}元",
                height=100,
            )
            st.markdown(
                f"**投注注数：{perm_total_count} 注（组选 {perm_group_count} 注 + 直选 {perm_direct_count} 注）**"
            )
            st.markdown(f"**投注成本：{perm_cost} 元**")
            st.markdown(
                f"**奖金合计：{perm_bonus} 元（假设组选与直选各命中1注）**"
            )
            st.markdown(
                f"**纯收益：{'盈利' if perm_profit >= 0 else '亏损'} {abs(perm_profit)} 元**"
            )
