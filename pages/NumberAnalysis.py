from __future__ import annotations

import itertools
from typing import List, Set

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_playtypes, fetch_recent_issues
from utils.numbers import parse_tokens
from utils.ui import download_csv_button


def _normalize_combo(tokens: List[str]) -> str:
    return "-".join(sorted(tokens))


def _digits_from_tokens(tokens: List[str]) -> List[int]:
    digits: List[int] = []
    for token in tokens:
        for char in token:
            if char.isdigit():
                digits.append(int(char))
    return digits


def _has_consecutive(digits: List[int]) -> bool:
    if not digits:
        return False
    sorted_digits = sorted(set(digits))
    return any(b - a == 1 for a, b in zip(sorted_digits, sorted_digits[1:]))


def _range_slider(label: str, series: pd.Series) -> tuple[int, int]:
    min_val = int(series.min())
    max_val = int(series.max())
    if min_val == max_val:
        st.info(f"{label} 固定为 {min_val}")
        return min_val, max_val
    return st.slider(
        label,
        min_value=min_val,
        max_value=max_val,
        value=(min_val, max_val),
    )


st.header("NumberAnalysis - 号码组合分析")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

lottery = fetch_lottery_info(selected_issue)
if lottery:
    st.caption(
        f"开奖号码：{lottery.get('open_code') or '未开奖'}丨和值：{lottery.get('sum')}丨跨度：{lottery.get('span')}"
    )

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()
}
selected_playtype = st.selectbox(
    "选择玩法",
    options=list(playtype_map.keys()),
    format_func=lambda value: playtype_map.get(value, value),
)

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
combo_df["has_consecutive"] = combo_df["digits"].apply(_has_consecutive)
combo_df.sort_values(by="count", ascending=False, inplace=True)

count_min, count_max = _range_slider("出现次数范围", combo_df["count"])

include_digits = st.multiselect("必须包含数字", options=[str(i) for i in range(10)])
exclude_digits = st.multiselect("排除包含数字", options=[str(i) for i in range(10)])

sum_min, sum_max = _range_slider("和值范围", combo_df["sum_digits"])
span_min, span_max = _range_slider("跨度范围", combo_df["span"])

odd_even_options = sorted(combo_df["odd_even_ratio"].unique())
selected_odd_even = st.multiselect("保留奇偶比", options=odd_even_options)

big_small_options = sorted(combo_df["big_small_ratio"].unique())
selected_big_small = st.multiselect("保留大小比", options=big_small_options)

exclude_consecutive = st.checkbox("排除连续数字", value=False)

filtered_df = combo_df[
    (combo_df["count"].between(count_min, count_max))
    & (combo_df["sum_digits"].between(sum_min, sum_max))
    & (combo_df["span"].between(span_min, span_max))
]

if include_digits:
    include_set = set(include_digits)
    filtered_df = filtered_df[
        filtered_df["digits"].apply(
            lambda digits: include_set.issubset({str(d) for d in digits})
        )
    ]

if exclude_digits:
    exclude_set = set(exclude_digits)
    filtered_df = filtered_df[
        ~filtered_df["digits"].apply(
            lambda digits: bool(exclude_set.intersection({str(d) for d in digits}))
        )
    ]

if selected_odd_even:
    filtered_df = filtered_df[filtered_df["odd_even_ratio"].isin(selected_odd_even)]

if selected_big_small:
    filtered_df = filtered_df[filtered_df["big_small_ratio"].isin(selected_big_small)]

if exclude_consecutive:
    filtered_df = filtered_df[~filtered_df["has_consecutive"]]

filtered_df = filtered_df.copy()
filtered_df["numbers"] = filtered_df["sample_numbers"]

st.subheader("组合统计")
st.dataframe(
    filtered_df[
        [
            "combo_key",
            "numbers",
            "count",
            "sum_digits",
            "span",
            "odd_even_ratio",
            "big_small_ratio",
            "has_consecutive",
        ]
    ],
    use_container_width=True,
)
st.caption(
    f"筛选后组合数：{len(filtered_df)}丨平均出现次数：{filtered_df['count'].mean() if not filtered_df.empty else 0:.2f}"
)

download_csv_button(
    filtered_df[
        [
            "combo_key",
            "numbers",
            "count",
            "sum_digits",
            "span",
            "odd_even_ratio",
            "big_small_ratio",
            "has_consecutive",
        ]
    ],
    "下载组合统计",
    "number_analysis_combinations",
)

st.subheader("组合出现次数分布")

chart = (
    alt.Chart(filtered_df)
    .mark_bar()
    .encode(
        x=alt.X("combo_key:N", sort="-y", title="组合"),
        y=alt.Y("count:Q", title="出现次数"),
        tooltip=["combo_key", "count", "sum_digits", "span"],
    )
    .properties(width="container", height=400)
)
st.altair_chart(chart, use_container_width=True)

st.subheader("号码配对器")
sort_mode = st.radio(
    "排序方式", options=("出现次数高到低", "出现次数低到高"), horizontal=True
)
max_digits = st.slider("最大覆盖数字数", min_value=3, max_value=10, value=9)

pair_df = filtered_df.sort_values(by="count", ascending=(sort_mode != "出现次数高到低"))
selected_pairs = []
used_digits: Set[int] = set()

for _, row in pair_df.iterrows():
    digits = set(row["digits"])
    combined = used_digits.union(digits)
    if len(combined) <= max_digits:
        selected_pairs.append(row)
        used_digits = combined

if selected_pairs:
    pair_table = pd.DataFrame(selected_pairs)
    st.write(
        "已选择组合数：",
        len(pair_table),
        "丨覆盖数字：",
        "".join(str(d) for d in sorted(used_digits)),
    )
    st.dataframe(
        pair_table[["combo_key", "numbers", "count"]], use_container_width=True
    )
else:
    st.info("未能根据配对规则选择组合。")

st.subheader("全排列转换（组选）")
permutation_enabled = st.checkbox("启用全排列转换", value=False)
max_permutations = 5000
permutation_results: list[str] = []

if permutation_enabled:
    for tokens in filtered_df["tokens"]:
        digits = [d for token in tokens for d in token]
        if len(digits) > 6:  # 避免组合过大
            continue
        perms = {"".join(p) for p in itertools.permutations(digits)}
        permutation_results.extend(sorted(perms))
        if len(permutation_results) >= max_permutations:
            break
    permutation_results = permutation_results[:max_permutations]
    if permutation_results:
        st.write(
            f"展示前 {len(permutation_results)} 项全排列结果（上限 {max_permutations}）。"
        )
        st.text(", ".join(permutation_results))
    else:
        st.info("未生成任何全排列结果（可能组合位数过大）。")

st.subheader("投注估算")
col_group, col_direct = st.columns(2)
with col_group:
    group_multiplier = st.number_input("组选倍数", min_value=0, value=1, step=1)
with col_direct:
    direct_multiplier = st.number_input("直选倍数", min_value=0, value=0, step=1)

combo_count = len(filtered_df)
permutation_count = len(permutation_results) if permutation_enabled else combo_count

direct_payout = 970  # 直选参考奖金
combo_payout = 320  # 组选参考奖金

estimated_cost = (
    combo_count * group_multiplier * 2 + combo_count * direct_multiplier * 2
)
estimated_reward = combo_payout * group_multiplier + direct_payout * direct_multiplier

st.write(
    f"组合数：{combo_count}丨排列数：{permutation_count}丨预计投入：¥{estimated_cost:.2f}丨预估奖金：¥{estimated_reward:.2f}"
)
