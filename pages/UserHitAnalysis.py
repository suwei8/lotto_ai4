from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_experts, fetch_playtypes
from utils.numbers import count_digit_hits, count_hits, parse_tokens
from utils.ui import (
    dataframe_with_pagination,
    display_issue_summary,
    download_csv_button,
    issue_multiselect,
    issue_range_selector,
)


def _average_gap(issue_list: list[str]) -> str:
    numeric = []
    for issue in issue_list:
        try:
            numeric.append(int(issue))
        except (TypeError, ValueError):
            continue
    if len(numeric) <= 1:
        return "∞"
    numeric.sort()
    diffs = [b - a for a, b in zip(numeric, numeric[1:]) if b >= a]
    if not diffs:
        return "∞"
    avg = sum(diffs) / len(diffs)
    return f"{avg:.2f}"


st.header("UserHitAnalysis - 专家多期命中分析")

start_issue, end_issue, issues = issue_range_selector(
    "user_hit_analysis", default_window=30
)
manual_issues = issue_multiselect(
    "user_hit_analysis_manual",
    label="精准选择期号（可多选）",
    max_default=10,
    source="predictions",
)

display_issue_summary(start_issue, end_issue)
if manual_issues:
    st.caption(f"已选择自定义期号：{', '.join(manual_issues)}")

experts = fetch_experts(limit=500)
if experts.empty:
    st.warning("未能获取专家列表。")
    st.stop()

expert_options = experts["user_id"].astype(str).tolist()
labels = {str(row.user_id): row.nick_name for row in experts.itertuples()}

selected_user = st.selectbox(
    "选择专家",
    options=expert_options,
    format_func=lambda value: labels.get(value, value),
)

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空，无法继续分析。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()
}
selected_playtype = st.selectbox(
    "选择玩法",
    options=list(playtype_map.keys()),
    format_func=lambda value: playtype_map.get(value, value),
)

params = {"user_id": selected_user, "playtype_id": int(selected_playtype)}
filters = ["ep.user_id = :user_id", "ep.playtype_id = :playtype_id"]

if manual_issues:
    issue_placeholders = ", ".join(
        [":issue_" + str(idx) for idx in range(len(manual_issues))]
    )
    filters.append(f"ep.issue_name IN ({issue_placeholders})")
    params.update({f"issue_{idx}": issue for idx, issue in enumerate(manual_issues)})
else:
    filters.append("(:start_issue IS NULL OR ep.issue_name >= :start_issue)")
    filters.append("(:end_issue IS NULL OR ep.issue_name <= :end_issue)")
    params.update({"start_issue": start_issue, "end_issue": end_issue})

where_clause = " AND ".join(filters)

sql = f"""
    SELECT
        ep.issue_name,
        ep.numbers,
        lr.open_code,
        lr.open_time
    FROM expert_predictions ep
    LEFT JOIN lottery_results lr ON lr.issue_name = ep.issue_name
    WHERE {where_clause}
    ORDER BY ep.issue_name DESC
    LIMIT 500
"""

try:
    rows = cached_query(query_db, sql, params=params, ttl=300)
except Exception as exc:
    st.warning(f"查询命中详情失败：{exc}")
    st.stop()

if not rows:
    st.info("当前条件未获取到推荐记录。")
else:
    detail_df = pd.DataFrame(rows)
    detail_df["tokens"] = detail_df["numbers"].apply(parse_tokens)
    detail_df["token_count"] = detail_df["tokens"].apply(len)
    detail_df["hit_count"] = detail_df.apply(
        lambda row: count_hits(row["tokens"], row.get("open_code")), axis=1
    )
    detail_df["hit_digits"] = detail_df.apply(
        lambda row: count_digit_hits(row["tokens"], row.get("open_code")), axis=1
    )
    detail_df.sort_values(by="issue_name", ascending=False, inplace=True)
    detail_df["是否命中"] = detail_df["hit_count"] > 0
    metrics_cols = st.columns(3)
    metrics_cols[0].metric("命中期数", int((detail_df["hit_count"] > 0).sum()))
    metrics_cols[1].metric("命中组合数", int(detail_df["hit_count"].sum()))
    metrics_cols[2].metric("命中数字数量", int(detail_df["hit_digits"].sum()))

    subset, _, _ = dataframe_with_pagination(
        detail_df, page_size=30, key_prefix="user_hit_analysis"
    )
    st.dataframe(subset.drop(columns=["tokens"]), use_container_width=True)
    download_csv_button(
        detail_df.drop(columns=["tokens"]), "下载推荐明细", "user_hit_analysis_detail"
    )

    chart_data = detail_df[["issue_name", "hit_count", "hit_digits"]].copy()
    chart_data = chart_data.sort_values("issue_name")
    chart = (
        alt.Chart(chart_data)
        .transform_fold(["命中组合数", "命中数字数"], value="数值", key="指标")
        .mark_line(point=True)
        .encode(
            x=alt.X("issue_name:N", title="期号", sort=None),
            y=alt.Y("数值:Q"),
            color="指标:N",
        )
        .properties(width="container", height=400)
    )
    st.altair_chart(chart, use_container_width=True)

