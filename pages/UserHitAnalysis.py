from __future__ import annotations

from typing import Sequence

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    fetch_lottery_infos,
    fetch_playtypes,
    fetch_playtypes_for_issue,
    fetch_predictions,
)
from utils.numbers import match_prediction_hit, normalize_code, parse_tokens
from utils.ui import issue_picker, playtype_picker, render_open_info

st.set_page_config(page_title="专家多期命中分析", layout="wide")
st.header("UserHitAnalysis - 专家多期命中分析")

# 预加载玩法字典供跨期画像展示使用
_all_playtypes_df = fetch_playtypes()
PLAYTYPE_NAME_MAP: dict[int, str] = (
    {int(row.playtype_id): row.playtype_name for row in _all_playtypes_df.itertuples()}
    if not _all_playtypes_df.empty
    else {}
)

selected_issues = issue_picker(
    "user_hit_analysis_issues",
    mode="multi",
    label="期号",
)
if not selected_issues:
    st.warning("请至少选择一个期号。")
    st.stop()

# 以列表首项加载可用玩法，与旧版保持一致
selected_issue = selected_issues[0]
render_open_info(selected_issue, key="user_hit_analysis_open", show_metrics=False)
playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期号下无推荐数据。")
    st.stop()

issue_playtype_map = {int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()}
playtype_options = list(issue_playtype_map.keys())

selected_playtype_id = playtype_picker(
    "user_hit_analysis_playtype",
    mode="single",
    label="🎮 选择玩法",
    include=[str(pid) for pid in playtype_options],
)
if not selected_playtype_id:
    st.stop()
selected_playtype_id = int(selected_playtype_id)
selected_playtype_name = issue_playtype_map.get(
    int(selected_playtype_id), str(selected_playtype_id)
)

user_input = st.text_input("👤 输入专家 user_id")


def _fetch_predictions(
    issue_list: Sequence[str],
    *,
    playtype_ids: Sequence[int] | None = None,
    user_ids: Sequence[int] | None = None,
) -> pd.DataFrame:
    issue_tuple = tuple(issue_list)
    return fetch_predictions(
        issue_tuple,
        playtype_ids=playtype_ids,
        user_ids=user_ids,
        columns=["issue_name", "playtype_id", "user_id", "numbers"],
        ttl=None,
    )


def _fetch_open_infos(issue_list: Sequence[str]) -> dict[str, dict[str, object]]:
    return fetch_lottery_infos(tuple(issue_list), ttl=None)


def _fetch_expert_name(user_id: int) -> str:
    rows = query_db(
        "SELECT nick_name FROM expert_info WHERE user_id = :uid LIMIT 1",
        {"uid": user_id},
    )
    if rows and rows[0].get("nick_name"):
        return rows[0]["nick_name"]
    return "未知"


if st.button("🔍 批量查询专家多期命中"):
    raw_user = user_input.strip()
    if not raw_user:
        st.warning("请先输入专家 user_id。")
        st.stop()
    try:
        user_id = int(raw_user)
    except ValueError:
        st.error("user_id 必须是数字。")
        st.stop()

    history_issues: list[str] = list(dict.fromkeys(selected_issues))
    if not history_issues:
        st.warning("缺少历史期号用于分析。")
        st.stop()

    predictions_df = _fetch_predictions(
        history_issues,
        playtype_ids=[int(selected_playtype_id)],
        user_ids=[user_id],
    )
    if predictions_df.empty:
        st.info("所选范围内无预测记录。")
        st.stop()

    predictions_df["issue_name"] = predictions_df["issue_name"].astype(str)
    user_records = predictions_df
    if user_records.empty:
        st.info("该专家在所选期号内未给出推荐。")
        st.stop()

    nick_name = _fetch_expert_name(user_id)
    st.markdown(
        f"### 👤 当前专家：<code>{user_id}</code>（昵称：<code>{nick_name}</code>）",
        unsafe_allow_html=True,
    )

    info_map = _fetch_open_infos(history_issues)
    grouped = {issue: frame for issue, frame in user_records.groupby("issue_name", sort=False)}

    result_rows = []
    for issue in history_issues:
        sub_df = grouped.get(issue)
        open_info = info_map.get(issue, {})
        open_code = open_info.get("open_code") if open_info else None
        open_digits = set(normalize_code(open_code)) if open_code else set()

        if sub_df is None or sub_df.empty:
            result_rows.append(
                {
                    "期号": issue,
                    "推荐组合": "-",
                    "推荐组合数": 0,
                    "命中数": 0,
                    "命中数字数量": 0,
                    "开奖号码": open_code or "-",
                }
            )
            continue

        numbers_list = sub_df["numbers"].tolist()
        hit_count = 0
        hit_digits_total = 0
        for numbers in numbers_list:
            digits = set("".join(parse_tokens(numbers)))
            if open_code:
                if match_prediction_hit(selected_playtype_name, numbers, open_code):
                    hit_count += 1
                hit_digits_total += len(open_digits & digits)

        result_rows.append(
            {
                "期号": issue,
                "推荐组合": "、".join(numbers_list),
                "推荐组合数": len(numbers_list),
                "命中数": hit_count,
                "命中数字数量": hit_digits_total,
                "开奖号码": open_code or "-",
            }
        )

    result_df = pd.DataFrame(result_rows)
    if result_df.empty:
        st.info("无统计数据。")
    else:
        hit_issues = int((result_df["命中数"] > 0).sum())
        total_issues = len(result_df)
        hit_digits_sum = int(result_df["命中数字数量"].sum())
        miss_issues = total_issues - hit_issues

        result_df = result_df.sort_values("期号", ascending=False)
        st.markdown(
            f"### 📊 命中统计表（共 {total_issues} 期）命中：{hit_issues} 期，未命中：{miss_issues} 期，命中数字合计：{hit_digits_sum} 个"
        )
        st.dataframe(result_df, hide_index=True, use_container_width=True)

        chart_data = result_df[["期号", "命中数", "命中数字数量"]].copy()
        chart_data["期号"] = chart_data["期号"].astype(str)
        chart_long = chart_data.melt(
            id_vars="期号",
            value_vars=["命中数", "命中数字数量"],
            var_name="指标",
            value_name="数值",
        )
        chart = (
            alt.Chart(chart_long)
            .mark_line(point=True)
            .encode(
                x=alt.X("期号:N", sort=None),
                y=alt.Y("数值:Q"),
                color=alt.Color("指标:N", title="指标"),
                tooltip=["期号", "指标", "数值"],
            )
            .properties(width="container", height=360)
        )
        st.altair_chart(chart, use_container_width=True)

    st.session_state["user_hit_analysis"] = {
        "user_id": user_id,
        "nick_name": nick_name,
        "issues": history_issues,
    }

