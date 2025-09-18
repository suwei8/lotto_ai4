from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes, fetch_recent_issues
from utils.numbers import normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button


def determine_hit(playtype_name: str, tokens: list[str], open_code: str | None) -> bool:
    if not open_code:
        return False
    normalized = normalize_code(open_code)
    if not normalized:
        return False
    digits = list(normalized)
    token_sets = [set(token) for token in tokens if token]

    if "杀" in playtype_name:
        # 命中即杀成功：开奖号码不包含被杀数字
        for digit in digits:
            if any(digit in token_set for token_set in token_sets):
                return False
        return True

    if any(keyword in playtype_name for keyword in ("百位", "十位", "个位")):
        for token in tokens:
            if "百" in playtype_name and digits[0] not in token:
                return False
            if "十" in playtype_name and digits[1] not in token:
                return False
            if "个" in playtype_name and digits[2] not in token:
                return False
        return True

    # 默认：若完整开奖号码在组合中，或组合覆盖全部开奖号码
    if normalized in tokens:
        return True
    combined = set().union(*token_sets) if token_sets else set()
    return all(digit in combined for digit in digits)


st.header("HitComboFrequencyAnalysis - 命中组合统计")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issues = st.multiselect("选择期号", options=issues, default=issues[:10])
if not selected_issues:
    st.warning("请选择至少一个期号。")
    st.stop()

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
playtype_name = playtype_map.get(selected_playtype, selected_playtype)

issue_clause, issue_params = make_in_clause("issue_name", selected_issues, "issue")
sql_predictions = f"""
    SELECT issue_name, user_id, numbers
    FROM expert_predictions
    WHERE {issue_clause}
      AND playtype_id = :playtype_id
"""
issue_params.update({"playtype_id": int(selected_playtype)})

try:
    prediction_rows = cached_query(
        query_db, sql_predictions, params=issue_params, ttl=300
    )
except Exception as exc:
    st.warning(f"查询预测数据失败：{exc}")
    prediction_rows = []

if not prediction_rows:
    st.info("未获取到预测数据。")
    st.stop()

prediction_df = pd.DataFrame(prediction_rows)
prediction_df.drop_duplicates(subset=["issue_name", "user_id", "numbers"], inplace=True)

lottery_clause, lottery_params = make_in_clause(
    "issue_name", selected_issues, "lottery"
)
sql_lottery = f"""
    SELECT issue_name, open_code
    FROM lottery_results
    WHERE {lottery_clause}
"""
lottery_rows = cached_query(query_db, sql_lottery, params=lottery_params, ttl=300)
open_map = {row["issue_name"]: row.get("open_code") for row in lottery_rows}

records = []
for issue_name, group in prediction_df.groupby("issue_name"):
    open_code = open_map.get(issue_name)
    combo_counts = (
        group.groupby("numbers").agg(count=("user_id", "nunique")).reset_index()
    )
    for row in combo_counts.itertuples():
        tokens = parse_tokens(row.numbers)
        hit = determine_hit(playtype_name, tokens, open_code)
        records.append(
            {
                "issue_name": issue_name,
                "numbers": row.numbers,
                "occurrences": int(row.count),
                "open_code": open_code,
                "is_hit": hit,
            }
        )

if not records:
    st.info("无法生成命中组合统计。")
    st.stop()

result_df = pd.DataFrame(records)
result_df.sort_values(
    by=["issue_name", "occurrences"], ascending=[False, False], inplace=True
)

st.subheader("命中组合列表")
st.dataframe(result_df[result_df["is_hit"]], use_container_width=True)

download_csv_button(result_df, "下载组合统计", "hit_combo_frequency")

st.subheader("出现次数组 × 命中率")

group_df = result_df.groupby(["issue_name", "occurrences"], as_index=False).agg(
    total_combos=("numbers", "count"), hit_combos=("is_hit", "sum")
)
group_df["hit_rate"] = group_df.apply(
    lambda row: row["hit_combos"] / row["total_combos"] if row["total_combos"] else 0,
    axis=1,
)

st.dataframe(group_df, use_container_width=True)

chart = (
    alt.Chart(group_df)
    .mark_bar()
    .encode(
        x=alt.X("occurrences:O", title="出现次数"),
        y=alt.Y("hit_rate:Q", title="命中率"),
        color="issue_name:N",
        tooltip=[
            "issue_name",
            "occurrences",
            "total_combos",
            "hit_combos",
            alt.Tooltip("hit_rate:Q", format=".2%"),
        ],
    )
    .properties(width=600, height=320)
)
st.altair_chart(chart, use_container_width=True)

st.subheader("未命中出现次数分布 Top3")
miss_df = group_df[group_df["hit_combos"] == 0].copy()
miss_top = (
    miss_df.sort_values(by="total_combos", ascending=False)
    .groupby("issue_name")
    .head(3)
)
st.dataframe(miss_top, use_container_width=True)
