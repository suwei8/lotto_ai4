from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes
from utils.sql import make_in_clause
from utils.ui import (
    dataframe_with_pagination,
    display_issue_summary,
    download_csv_button,
    issue_range_selector,
)


def _load_rankings(
    start_issue: str | None,
    end_issue: str | None,
    playtype_names: list[str],
    limit: int,
):
    playtype_clause, playtype_params = make_in_clause(
        "s.playtype_name", playtype_names, "pt"
    )
    sql = f"""
        SELECT
            s.user_id,
            COALESCE(info.nick_name, CONCAT('专家', s.user_id)) AS nick_name,
            s.playtype_name,
            s.total_count,
            s.hit_count,
            s.hit_number_count,
            s.avg_hit_gap,
            ROUND(CASE WHEN s.total_count = 0 THEN 0 ELSE s.hit_count / s.total_count END, 4) AS hit_rate
        FROM expert_hit_stat s
        LEFT JOIN expert_info info ON info.user_id = s.user_id
        WHERE (:start_issue IS NULL OR s.issue_name >= :start_issue)
          AND (:end_issue IS NULL OR s.issue_name <= :end_issue)
          AND {playtype_clause}
        ORDER BY hit_rate DESC, s.hit_count DESC, s.avg_hit_gap ASC
        LIMIT :limit
    """
    params: dict[str, object] = {
        "start_issue": start_issue,
        "end_issue": end_issue,
        "limit": int(limit),
        **playtype_params,
    }
    return cached_query(query_db, sql, params=params, ttl=300)


def _load_detail(
    user_id: str,
    playtype_name: str,
    start_issue: str | None,
    end_issue: str | None,
):
    sql = """
        SELECT
            p.issue_name,
            p.numbers,
            r.open_code,
            r.open_time
        FROM expert_predictions p
        JOIN lottery_results r ON r.issue_name = p.issue_name
        WHERE p.user_id = :user_id
          AND (:start_issue IS NULL OR p.issue_name >= :start_issue)
          AND (:end_issue IS NULL OR p.issue_name <= :end_issue)
          AND p.playtype_id = (
              SELECT d.playtype_id
              FROM playtype_dict d
              WHERE d.playtype_name = :playtype_name
              LIMIT 1
          )
        ORDER BY p.issue_name DESC
        LIMIT 500
    """
    params = {
        "user_id": user_id,
        "playtype_name": playtype_name,
        "start_issue": start_issue,
        "end_issue": end_issue,
    }
    return cached_query(query_db, sql, params=params, ttl=300)


def _mark_hit(numbers: str | None, open_code: str | None) -> bool:
    if not numbers or not open_code:
        return False
    cleaned_target = open_code.replace(" ", "").replace(",", "").strip()
    candidates = [
        candidate.replace(" ", "").replace(",", "").strip()
        for candidate in numbers.replace("|", ",").split(",")
        if candidate.strip()
    ]
    return cleaned_target in candidates


st.header("Expert Hit Top - 专家命中排行榜")

start_issue, end_issue, _ = issue_range_selector("expert_hit_top", default_window=30)

playtype_df = fetch_playtypes()
if playtype_df.empty:
    st.warning("无法获取玩法字典，排行榜功能不可用。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtype_df.itertuples()
}
selected_ids = st.multiselect(
    "选择玩法",
    options=list(playtype_map.keys()),
    default=list(playtype_map.keys()),
    format_func=lambda value: playtype_map.get(value, value),
)
selected_names = [playtype_map.get(value, value) for value in selected_ids]
if not selected_names:
    st.warning("请至少选择一个玩法。")
    st.stop()

col_topn, col_sort, col_order = st.columns(3)
with col_topn:
    top_n = st.slider("Top N", min_value=20, max_value=500, value=50, step=10)
with col_sort:
    sort_field = st.selectbox(
        "排序指标",
        options=[
            ("hit_rate", "命中率"),
            ("hit_count", "命中次数"),
            ("total_count", "预测次数"),
            ("avg_hit_gap", "平均命中间隔"),
        ],
        format_func=lambda item: item[1],
    )[0]
with col_order:
    sort_ascending = (
        st.radio(
            "排序方式",
            options=[("desc", "降序"), ("asc", "升序")],
            format_func=lambda item: item[1],
            horizontal=True,
        )[0]
        == "asc"
    )

try:
    rows = _load_rankings(start_issue, end_issue, selected_names, top_n)
except Exception as exc:
    st.warning(f"查询排行榜失败：{exc}")
    st.stop()

if not rows:
    st.info("在当前条件下未找到排行榜数据。")
    st.stop()

frame = pd.DataFrame(rows)
frame.sort_values(by=sort_field, ascending=sort_ascending, inplace=True)
frame.reset_index(drop=True, inplace=True)

st.success(f"共加载 {len(frame)} 条专家统计记录。")

subset, _, _ = dataframe_with_pagination(
    frame, page_size=50, key_prefix="expert_hit_top"
)
st.dataframe(subset, use_container_width=True)

download_csv_button(frame, label="下载排行榜 CSV", key="expert_hit_top_rankings")
display_issue_summary(start_issue, end_issue)

chart = (
    alt.Chart(frame)
    .mark_bar()
    .encode(
        x=alt.X("nick_name:N", sort="-y", title="专家"),
        y=alt.Y("hit_rate:Q", title="命中率"),
        color="playtype_name:N",
        tooltip=["user_id", "nick_name", "hit_rate", "hit_count", "total_count"],
    )
    .properties(width="container", height=400)
)
st.altair_chart(chart, use_container_width=True)

st.subheader("玩法命中热力图")
playtype_pivot = (
    frame.groupby("playtype_name")[["hit_rate", "hit_count", "total_count"]]
    .agg({"hit_rate": "mean", "hit_count": "sum", "total_count": "sum"})
    .reset_index()
)
if not playtype_pivot.empty:
    pivot_long = playtype_pivot.rename(
        columns={
            "hit_rate": "平均命中率",
            "hit_count": "命中次数",
            "total_count": "预测次数",
        }
    ).melt(id_vars="playtype_name", var_name="指标", value_name="数值")

    pivot_chart = (
        alt.Chart(pivot_long)
        .mark_rect()
        .encode(
            x=alt.X("playtype_name:N", title="玩法"),
            y=alt.Y("指标:N"),
            color=alt.Color("数值:Q", scale=alt.Scale(scheme="blues")),
            tooltip=["playtype_name", "指标", alt.Tooltip("数值:Q", format=".4f")],
        )
        .properties(width="container", height=240)
    )
    st.altair_chart(pivot_chart, use_container_width=True)
else:
    st.info("暂无玩法聚合数据。")

st.subheader("专家逐期明细")
selected_user_id = st.selectbox(
    "选择专家（按 user_id）",
    options=frame["user_id"].astype(str).tolist(),
)
selected_playtype = frame.loc[
    frame["user_id"].astype(str) == selected_user_id, "playtype_name"
].iloc[0]

try:
    detail_rows = _load_detail(
        selected_user_id, selected_playtype, start_issue, end_issue
    )
except Exception as exc:
    st.warning(f"加载专家明细失败：{exc}")
    detail_rows = []

if detail_rows:
    detail_df = pd.DataFrame(detail_rows)
    detail_df["is_hit"] = detail_df.apply(
        lambda row: _mark_hit(row.get("numbers"), row.get("open_code")), axis=1
    )
    st.dataframe(detail_df, use_container_width=True)
    download_csv_button(detail_df, label="下载专家详情", key="expert_hit_top_detail")
else:
    st.info("暂无专家明细数据。")
