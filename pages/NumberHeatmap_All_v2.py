from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_playtypes, fetch_recent_issues
from utils.numbers import normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button

st.header("NumberHeatmap_All_v2 - 单期热力图")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

lottery_info = fetch_lottery_info(selected_issue)
if lottery_info:
    st.caption(
        f"开奖号码：{lottery_info.get('open_code') or '未开奖'}丨和值：{lottery_info.get('sum')}"
    )

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()
}
selected_playtypes = st.multiselect(
    "选择玩法（可多选）",
    options=list(playtype_map.keys()),
    default=list(playtype_map.keys())[:3],
    format_func=lambda value: playtype_map.get(value, value),
)

if not selected_playtypes:
    st.warning("请选择至少一个玩法。")
    st.stop()

clause, params = make_in_clause(
    "playtype_id", [int(pid) for pid in selected_playtypes], "pt"
)
sql = f"""
    SELECT playtype_id, user_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue_name
      AND {clause}
"""
params.update({"issue_name": selected_issue})

try:
    rows = cached_query(query_db, sql, params=params, ttl=120)
except Exception as exc:
    st.warning(f"查询推荐数据失败：{exc}")
    rows = []

if not rows:
    st.info("未找到符合条件的推荐记录。")
    st.stop()

open_code = normalize_code(lottery_info.get("open_code")) if lottery_info else ""

open_digits = list(open_code) if open_code else []
position_hits = {
    "百": open_digits[0] if len(open_digits) >= 1 else None,
    "十": open_digits[1] if len(open_digits) >= 2 else None,
    "个": open_digits[2] if len(open_digits) >= 3 else None,
}

records = []
for row in rows:
    playtype_id = str(row["playtype_id"])
    playtype_name = playtype_map.get(playtype_id, playtype_id)
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
                    "digit": digit,
                    "playtype_id": playtype_id,
                    "playtype_name": playtype_name,
                    "is_hit": is_hit,
                }
            )

if not records:
    st.info("无法拆解推荐数字，可能数据格式异常。")
    st.stop()

heatmap_df = pd.DataFrame(records)
heatmap_df["count"] = 1
heatmap_df = heatmap_df.groupby(["playtype_name", "digit", "is_hit"], as_index=False)[
    "count"
].sum()

st.subheader("数字热力图")

chart = (
    alt.Chart(heatmap_df)
    .mark_rect()
    .encode(
        x=alt.X("digit:N", title="数字"),
        y=alt.Y("playtype_name:N", title="玩法"),
        color=alt.Color("count:Q", title="推荐次数", scale=alt.Scale(scheme="viridis")),
        tooltip=["playtype_name", "digit", "count", "is_hit"],
    )
    .properties(width="container", height=400)
)
st.altair_chart(chart, use_container_width=True)

download_csv_button(heatmap_df, "下载热力图数据", "number_heatmap_all_v2")

st.subheader("排行榜命中检测 (Top10)")

ranking_df = (
    heatmap_df.groupby(["digit"], as_index=False)["count"]
    .sum()
    .sort_values(by="count", ascending=False)
)
top10 = ranking_df.head(10).copy()
top10["rank"] = range(1, len(top10) + 1)
top10 = top10.merge(
    heatmap_df.groupby("digit")["is_hit"].max().reset_index(), on="digit", how="left"
)

top_chart = (
    alt.Chart(top10)
    .mark_bar()
    .encode(
        x=alt.X("rank:O", title="排行榜位置"),
        y=alt.Y("count:Q", title="推荐次数"),
        color=alt.Color(
            "is_hit:N",
            title="是否命中",
            scale=alt.Scale(domain=[True, False], range=["#e15759", "#bab0ab"]),
        ),
        tooltip=["digit", "count", "is_hit"],
    )
    .properties(width=600, height=300)
)
st.altair_chart(top_chart, use_container_width=True)

download_csv_button(top10, "下载排行榜", "number_heatmap_rank")
