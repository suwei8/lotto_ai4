from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info
from utils.ui import issue_picker

st.set_page_config(page_title="Lotto AI", layout="wide")

st.header("Playtype_CombinationView - 三位定1组合预览")

selected_issue = issue_picker(
    "comb_view_issue",
    mode="single",
    label="期号",
)
if not selected_issue:
    st.stop()

lottery_info = fetch_lottery_info(selected_issue)
if lottery_info:
    st.caption(
        f"开奖号码：{lottery_info.get('open_code') or '未开奖'}丨和值：{lottery_info.get('sum')}丨跨度：{lottery_info.get('span')}"
    )

sql = """
    SELECT
        p.user_id,
        MAX(CASE WHEN pd.playtype_name = '百位定1' THEN p.numbers ELSE '' END) AS bai,
        MAX(CASE WHEN pd.playtype_name = '十位定1' THEN p.numbers ELSE '' END) AS shi,
        MAX(CASE WHEN pd.playtype_name = '个位定1' THEN p.numbers ELSE '' END) AS ge
    FROM expert_predictions p
    JOIN playtype_dict pd ON pd.playtype_id = p.playtype_id
    WHERE p.issue_name = :issue
      AND pd.playtype_name IN ('百位定1', '十位定1', '个位定1')
    GROUP BY p.user_id
"""
rows = cached_query(query_db, sql, params={"issue": selected_issue}, ttl=120)
if not rows:
    st.info("当前期号下未找到定1玩法的组合。")
    st.stop()

df = pd.DataFrame(rows)
df["组合结果"] = df[["bai", "shi", "ge"]].fillna("").agg("".join, axis=1)
df = df[df["组合结果"].str.len() == 3]
if df.empty:
    st.info("未汇总到有效的三位定1组合。")
    st.stop()

df.rename(
    columns={"user_id": "AI-ID", "bai": "百位定1", "shi": "十位定1", "ge": "个位定1"}, inplace=True
)

keyword = st.text_input("🔍 搜索组合（按数字，忽略顺序）").strip()
if keyword:
    if keyword.isdigit():
        keyword_counter = Counter(keyword)
        df = df[df["组合结果"].apply(lambda x: Counter(x) == keyword_counter)]
    else:
        st.warning("请输入数字组合。")

st.markdown(f"### 共找到 {len(df)} 位 AI 的组合推荐")
st.dataframe(df, use_container_width=True)

freq_df = df["组合结果"].value_counts().reset_index()
freq_df.columns = ["号码组合", "出现次数"]


def classify(combo: str) -> str:
    if len(combo) != 3 or not combo.isdigit():
        return "未知"
    counts = Counter(combo)
    if len(counts) == 1:
        return "豹子"
    if len(counts) == 2:
        return "组三"
    ordered = sorted(map(int, combo))
    if ordered in (
        [0, 1, 2],
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
        [4, 5, 6],
        [5, 6, 7],
        [6, 7, 8],
        [7, 8, 9],
    ):
        return "顺子"
    return "组六"


freq_df["组合类型"] = freq_df["号码组合"].apply(classify)

st.markdown("### 组合筛选")
columns = st.columns([1, 1, 1, 1])
with columns[0]:
    exclude_types = st.multiselect(
        "排除组选类型", ["组六", "组三", "豹子", "顺子"], key="comb_view_exclude_types"
    )
with columns[1]:
    all_digits = [str(i) for i in range(10)]
    exclude_digits = st.multiselect(
        "排除包含以下数字", options=all_digits, key="comb_view_exclude_digits"
    )
with columns[2]:
    include_digits = st.multiselect(
        "仅保留包含以下数字", options=all_digits, key="comb_view_include_digits"
    )
with columns[3]:
    remove_permutations = st.checkbox("过滤重复组合（忽略顺序）", key="comb_view_remove_perms")

if not freq_df.empty:
    min_count, max_count = freq_df["出现次数"].min(), freq_df["出现次数"].max()
    selected_range = st.slider(
        "组合出现次数范围",
        min_value=int(min_count),
        max_value=int(max_count),
        value=(int(min_count), int(max_count)),
    )
else:
    selected_range = (0, 0)

filtered_df = freq_df.copy()
if exclude_types:
    filtered_df = filtered_df[~filtered_df["组合类型"].isin(exclude_types)]
if exclude_digits:
    filtered_df = filtered_df[
        ~filtered_df["号码组合"].apply(lambda combo: any(d in combo for d in exclude_digits))
    ]
if include_digits:
    include_set = set(include_digits)
    filtered_df = filtered_df[
        filtered_df["号码组合"].apply(lambda combo: include_set.issubset(set(combo)))
    ]
filtered_df = filtered_df[
    (filtered_df["出现次数"] >= selected_range[0]) & (filtered_df["出现次数"] <= selected_range[1])
]
if remove_permutations and not filtered_df.empty:
    filtered_df["组合Key"] = filtered_df["号码组合"].apply(lambda combo: "".join(sorted(combo)))
    filtered_df = filtered_df.drop_duplicates(subset=["组合Key"])
    filtered_df = filtered_df.drop(columns=["组合Key"])

st.markdown(f"### 号码组合统计（共 {len(filtered_df)} 个）")
st.dataframe(filtered_df[["号码组合", "出现次数", "组合类型"]], use_container_width=True)

with st.expander("🔍 查找特定号码组合", expanded=False):
    target = st.text_input("请输入号码组合（支持任意顺序）").strip()
    if target:
        if target.isdigit():
            counter_target = Counter(target)
            match_df = freq_df[
                freq_df["号码组合"].apply(lambda combo: Counter(combo) == counter_target)
            ]
            if not match_df.empty:
                st.dataframe(match_df, use_container_width=True)
            else:
                st.info("未找到匹配组合。")
        else:
            st.warning("请输入数字组合。")

category_counts = df["组合结果"].apply(classify).value_counts().to_dict()
st.markdown(
    """
    ### 组合类型统计
    - 组六组合数量：**{} 个**
    - 组三组合数量：**{} 个**
    - 豹子组合数量：**{} 个**
    """.format(
        category_counts.get("组六", 0),
        category_counts.get("组三", 0),
        category_counts.get("豹子", 0),
    )
)
