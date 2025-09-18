from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes
from utils.numbers import count_hits, parse_tokens
from utils.ui import (
    dataframe_with_pagination,
    display_issue_summary,
    download_csv_button,
    issue_range_selector,
)

st.header("UserExpertHitStat - 专家命中统计")

start_issue, end_issue, available_issues = issue_range_selector(
    "user_expert_hit_stat", default_window=30
)

selected_issue_subset = st.multiselect(
    "指定统计期号（可多选，留空则使用上方区间）",
    options=available_issues,
    default=available_issues[:5],
    help="多选用于精准控制统计窗口；如不选择则按上方期号区间统计。",
)

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空，无法进行统计分析。")
    st.stop()

labels = {str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()}
playtype_choice = st.selectbox(
    "选择玩法",
    options=list(labels.keys()),
    format_func=lambda value: labels.get(value, value),
)
selected_playtype_name = labels.get(playtype_choice, playtype_choice)

col_min_hit, col_min_rate, col_limit = st.columns(3)
with col_min_hit:
    min_hit_count = st.number_input("最少命中次数", min_value=0, value=5, step=1)
with col_min_rate:
    min_hit_rate = st.slider(
        "最低命中率", min_value=0.0, max_value=1.0, step=0.01, value=0.2
    )
with col_limit:
    top_limit = st.slider("Top N", min_value=20, max_value=500, step=10, value=200)

filters = ["s.playtype_name = :playtype_name"]
params = {
    "playtype_name": selected_playtype_name,
    "min_hit": int(min_hit_count),
    "min_rate": float(min_hit_rate),
    "limit": int(top_limit),
}

if selected_issue_subset:
    issue_placeholders = ", ".join(
        [":issue_" + str(idx) for idx in range(len(selected_issue_subset))]
    )
    filters.append(f"s.issue_name IN ({issue_placeholders})")
    params.update(
        {f"issue_{idx}": issue for idx, issue in enumerate(selected_issue_subset)}
    )
else:
    filters.append("(:start_issue IS NULL OR s.issue_name >= :start_issue)")
    filters.append("(:end_issue IS NULL OR s.issue_name <= :end_issue)")
    params.update({"start_issue": start_issue, "end_issue": end_issue})

where_clause = " AND ".join(filters)

sql = f"""
    SELECT
        s.user_id,
        COALESCE(info.nick_name, CONCAT('专家', s.user_id)) AS nick_name,
        SUM(s.total_count) AS total_count,
        SUM(s.hit_count) AS hit_count,
        SUM(s.hit_number_count) AS hit_number_count,
        AVG(s.avg_hit_gap) AS avg_hit_gap,
        ROUND(SUM(s.hit_count) / NULLIF(SUM(s.total_count), 0), 4) AS hit_rate
    FROM expert_hit_stat s
    LEFT JOIN expert_info info ON info.user_id = s.user_id
    WHERE {where_clause}
    GROUP BY s.user_id, info.nick_name
    HAVING SUM(s.hit_count) >= :min_hit
       AND ROUND(SUM(s.hit_count) / NULLIF(SUM(s.total_count), 0), 4) >= :min_rate
    ORDER BY hit_rate DESC, hit_count DESC, total_count DESC
    LIMIT :limit
"""

try:
    rows = cached_query(query_db, sql, params=params, ttl=300)
except Exception as exc:
    st.warning(f"查询命中统计失败：{exc}")
    st.stop()

if not rows:
    st.info("未查询到符合条件的专家。")
    st.stop()

frame = pd.DataFrame(rows)
frame.sort_values(by="hit_rate", ascending=False, inplace=True)
frame.reset_index(drop=True, inplace=True)
if "avg_hit_gap" in frame:
    frame["avg_hit_gap"] = frame["avg_hit_gap"].fillna(0)

