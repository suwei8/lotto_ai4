from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    fetch_lottery_info,
    fetch_playtypes_for_issue,
    fetch_predictions,
    fetch_recent_issues,
)
from utils.numbers import aggregate_digits, count_hits, normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button


@dataclass
class NumberCondition:
    playtypes: List[int]
    mode: str  # 包含 or 不包含
    match: str  # 任意匹配 or 全部匹配
    digits: List[str]


@dataclass
class HitCondition:
    playtype_id: int
    mode: str  # 上期命中/未命中/近N期命中M次
    recent_n: int = 5
    expected: int = 1
    operator: str = ">="


st.header("UserExpertFilterPlus - 推荐过滤器 Pro")

issues = fetch_recent_issues(limit=200)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期号下无推荐数据。")
    st.stop()

playtype_map = {
    int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()
}
playtype_options = list(playtype_map.keys())

target_playtype = st.selectbox(
    "目标玩法",
    options=playtype_options,
    format_func=lambda pid: playtype_map.get(pid, str(pid)),
)

st.subheader("推荐数字过滤条件")
condition_count = st.number_input("条件数量", min_value=0, max_value=5, value=1, step=1)
number_conditions: List[NumberCondition] = []
for idx in range(condition_count):
    with st.expander(f"条件 {idx + 1}", expanded=idx == 0):
        selected_pts = st.multiselect(
            "适用玩法",
            options=playtype_options,
            default=[target_playtype],
            key=f"num_cond_playtypes_{idx}",
            format_func=lambda pid: playtype_map.get(pid, str(pid)),
        )
        mode = st.selectbox(
            "模式", options=["包含", "不包含"], key=f"num_cond_mode_{idx}"
        )
        match_mode = st.selectbox(
            "匹配方式",
            options=["任意匹配", "全部匹配"],
            key=f"num_cond_match_{idx}",
            help="不包含模式固定视为全部匹配。",
        )
        digits = st.multiselect(
            "数字集合",
            options=[str(d) for d in range(10)],
            key=f"num_cond_digits_{idx}",
        )
        number_conditions.append(
            NumberCondition(
                playtypes=(
                    [int(pid) for pid in selected_pts]
                    if selected_pts
                    else playtype_options
                ),
                mode=mode,
                match=match_mode,
                digits=digits,
            )
        )

st.subheader("往期命中奖励过滤器")
lookback_n = st.slider("回溯期数", min_value=5, max_value=60, value=20, step=5)
remove_duplicates = st.checkbox("去重同专家同玩法同号码", value=True)

hit_condition_count = st.number_input(
    "命中过滤条件数量", min_value=0, max_value=3, value=1, step=1
)
hit_conditions: List[HitCondition] = []
for idx in range(hit_condition_count):
    with st.expander(f"命中奖励条件 {idx + 1}", expanded=False):
        playtype_id = st.selectbox(
            "玩法",
            options=playtype_options,
            key=f"hit_cond_playtype_{idx}",
            format_func=lambda pid: playtype_map.get(pid, str(pid)),
        )
        mode = st.selectbox(
            "模式",
            options=["上期命中", "上期未命中", "近N期命中M次"],
            key=f"hit_cond_mode_{idx}",
        )
        if mode == "近N期命中M次":
            col_recent, col_expected, col_op = st.columns(3)
            with col_recent:
                recent_n = st.slider(
                    "近 N 期",
                    min_value=3,
                    max_value=lookback_n,
                    value=min(10, lookback_n),
                    key=f"hit_recent_{idx}",
                )
            with col_expected:
                expected = st.number_input(
                    "命中次数",
                    min_value=0,
                    max_value=recent_n,
                    value=2,
                    key=f"hit_expected_{idx}",
                )
            with col_op:
                operator = st.selectbox(
                    "比较符",
                    options=[">", ">=", "=", "<", "<="],
                    key=f"hit_operator_{idx}",
                )
        else:
            recent_n = 1
            expected = 1
            operator = ">="
        hit_conditions.append(
            HitCondition(
                playtype_id=int(playtype_id),
                mode=mode,
                recent_n=int(recent_n),
                expected=int(expected),
                operator=operator,
            )
        )

lottery_info = fetch_lottery_info(selected_issue)
if lottery_info:
    st.caption(
        f"开奖号码：{lottery_info.get('open_code') or '未开奖'}丨和值：{lottery_info.get('sum')}丨跨度：{lottery_info.get('span')}"
    )

# 当前期预测
prediction_rows = cached_query(
    query_db,
    """
    SELECT user_id, playtype_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue
    """,
    params={"issue": selected_issue},
    ttl=120,
)
prediction_df = pd.DataFrame(prediction_rows)
if prediction_df.empty:
    st.info("当前期暂无推荐记录。")
    st.stop()

if remove_duplicates:
    prediction_df.drop_duplicates(
        subset=["user_id", "playtype_id", "numbers"], inplace=True
    )

# Prepare digit tokens
prediction_df["tokens"] = prediction_df["numbers"].apply(parse_tokens)

# Apply number conditions sequentially
for condition in number_conditions:
    if not condition.digits:
        continue
    applicable = prediction_df["playtype_id"].isin(condition.playtypes)

    def satisfies(tokens: Sequence[str]) -> bool:
        digits = set("".join(tokens))
        if condition.mode == "包含":
            if condition.match == "全部匹配":
                return set(condition.digits).issubset(digits)
            return bool(set(condition.digits).intersection(digits))
        # 不包含
        return set(condition.digits).isdisjoint(digits)

    mask = prediction_df["tokens"].apply(satisfies)
    prediction_df = prediction_df[(~applicable) | mask]

