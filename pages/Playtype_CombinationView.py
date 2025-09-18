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

st.header("Playtype_CombinationView - 多玩法对比视图")

issues = fetch_recent_issues(limit=120)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()
}
selected_playtypes = st.multiselect(
    "选择玩法（多选对比）",
    options=list(playtype_map.keys()),
    default=list(playtype_map.keys())[:3],
    format_func=lambda value: playtype_map.get(value, value),
)

if not selected_playtypes:
    st.warning("请至少选择一个玩法。")
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
    st.info("未查询到推荐数据。")
    st.stop()

open_row = cached_query(
    query_db,
    "SELECT open_code, open_time FROM lottery_results WHERE issue_name = :issue LIMIT 1",
    params={"issue": selected_issue},
    ttl=60,
)
open_code = normalize_code(open_row[0]["open_code"]) if open_row else ""
open_time = open_row[0].get("open_time") if open_row else None
open_digits = list(open_code) if open_code else []
position_hits = {
    "百": open_digits[0] if len(open_digits) >= 1 else None,
    "十": open_digits[1] if len(open_digits) >= 2 else None,
    "个": open_digits[2] if len(open_digits) >= 3 else None,
}

st.info(
    f"开奖信息：期号 {selected_issue}丨开奖号码 {open_code or '未知'}丨开奖时间 {open_time or '未知'}"
)

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
                    "playtype_id": playtype_id,
                    "playtype_name": playtype_name,
                    "digit": digit,
                    "is_hit": is_hit,
                }
            )

if not records:
    st.info("无法解析推荐数字。")
    st.stop()

heatmap_df = pd.DataFrame(records)
heatmap_df["count"] = 1
heatmap_df = heatmap_df.groupby(
    ["playtype_id", "playtype_name", "digit", "is_hit"], as_index=False
)["count"].sum()

st.subheader("玩法对比热力图")

cols = st.columns(min(3, len(selected_playtypes)))
for idx, playtype_id in enumerate(selected_playtypes):
    col = cols[idx % len(cols)]
    data = heatmap_df[heatmap_df["playtype_id"] == playtype_id]
    if data.empty:
        col.info(f"玩法 {playtype_map.get(playtype_id)} 无数据")
        continue
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("digit:N", title="数字"),
            y=alt.Y("count:Q", title="次数"),
            color=alt.Color(
                "is_hit:N",
                title="命中",
                scale=alt.Scale(domain=[True, False], range=["#ff7f0e", "#1f77b4"]),
            ),
            tooltip=["digit", "count", "is_hit"],
        )
        .properties(width=250, height=280, title=playtype_map.get(playtype_id))
    )
    col.altair_chart(chart, use_container_width=True)

st.subheader("玩法高频数字交叉分析")

top_k = st.slider("TopK 高频数字", min_value=3, max_value=10, value=5)

top_sets = {}
for playtype_id in selected_playtypes:
    data = (
        heatmap_df[heatmap_df["playtype_id"] == playtype_id]
        .groupby("digit", as_index=False)["count"]
        .sum()
        .sort_values(by="count", ascending=False)
        .head(top_k)
    )
    top_sets[playtype_id] = set(data["digit"].tolist())

if top_sets:
    union_digits = sorted(set().union(*top_sets.values()))
    intersection_digits = (
        sorted(set.intersection(*top_sets.values()))
        if len(top_sets) > 1
        else union_digits
    )
    st.write(
        f"高频数字并集：{' '.join(union_digits) if union_digits else '无'} | 交集：{' '.join(intersection_digits) if intersection_digits else '无'}"
    )
else:
    st.info("无法计算交集/并集。")

st.subheader("排行榜命中位次 (Top10)")

rank_records = []
for playtype_id in selected_playtypes:
    data = (
        heatmap_df[heatmap_df["playtype_id"] == playtype_id]
        .groupby(["digit"], as_index=False)["count"]
        .sum()
        .sort_values(by="count", ascending=False)
        .head(10)
    )
    hits = (
        heatmap_df[heatmap_df["playtype_id"] == playtype_id]
        .groupby("digit")["is_hit"]
        .max()
    )
    for rank, (_, row) in enumerate(data.iterrows(), start=1):
        rank_records.append(
            {
                "playtype_id": playtype_id,
                "playtype_name": playtype_map.get(playtype_id),
                "rank": rank,
                "is_hit": bool(hits.get(row["digit"], False)),
            }
        )

if rank_records:
    rank_df = pd.DataFrame(rank_records)
    chart = (
        alt.Chart(rank_df)
        .mark_bar()
        .encode(
            x=alt.X("rank:O", title="排行榜位置"),
            y=alt.Y("count():Q", title="命中次数"),
            color=alt.Color("playtype_name:N", title="玩法"),
            column=alt.Column("is_hit:N", title="是否命中"),
            tooltip=["playtype_name", "rank", "is_hit"],
        )
        .properties(width=140)
    )
    st.altair_chart(chart, use_container_width=True)
else:
    st.info("无法生成排行榜命中数据。")


download_csv_button(heatmap_df, "下载玩法对比数据", "playtype_combination_view")