metrics = frame[["hit_count", "hit_number_count", "total_count"]].sum()
col_metrics = st.columns(3)
col_metrics[0].metric("累计命中次数", int(metrics.get("hit_count", 0)))
col_metrics[1].metric("命中号码覆盖数", int(metrics.get("hit_number_count", 0)))
col_metrics[2].metric("预测总次数", int(metrics.get("total_count", 0)))

subset, _, _ = dataframe_with_pagination(
    frame, page_size=50, key_prefix="user_expert_hit_stat"
)
st.dataframe(subset, use_container_width=True)

chart = (
    alt.Chart(frame)
    .mark_circle(size=60)
    .encode(
        x=alt.X("total_count:Q", title="预测期数"),
        y=alt.Y("hit_rate:Q", title="命中率"),
        size=alt.Size("hit_count:Q", title="命中次数"),
        color=alt.Color(
            "hit_rate:Q", title="命中率", scale=alt.Scale(scheme="tealblues")
        ),
        tooltip=["user_id", "nick_name", "hit_rate", "hit_count", "total_count"],
    )
    .properties(width="container", height=400)
)
st.altair_chart(chart, use_container_width=True)

gap_chart = (
    alt.Chart(frame)
    .mark_line(point=True)
    .encode(
        x=alt.X("nick_name:N", sort="-y", title="专家"),
        y=alt.Y("avg_hit_gap:Q", title="平均命中间隔"),
        tooltip=["user_id", "nick_name", "avg_hit_gap"],
    )
    .properties(width="container", height=260)
)
st.altair_chart(gap_chart, use_container_width=True)

download_csv_button(frame, label="下载命中统计", key="user_expert_hit_stat")
display_issue_summary(start_issue, end_issue)
if selected_issue_subset:
    st.caption(f"当前精确统计期号：{', '.join(selected_issue_subset)}")

st.subheader("命中详情下钻")
selected_user = st.selectbox(
    "选择需要下钻的专家",
    options=frame["user_id"].astype(str).tolist(),
)
selected_issue = st.selectbox(
    "选择期号",
    options=["最新"] + available_issues,
    index=0,
)
issue_filter = None if selected_issue == "最新" else selected_issue

sql_detail = """
    SELECT
        p.issue_name,
        p.numbers,
        r.open_code,
        r.open_time
    FROM expert_predictions p
    JOIN lottery_results r ON r.issue_name = p.issue_name
    WHERE p.user_id = :user_id
      AND p.playtype_id = (
          SELECT playtype_id FROM playtype_dict WHERE playtype_name = :playtype_name LIMIT 1
      )
      AND (:start_issue IS NULL OR p.issue_name >= :start_issue)
      AND (:end_issue IS NULL OR p.issue_name <= :end_issue)
      AND (:issue_filter IS NULL OR p.issue_name = :issue_filter)
    ORDER BY p.issue_name DESC
    LIMIT 300
"""
detail_params = {
    "user_id": selected_user,
    "playtype_name": selected_playtype_name,
    "start_issue": start_issue,
    "end_issue": end_issue,
    "issue_filter": issue_filter,
}

try:
    detail_rows = cached_query(query_db, sql_detail, params=detail_params, ttl=300)
except Exception as exc:
    st.warning(f"加载专家明细失败：{exc}")
    detail_rows = []

if detail_rows:
    detail_df = pd.DataFrame(detail_rows)
    detail_df["tokens"] = detail_df["numbers"].apply(parse_tokens)
    detail_df["命中次数"] = detail_df.apply(
        lambda row: count_hits(row["tokens"], row.get("open_code")), axis=1
    )
    detail_df["是否命中"] = detail_df["命中次数"] > 0
    st.dataframe(detail_df.drop(columns=["tokens"]), use_container_width=True)
    download_csv_button(
        detail_df.drop(columns=["tokens"]),
        label="下载专家明细",
        key="user_expert_hit_stat_detail",
    )
else:
    st.info("当前条件未查询到明细数据。")