# Only keep target playtype for display but retain other playtypes for hit conditioning
filtered_df = prediction_df[prediction_df["playtype_id"] == target_playtype].copy()

if filtered_df.empty:
    st.info("数字过滤后无符合条件的推荐。")
    st.stop()

# Hit condition evaluation
if hit_conditions:
    start_idx = issues.index(selected_issue) if selected_issue in issues else 0
    lookback_slice = issues[start_idx + 1 : start_idx + 1 + lookback_n]
    history_playtypes = {cond.playtype_id for cond in hit_conditions}
    history_df = fetch_predictions(lookback_slice, playtype_ids=history_playtypes)
    if remove_duplicates and not history_df.empty:
        history_df.drop_duplicates(
            subset=["issue_name", "playtype_id", "user_id", "numbers"], inplace=True
        )

    open_map = {
        issue: normalize_code((lottery_info or {}).get("open_code"))
        for issue in [selected_issue]
    }
    if lookback_slice:
        lottery_clause, lottery_params = make_in_clause(
            "issue_name", lookback_slice, "hist"
        )
        sql_lottery = f"""
            SELECT issue_name, open_code
            FROM lottery_results
            WHERE {lottery_clause}
        """
        try:
            rows = cached_query(query_db, sql_lottery, params=lottery_params, ttl=120)
        except Exception:
            rows = []
        for row in rows:
            open_map[row["issue_name"]] = normalize_code(row.get("open_code"))

    history_df["tokens"] = history_df["numbers"].apply(parse_tokens)
    history_df["is_hit"] = history_df.apply(
        lambda row: count_hits(row["tokens"], open_map.get(row["issue_name"])) > 0,
        axis=1,
    )

    def evaluate_hit_condition(user_id: int, condition: HitCondition) -> bool:
        subset = history_df[
            (history_df["user_id"] == user_id)
            & (history_df["playtype_id"] == condition.playtype_id)
        ].sort_values("issue_name", ascending=False)
        if subset.empty:
            return False
        if condition.mode == "上期命中":
            return bool(subset.iloc[0]["is_hit"])
        if condition.mode == "上期未命中":
            return not bool(subset.iloc[0]["is_hit"])
        window = subset.head(condition.recent_n)
        hit_times = int(window["is_hit"].sum())
        if condition.operator == ">=":
            return hit_times >= condition.expected
        if condition.operator == ">":
            return hit_times > condition.expected
        if condition.operator == "=":
            return hit_times == condition.expected
        if condition.operator == "<":
            return hit_times < condition.expected
        return hit_times <= condition.expected

    user_pool = set(filtered_df["user_id"].unique())
    retained_users = [
        user
        for user in user_pool
        if all(evaluate_hit_condition(user, cond) for cond in hit_conditions)
    ]
    filtered_df = filtered_df[filtered_df["user_id"].isin(retained_users)]

if filtered_df.empty:
    st.info("命中过滤后无符合条件的推荐。")
    st.stop()

# Join nickname
user_clause, user_params = make_in_clause(
    "user_id", filtered_df["user_id"].unique().tolist(), "nick"
)
expert_rows = cached_query(
    query_db,
    f"""
    SELECT user_id, nick_name
    FROM expert_info
    WHERE {user_clause}
    """,
    params=user_params,
    ttl=120,
)
nick_map = {row["user_id"]: row.get("nick_name") for row in expert_rows}

filtered_df["nick_name"] = filtered_df["user_id"].map(nick_map)
filtered_df["digit_hits"] = filtered_df["tokens"].apply(
    lambda tokens: count_hits(
        tokens, normalize_code(lottery_info.get("open_code")) if lottery_info else None
    )
)
filtered_df["is_hit"] = filtered_df["digit_hits"] > 0

st.subheader("符合条件的专家")
result_view = filtered_df[["user_id", "nick_name", "numbers", "is_hit", "digit_hits"]]
st.dataframe(result_view, use_container_width=True)

download_csv_button(result_view, "下载过滤结果", "user_expert_filter_plus")

st.subheader("推荐数字热力图")
heatmap_records: List[Dict[str, str]] = []
for _, row in filtered_df.iterrows():
    for token in row["tokens"]:
        for digit in token:
            heatmap_records.append(
                {
                    "digit": digit,
                    "user_id": row["user_id"],
                    "nick_name": row.get("nick_name") or str(row["user_id"]),
                }
            )

heatmap_df = pd.DataFrame(heatmap_records)
if heatmap_df.empty:
    st.info("无法生成热力图数据。")
else:
    heatmap_df["count"] = 1
    digit_summary = heatmap_df.groupby("digit")["count"].sum().reset_index()
    chart = (
        alt.Chart(digit_summary)
        .mark_bar()
        .encode(
            x=alt.X("digit:N", title="数字"),
            y=alt.Y("count:Q", title="频次"),
            color=alt.value("#ff7f0e"),
            tooltip=["digit", "count"],
        )
        .properties(width=600, height=320)
    )
    st.altair_chart(chart, use_container_width=True)

    if lottery_info and lottery_info.get("open_code"):
        open_digits = set(normalize_code(lottery_info.get("open_code")))
        st.caption(f"开奖号码包含数字：{'、'.join(sorted(open_digits))}")

st.subheader("参与统计的专家及推荐项")
summary_df = (
    filtered_df.groupby(["user_id", "nick_name"])["numbers"]
    .apply(lambda vals: "；".join(sorted(set(vals))))
    .reset_index()
)
st.dataframe(summary_df, use_container_width=True)