# 画像统计
profile_params = {"user_id": selected_user}
profile_filters = ["ep.user_id = :user_id"]
if manual_issues:
    issue_placeholders = ", ".join(
        [":p_issue_" + str(idx) for idx in range(len(manual_issues))]
    )
    profile_filters.append(f"ep.issue_name IN ({issue_placeholders})")
    profile_params.update(
        {f"p_issue_{idx}": issue for idx, issue in enumerate(manual_issues)}
    )
else:
    profile_filters.append("(:start_issue IS NULL OR ep.issue_name >= :start_issue)")
    profile_filters.append("(:end_issue IS NULL OR ep.issue_name <= :end_issue)")
    profile_params.update({"start_issue": start_issue, "end_issue": end_issue})

profile_where = " AND ".join(profile_filters)

sql_profile = f"""
    SELECT
        ep.issue_name,
        ep.playtype_id,
        pd.playtype_name,
        ep.numbers,
        lr.open_code
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    LEFT JOIN lottery_results lr ON lr.issue_name = ep.issue_name
    WHERE {profile_where}
    ORDER BY ep.issue_name DESC
    LIMIT 1000
"""

try:
    profile_rows = cached_query(query_db, sql_profile, params=profile_params, ttl=300)
except Exception as exc:
    st.warning(f"加载专家画像失败：{exc}")
    profile_rows = []

if profile_rows:
    profile_df = pd.DataFrame(profile_rows)
    profile_df["tokens"] = profile_df["numbers"].apply(parse_tokens)
    profile_df["hit_count"] = profile_df.apply(
        lambda row: count_hits(row["tokens"], row.get("open_code")), axis=1
    )
    profile_df["hit_digits"] = profile_df.apply(
        lambda row: count_digit_hits(row["tokens"], row.get("open_code")), axis=1
    )

    summary_records = []
    for (playtype_id, playtype_name), group in profile_df.groupby(
        ["playtype_id", "playtype_name"]
    ):
        issues_hit = group.loc[group["hit_count"] > 0, "issue_name"].tolist()
        summary_records.append(
            {
                "playtype_id": playtype_id,
                "playtype_name": playtype_name,
                "recommend_count": len(group),
                "hit_issue_count": int((group["hit_count"] > 0).sum()),
                "hit_combination_count": int(group["hit_count"].sum()),
                "hit_digit_count": int(group["hit_digits"].sum()),
                "avg_hit_gap": _average_gap(issues_hit),
            }
        )
    if not summary_records:
        st.info("未能根据当前条件生成玩法画像统计。")
    else:
        summary_df = pd.DataFrame(summary_records)
        st.subheader("玩法画像概览")
        st.dataframe(summary_df, use_container_width=True)
        download_csv_button(summary_df, "下载玩法画像", "user_hit_analysis_profile")

        bar_chart = (
            alt.Chart(summary_df)
            .mark_bar()
            .encode(
                x=alt.X("playtype_name:N", title="玩法", sort="-y"),
                y=alt.Y("hit_issue_count:Q", title="命中期数"),
                tooltip=[
                    "playtype_name",
                    "recommend_count",
                    "hit_issue_count",
                    "avg_hit_gap",
                ],
                color="playtype_name:N",
            )
            .properties(width="container", height=400)
        )
        st.altair_chart(bar_chart, use_container_width=True)
else:
    st.info("未获取到该专家的玩法画像数据。")
