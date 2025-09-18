from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_infos, fetch_playtypes, fetch_recent_issues
from utils.numbers import normalize_code, parse_tokens
from utils.sql import make_in_clause

st.header("NumberHeatmap_Simplified_v2_all - 多期热力图")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

default_selection = issues[:4]
selected_issues = st.multiselect(
    "选择期号（最多选择 12 期）",
    options=issues,
    default=default_selection,
)

if not selected_issues:
    st.warning("请选择至少一个期号。")
    st.stop()

if len(selected_issues) > 12:
    st.warning("建议每次最多选择 12 期以保持可视化性能。")
    selected_issues = selected_issues[:12]

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

issue_clause, issue_params = make_in_clause("issue_name", selected_issues, "issue")
sql_predictions = f"""
    SELECT issue_name, user_id, numbers
    FROM expert_predictions
    WHERE playtype_id = :playtype_id
      AND {issue_clause}
"""
issue_params.update({"playtype_id": int(selected_playtype)})

try:
    rows = cached_query(query_db, sql_predictions, params=issue_params, ttl=120)
except Exception as exc:
    st.warning(f"查询预测数据失败：{exc}")
    rows = []

if not rows:
    st.info("所选期号范围内无预测数据。")
    st.stop()

lottery_clause, lottery_params = make_in_clause(
    "issue_name", selected_issues, "lottery"
)
sql_lottery = f"""
    SELECT issue_name, open_code
    FROM lottery_results
    WHERE {lottery_clause}
"""
lottery_rows = cached_query(query_db, sql_lottery, params=lottery_params, ttl=120)
open_map = {
    row["issue_name"]: normalize_code(row.get("open_code")) for row in lottery_rows
}

playtype_name = playtype_map.get(selected_playtype, selected_playtype)

records = []
for row in rows:
    issue_name = row["issue_name"]
    open_code = open_map.get(issue_name, "")
    open_digits = list(open_code) if open_code else []
    position_hits = {
        "百": open_digits[0] if len(open_digits) >= 1 else None,
        "十": open_digits[1] if len(open_digits) >= 2 else None,
        "个": open_digits[2] if len(open_digits) >= 3 else None,
    }
    tokens = parse_tokens(row["numbers"])
    for token in tokens:
        for digit in token:
            is_hit = False
            if any(keyword in playtype_name for keyword in ("百位", "十位", "个位")):
                if "百" in playtype_name:
                    is_hit = position_hits.get("百") == digit
                elif "十" in playtype_name:
                    is_hit = position_hits.get("十") == digit
                elif "个" in playtype_name:
                    is_hit = position_hits.get("个") == digit
            else:
                is_hit = digit in open_digits
            records.append(
                {
                    "issue_name": issue_name,
                    "digit": digit,
                    "is_hit": is_hit,
                }
            )

if not records:
    st.info("无法拆解推荐数字。")
    st.stop()

heatmap_df = pd.DataFrame(records)
heatmap_df["count"] = 1
heatmap_df = heatmap_df.groupby(["issue_name", "digit", "is_hit"], as_index=False)[
    "count"
].sum()
heatmap_df.sort_values(by=["issue_name", "digit"], inplace=True)

st.subheader("分期热力图")

lottery_bulk = fetch_lottery_infos(selected_issues)

for i in range(0, len(selected_issues), 4):
    cols = st.columns(4)
    for col, issue in zip(cols, selected_issues[i : i + 4]):
        issue_data = heatmap_df[heatmap_df["issue_name"] == issue]
        if issue_data.empty:
            col.info(f"{issue} 无数据")
            continue
        info = lottery_bulk.get(issue)
        chart = (
            alt.Chart(issue_data)
            .mark_bar()
            .encode(
                x=alt.X("digit:N", title=f"期 {issue}"),
                y=alt.Y("count:Q", title="次数"),
                color=alt.Color(
                    "is_hit:N",
                    title="命中",
                    scale=alt.Scale(domain=[True, False], range=["#ff7f0e", "#1f77b4"]),
                ),
                tooltip=["digit", "count", "is_hit"],
            )
            .properties(width=180, height=240)
        )
        col.altair_chart(chart, use_container_width=True)
        if info:
            col.caption(f"开奖号码：{info.get('open_code')}")

st.subheader("多期排行榜命中检测")

rank_records = []
for issue in selected_issues:
    issue_data = heatmap_df[heatmap_df["issue_name"] == issue].sort_values(
        by="count", ascending=False
    )
    top10 = issue_data.head(10)
    for idx, (_, row) in enumerate(top10.iterrows(), start=1):
        rank_records.append({"rank": idx, "is_hit": row["is_hit"]})

if rank_records:
    rank_df = pd.DataFrame(rank_records)
    rank_summary = (
        rank_df.groupby(["rank", "is_hit"], as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )
    chart = (
        alt.Chart(rank_summary)
        .mark_bar()
        .encode(
            x=alt.X("rank:O", title="排行榜位置"),
            y=alt.Y("count:Q", title="命中次数"),
            color=alt.Color(
                "is_hit:N",
                title="是否命中",
                scale=alt.Scale(domain=[True, False], range=["#d62728", "#7f7f7f"]),
            ),
            tooltip=["rank", "count", "is_hit"],
        )
        .properties(width=600, height=300)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("无法生成排行榜命中结果。")