st.markdown("---")
st.markdown("## 🧠 专家综合画像")
if st.button("📌 查询专家综合画像"):
    cached = st.session_state.get("user_hit_analysis")
    if not cached:
        st.warning("请先执行【批量查询专家多期命中】。")
        st.stop()

    user_id = cached["user_id"]
    nick_name = cached.get("nick_name", "未知")
    history_issues = cached["issues"]
    if not history_issues:
        st.warning("缺少可用于画像的期号。")
        st.stop()

    history_tuple = tuple(history_issues)
    predictions_df = _fetch_predictions(history_tuple, user_ids=[user_id])
    if predictions_df.empty:
        st.info("无历史推荐数据用于画像分析。")
        st.stop()

    predictions_df["issue_name"] = predictions_df["issue_name"].astype(str)
    user_df = predictions_df
    if user_df.empty:
        st.info("该专家没有符合条件的历史推荐。")
        st.stop()

    info_map = _fetch_open_infos(history_tuple)

    summary_records = []
    for inner_playtype_id, sub_df in user_df.groupby("playtype_id"):
        inner_playtype_id = int(inner_playtype_id)
        inner_playtype_name = PLAYTYPE_NAME_MAP.get(inner_playtype_id, str(inner_playtype_id))
        total = len(sub_df)
        hit_count = 0
        hit_digits_sum = 0
        hit_issue_indices: list[int] = []

        for row in sub_df.itertuples():
            issue_name = str(row.issue_name)
            numbers = row.numbers
            open_info = info_map.get(issue_name)
            open_code = open_info.get("open_code") if open_info else None
            open_digits = set(normalize_code(open_code)) if open_code else set()
            digits = set("".join(parse_tokens(numbers)))

            if open_code and match_prediction_hit(inner_playtype_name, numbers, open_code):
                hit_count += 1
                hit_issue_indices.append(int(issue_name))
            hit_digits_sum += len(open_digits & digits)

        if hit_count > 1 and hit_issue_indices:
            hit_issue_indices.sort()
            computed_gaps = [j - i for i, j in zip(hit_issue_indices[:-1], hit_issue_indices[1:])]
            if computed_gaps:
                avg_gap = round(sum(computed_gaps) / len(computed_gaps), 1)
            else:
                avg_gap = "-"
        elif hit_count == 1:
            avg_gap = "1命中"
        else:
            avg_gap = "∞"

        summary_records.append(
            {
                "玩法": inner_playtype_name,
                "推荐期数": total,
                "命中期数": hit_count,
                "命中数字数量": hit_digits_sum,
                "平均命中间隔": avg_gap,
            }
        )

    if not summary_records:
        st.info("未能生成专家画像。")
    else:
        stats_df = pd.DataFrame(summary_records).sort_values("命中期数", ascending=False)
        st.markdown(f"### 🎯 专家综合画像（user_id: {user_id}，昵称：{nick_name}）")
        st.dataframe(stats_df, hide_index=True, use_container_width=True)

        chart = (
            alt.Chart(stats_df)
            .mark_bar()
            .encode(
                x=alt.X("命中期数:Q", title="命中期数"),
                y=alt.Y("玩法:N", sort="-x"),
                tooltip=[
                    "玩法",
                    "推荐期数",
                    "命中期数",
                    "命中数字数量",
                    "平均命中间隔",
                ],
            )
            .properties(width="container", height=360)
        )
        st.altair_chart(chart, use_container_width=True)
