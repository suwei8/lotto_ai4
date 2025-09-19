from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    fetch_lottery_info,
    fetch_playtypes_for_issue,
    fetch_recent_issues,
)
from utils.numbers import count_hits, normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button

st.header("Expert Hit Top - 本期命中榜")

issues = fetch_recent_issues(limit=200)
if not issues:
    st.warning("无法获取期号列表，请检查数据库连接。")
    st.stop()

selected_issue = st.selectbox("期号", options=issues)

lottery = fetch_lottery_info(selected_issue)
if lottery:
    col_code, col_sum, col_span = st.columns(3)
    col_code.metric("开奖号码", lottery.get("open_code") or "未开奖")
    col_sum.metric("和值", lottery.get("sum", "-"))
    col_span.metric("跨度", lottery.get("span", "-"))
else:
    st.warning("未能获取该期的开奖信息。")

playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期未找到可用玩法。")
    st.stop()

playtype_map = {
    int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()
}
selected_playtypes = st.multiselect(
    "玩法",
    options=list(playtype_map.keys()),
    default=list(playtype_map.keys()),
    format_func=lambda pid: playtype_map.get(pid, str(pid)),
)

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
prediction_df["tokens"] = prediction_df["numbers"].apply(parse_tokens)
prediction_df["playtype_name"] = prediction_df["playtype_id"].map(playtype_map)

open_code_clean = normalize_code((lottery or {}).get("open_code")) if lottery else ""
if open_code_clean:
    prediction_df["is_hit"] = prediction_df["tokens"].apply(
        lambda tokens: count_hits(tokens, open_code_clean) > 0
    )
    hits_df = prediction_df[prediction_df["is_hit"]].copy()
else:
    st.warning("缺少开奖号码，无法判定命中专家。")
    hits_df = pd.DataFrame(
        columns=["user_id", "playtype_id", "playtype_name", "numbers"]
    )

if hits_df.empty:
    st.info("本期暂无命中专家。")
else:
    user_clause, user_params = make_in_clause(
        "user_id", hits_df["user_id"].unique(), "user"
    )
    nick_rows = cached_query(
        query_db,
        f"SELECT user_id, nick_name FROM expert_info WHERE {user_clause}",
        params=user_params,
        ttl=300,
    )
    nick_map = {row["user_id"]: row.get("nick_name") for row in nick_rows}

    playtype_names = hits_df["playtype_name"].unique().tolist()
    pt_clause, pt_params = make_in_clause("playtype_name", playtype_names, "ptname")
    stat_params = {**user_params, **pt_params}
    stats_rows = cached_query(
        query_db,
        f"""
        SELECT user_id, playtype_name, SUM(hit_count) AS total_hit_count
        FROM expert_hit_stat
        WHERE {user_clause} AND {pt_clause}
        GROUP BY user_id, playtype_name
        """,
        params=stat_params,
        ttl=300,
    )
    stats_map = {
        (row["user_id"], row["playtype_name"]): row.get("total_hit_count", 0)
        for row in stats_rows
    }

    hits_df["nick_name"] = hits_df["user_id"].map(nick_map)
    hits_df["total_hit_count"] = hits_df.apply(
        lambda row: stats_map.get((row["user_id"], row["playtype_name"]), 0),
        axis=1,
    )

    st.subheader("命中 AI 专家")
    col_expert, col_records, col_playtypes = st.columns(3)
    col_expert.metric("命中专家数", hits_df["user_id"].nunique())
    col_records.metric("命中记录数", len(hits_df))
    col_playtypes.metric("涉及玩法数", hits_df["playtype_id"].nunique())

    hits_view = hits_df[
        [
            "user_id",
            "nick_name",
            "playtype_name",
            "numbers",
            "total_hit_count",
        ]
    ].copy()
    hits_view.columns = [
        "user_id",
        "nick_name",
        "玩法",
        "本期推荐数字",
        "全期命中次数",
    ]
    st.dataframe(hits_view, use_container_width=True)
    download_csv_button(hits_view, "下载命中专家", "expert_hit_top_hits")

st.subheader("本期玩法命中率热力图")
if not open_code_clean:
    st.info("缺少开奖号码，无法计算命中率。")
else:
    total_counts = (
        prediction_df.groupby("playtype_id")["numbers"]
        .count()
        .reset_index(name="total")
    )
    hit_counts = (
        prediction_df[prediction_df.get("is_hit", False)]
        .groupby("playtype_id")["numbers"]
        .count()
        .reset_index(name="hit")
    )
    rate_df = total_counts.merge(hit_counts, how="left", on="playtype_id").fillna(0)
    rate_df["hit_rate"] = rate_df.apply(
        lambda row: row["hit"] / row["total"] if row["total"] else 0,
        axis=1,
    )
    rate_df["playtype_name"] = rate_df["playtype_id"].map(playtype_map)

    if rate_df.empty():
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
