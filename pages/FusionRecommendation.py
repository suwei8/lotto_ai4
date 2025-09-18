from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes, fetch_recent_issues
from utils.numbers import parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button


def flatten_numbers(numbers: str) -> list[str]:
    parts = []
    for token in numbers.replace("|", ",").split(","):
        token = token.strip()
        if token:
            parts.append(token)
    return parts


def aggregate_digits(df: pd.DataFrame) -> pd.DataFrame:
    counter: dict[str, int] = {}
    for value in df["numbers"]:
        for token in flatten_numbers(value):
            for digit in token:
                if digit.isdigit():
                    counter[digit] = counter.get(digit, 0) + 1
    result = pd.DataFrame(
        sorted(
            ((digit, count) for digit, count in counter.items()),
            key=lambda item: item[1],
            reverse=True,
        ),
        columns=["digit", "count"],
    )
    result["rank"] = range(1, len(result) + 1)
    return result


st.header("FusionRecommendation - 融合推荐")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

playtypes = fetch_playtypes()
playtype_map = (
    {row.playtype_id: row.playtype_name for row in playtypes.itertuples()}
    if not playtypes.empty
    else {}
)

sql_predictions = """
    SELECT user_id, playtype_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue
"""
prediction_rows = cached_query(
    query_db, sql_predictions, params={"issue": selected_issue}, ttl=300
)
if not prediction_rows:
    st.info("未查询到预测记录。")
    st.stop()

pred_df = pd.DataFrame(prediction_rows)
pred_df["playtype_name"] = pred_df["playtype_id"].apply(
    lambda pid: playtype_map.get(pid, str(pid))
)

lottery_rows = cached_query(
    query_db,
    "SELECT open_code FROM lottery_results WHERE issue_name = :issue LIMIT 1",
    params={"issue": selected_issue},
    ttl=300,
)
open_code = lottery_rows[0]["open_code"] if lottery_rows else None
st.info(f"开奖号码提示：{open_code or '未开奖'}")

filtered_df = pred_df[~pred_df["playtype_name"].str.contains("杀", na=False)].copy()
consensus_df = aggregate_digits(filtered_df)

st.subheader("共识推荐数字")
st.dataframe(consensus_df, use_container_width=True)
st.altair_chart(
    alt.Chart(consensus_df)
    .mark_bar()
    .encode(
        x=alt.X("digit:N", title="数字"),
        y=alt.Y("count:Q", title="推荐次数"),
        tooltip=["digit", "count", "rank"],
    )
    .properties(width=600, height=320),
    use_container_width=True,
)

download_csv_button(consensus_df, "下载共识推荐", "fusion_consensus")

st.subheader("按玩法推荐热力图")
heatmap_records = []
for playtype_id, group in pred_df.groupby("playtype_id"):
    playtype_name = playtype_map.get(playtype_id, str(playtype_id))
    for numbers in group["numbers"]:
        for token in flatten_numbers(numbers):
            for digit in token:
                if digit.isdigit():
                    heatmap_records.append(
                        {"playtype_name": playtype_name, "digit": digit}
                    )

heatmap_df = pd.DataFrame(heatmap_records)
if heatmap_df.empty:
    st.info("无法生成热力图数据。")
else:
    heatmap_df["count"] = 1
    heatmap_df = heatmap_df.groupby(["playtype_name", "digit"], as_index=False)[
        "count"
    ].sum()
    chart = (
        alt.Chart(heatmap_df)
        .mark_rect()
        .encode(
            x=alt.X("digit:N", title="数字"),
            y=alt.Y("playtype_name:N", title="玩法"),
            color=alt.Color(
                "count:Q", title="推荐次数", scale=alt.Scale(scheme="tealblues")
            ),
            tooltip=["playtype_name", "digit", "count"],
        )
        .properties(width="container", height=400)
    )
    st.altair_chart(chart, use_container_width=True)

st.subheader("参与专家")
expert_clause, expert_params = make_in_clause(
    "user_id", pred_df["user_id"].unique().tolist(), "users"
)
sql_experts = f"""
    SELECT user_id, nick_name
    FROM expert_info
    WHERE {expert_clause}
"""
expert_rows = cached_query(query_db, sql_experts, params=expert_params, ttl=600)
expert_map = {row["user_id"]: row.get("nick_name") for row in expert_rows}


def summarize(numbers: pd.Series) -> str:
    sample = numbers.head(5).tolist()
    more = " ..." if len(numbers) > 5 else ""
    return "; ".join(sample) + more


experts_df = pred_df.groupby("user_id")["numbers"].apply(summarize).reset_index()
experts_df["nick_name"] = experts_df["user_id"].apply(
    lambda uid: expert_map.get(uid, "未知")
)
st.dataframe(experts_df[["user_id", "nick_name", "numbers"]], use_container_width=True)
