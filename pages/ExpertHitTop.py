from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    fetch_playtypes_for_issue,
)
from utils.ui import issue_picker, playtype_picker, render_open_info

from utils.sql import make_in_clause

st.header("Expert Hit Top - 本期命中榜")

selected_issue = issue_picker(
    "expert_hit_issue",
    mode="single",
    label="期号",
)
if not selected_issue:
    st.stop()

render_open_info(selected_issue, key="expert_hit_open")

playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期未找到可用玩法。")
    st.stop()

playtype_map = {
    int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()
}
raw_playtypes = playtype_picker(
    "expert_hit_playtypes",
    mode="multi",
    label="玩法",
    include=[str(pid) for pid in playtype_map.keys()],
    default=[str(pid) for pid in playtype_map.keys()],
)
selected_playtypes = [int(pid) for pid in raw_playtypes]

if not selected_playtypes:
    st.warning("请至少选择一个玩法。")
    st.stop()

playtype_clause, playtype_params = make_in_clause(
    "p.playtype_id", selected_playtypes, "pt"
)

sql_predictions = f"""
    SELECT p.user_id, p.playtype_id, p.numbers
    FROM expert_predictions p
    WHERE p.issue_name = :issue
      AND {playtype_clause}
"""
params = {"issue": selected_issue, **playtype_params}

try:
    prediction_rows = cached_query(query_db, sql_predictions, params=params, ttl=120)
except Exception as exc:
    st.warning(f"加载本期推荐失败：{exc}")
    prediction_rows = []

if not prediction_rows:
    st.info("当前期暂无推荐数据。")
    st.stop()

prediction_df = pd.DataFrame(prediction_rows)
prediction_df["playtype_name"] = prediction_df["playtype_id"].map(playtype_map)

numbers_map = (
    prediction_df.groupby(["user_id", "playtype_id"])["numbers"]
    .apply(lambda values: " | ".join(str(v) for v in values))
    .reset_index()
)

stat_clause, stat_clause_params = make_in_clause(
    "playtype_id", selected_playtypes, "pt_stat"
)
stat_params = {"issue": selected_issue, **stat_clause_params}

stats_sql = f"""
    SELECT user_id, playtype_id, hit_count, total_count, hit_number_count
    FROM expert_hit_stat
    WHERE issue_name = :issue
      AND {stat_clause}
"""
try:
    stat_rows = cached_query(query_db, stats_sql, params=stat_params, ttl=120)
except Exception as exc:
    st.warning(f"加载命中统计失败：{exc}")
    stat_rows = []

if not stat_rows:
    st.info("暂无命中统计数据。")
    st.stop()

stats_df = pd.DataFrame(stat_rows)
hit_stats_df = stats_df[stats_df["hit_count"] > 0].copy()

if hit_stats_df.empty:
    st.info("本期暂无命中专家。")
else:
    hit_stats_df = hit_stats_df.merge(
        numbers_map, how="left", on=["user_id", "playtype_id"]
    )
    hit_stats_df["numbers"] = hit_stats_df["numbers"].fillna("-")
    hit_stats_df["playtype_name"] = hit_stats_df["playtype_id"].map(playtype_map)

    user_ids = [int(uid) for uid in hit_stats_df["user_id"].dropna().unique().tolist()]
    user_clause, user_params = make_in_clause("user_id", user_ids, "user")
    nick_rows = cached_query(
        query_db,
        f"SELECT user_id, nick_name FROM expert_info WHERE {user_clause}",
        params=user_params,
        ttl=300,
    )
    nick_map = {row["user_id"]: row.get("nick_name") for row in nick_rows}

    playtype_ids = (
        hit_stats_df["playtype_id"].dropna().astype(int).unique().tolist()
    )
    if playtype_ids:
        pt_clause, pt_params = make_in_clause("playtype_id", playtype_ids, "ptid")
        history_params = {**user_params, **pt_params}
        stats_rows = cached_query(
            query_db,
            f"""
            SELECT user_id, playtype_id, SUM(hit_count) AS total_hit_count
            FROM expert_hit_stat
            WHERE {user_clause} AND {pt_clause}
            GROUP BY user_id, playtype_id
            """,
            params=history_params,
            ttl=300,
        )
        stats_map = {
            (row["user_id"], row["playtype_id"]): row.get("total_hit_count", 0)
            for row in stats_rows
        }
    else:
        stats_map = {}

    hit_stats_df["nick_name"] = hit_stats_df["user_id"].map(nick_map)
    hit_stats_df["total_hit_count"] = hit_stats_df.apply(
        lambda row: stats_map.get((row["user_id"], row["playtype_id"]), 0),
        axis=1,
    )

    st.subheader("命中 AI 专家")
    col_expert, col_records, col_playtypes = st.columns(3)
    col_expert.metric("命中专家数", hit_stats_df["user_id"].nunique())
    col_records.metric("命中记录数", int(hit_stats_df["hit_count"].sum()))
    col_playtypes.metric("涉及玩法数", hit_stats_df["playtype_id"].nunique())

    hits_view = hit_stats_df[
        [
            "user_id",
            "nick_name",
            "playtype_name",
            "numbers",
            "hit_count",
            "total_count",
            "hit_number_count",
            "total_hit_count",
        ]
    ].copy()
    hits_view.columns = [
        "user_id",
        "nick_name",
        "玩法",
        "推荐内容",
        "本期命中次数",
        "本期推荐次数",
        "命中号码覆盖数",
        "历史累计命中",
    ]
    st.dataframe(hits_view, width="stretch")

st.subheader("本期玩法命中率热力图")
rate_df = (
    stats_df.groupby("playtype_id")[["total_count", "hit_count"]]
    .sum()
    .reset_index()
)
rate_df["hit_rate"] = rate_df.apply(
    lambda row: row["hit_count"] / row["total_count"] if row["total_count"] else 0,
    axis=1,
)
rate_df["playtype_name"] = rate_df["playtype_id"].map(playtype_map)
rate_df.rename(columns={"hit_count": "hit", "total_count": "total"}, inplace=True)

if rate_df.empty:
    st.info("暂无命中率数据。")
else:
    heatmap = (
        alt.Chart(rate_df)
        .mark_bar()
        .encode(
            x=alt.X("playtype_name:N", title="玩法"),
            y=alt.Y("hit_rate:Q", title="命中率", axis=alt.Axis(format="%")),
            color=alt.Color(
                "hit_rate:Q", title="命中率", scale=alt.Scale(scheme="greens")
            ),
            tooltip=[
                "playtype_name",
                alt.Tooltip("hit_rate:Q", format=".2%", title="命中率"),
                alt.Tooltip("hit:Q", title="命中数量"),
                alt.Tooltip("total:Q", title="推荐数量"),
            ],
        )
        .properties(width="container", height=320)
    )
    st.altair_chart(heatmap, use_container_width=True)
