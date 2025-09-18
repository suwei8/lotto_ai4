from __future__ import annotations

import collections

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_recent_issues
from utils.numbers import count_hits, normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button

st.header("FilterTool_MissV2 - 组合缺失筛选")

issues = fetch_recent_issues(limit=200)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("当前期号", options=issues)

lottery = fetch_lottery_info(selected_issue)
if lottery:
    st.caption(
        f"开奖号码：{lottery.get('open_code') or '未开奖'}丨和值：{lottery.get('sum')}丨跨度：{lottery.get('span')}"
    )

sql_playtypes = """
    SELECT DISTINCT ep.playtype_id, pd.playtype_name
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.issue_name = :issue
    ORDER BY ep.playtype_id
"""
playtype_rows = cached_query(
    query_db, sql_playtypes, params={"issue": selected_issue}, ttl=300
)
if not playtype_rows:
    st.info("未找到可用玩法。")
    st.stop()

playtype_df = pd.DataFrame(playtype_rows)
playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtype_df.itertuples()
}
selected_playtypes = st.multiselect(
    "选择玩法",
    options=list(playtype_map.keys()),
    default=list(playtype_map.keys()),
    format_func=lambda value: playtype_map.get(value, value),
)

if not selected_playtypes:
    st.warning("请选择至少一个玩法。")
    st.stop()

lookback_n = st.slider("回溯期数", min_value=5, max_value=50, value=20, step=5)
remove_duplicates = st.checkbox("去重同专家同玩法同号码", value=True)
enable_filter = st.checkbox("启用命中过滤", value=False)
filter_mode = st.selectbox(
    "过滤模式",
    options=("未启用", "未命中次数≤X", "区间筛选L-H", "连续命中", "连续未命中"),
)
miss_threshold = st.number_input("未命中阈值 X", min_value=0, value=5)
miss_low = st.number_input("区间下限 L", min_value=0, value=3)
miss_high = st.number_input("区间上限 H", min_value=1, value=10)

include_digits = st.multiselect("必须包含数字", options=[str(d) for d in range(10)])
exclude_digits = st.multiselect("排除数字", options=[str(d) for d in range(10)])

issue_index = issues.index(selected_issue) if selected_issue in issues else 0
lookback_slice = issues[issue_index + 1 : issue_index + 1 + lookback_n]
if not lookback_slice:
    st.info("回溯期数超出可用范围。")
    lookback_slice = []

history_rows = []
# 获取回溯开奖数据
open_map = {}
history_df = pd.DataFrame(columns=["issue_name", "playtype_id", "user_id", "numbers"])
if lookback_slice:
    lottery_clause, lottery_params = make_in_clause(
        "issue_name", lookback_slice, "hist"
    )
    sql_lottery = f"""
        SELECT issue_name, open_code
        FROM lottery_results
        WHERE {lottery_clause}
    """
    open_rows = cached_query(query_db, sql_lottery, params=lottery_params, ttl=300)
    open_map = {
        row["issue_name"]: normalize_code(row.get("open_code")) for row in open_rows
    }

    lookback_clause, lookback_params = make_in_clause(
        "issue_name", lookback_slice, "lb"
    )
    playtype_clause, playtype_params = make_in_clause(
        "playtype_id", [int(pid) for pid in selected_playtypes], "pt"
    )
    lookback_params.update(playtype_params)
    sql_history = f"""
        SELECT issue_name, playtype_id, user_id, numbers
        FROM expert_predictions
        WHERE {lookback_clause}
          AND {playtype_clause}
    """

    try:
        history_rows = cached_query(
            query_db, sql_history, params=lookback_params, ttl=300
        )
    except Exception as exc:
        st.warning(f"加载回溯数据失败：{exc}")
        history_rows = []

    history_df = pd.DataFrame(history_rows)
if remove_duplicates and not history_df.empty:
    history_df.drop_duplicates(
        subset=["issue_name", "playtype_id", "user_id", "numbers"], inplace=True
    )

# 计算命中情况
hit_records = collections.defaultdict(list)
for row in history_df.itertuples():
    open_code = open_map.get(row.issue_name)
    tokens = parse_tokens(row.numbers)
    hit = count_hits(tokens, open_code) > 0
    hit_records[row.user_id].append((row.issue_name, hit))

kept_users = set(history_df["user_id"].unique()) if history_rows else set()

if enable_filter and filter_mode != "未启用":
    filtered = set()
    for user_id, results in hit_records.items():
        misses = sum(1 for _, hit in results if not hit)
        if filter_mode == "未命中次数≤X":
            if misses <= miss_threshold:
                filtered.add(user_id)
        elif filter_mode == "区间筛选L-H":
            if miss_low <= misses <= miss_high:
                filtered.add(user_id)
        elif filter_mode == "连续命中":
            if all(hit for _, hit in results):
                filtered.add(user_id)
        elif filter_mode == "连续未命中":
            if all(not hit for _, hit in results):
                filtered.add(user_id)
    kept_users = filtered

# 当前期预测数据
current_clause, current_params = make_in_clause(
    "playtype_id", [int(pid) for pid in selected_playtypes], "cur"
)
current_params.update({"issue": selected_issue})
sql_current = f"""
    SELECT user_id, playtype_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue
      AND {current_clause}
"""
current_rows = cached_query(query_db, sql_current, params=current_params, ttl=300)
current_df = pd.DataFrame(current_rows)
if remove_duplicates and not current_df.empty:
    current_df.drop_duplicates(
        subset=["user_id", "playtype_id", "numbers"], inplace=True
    )

if kept_users:
    current_df = current_df[current_df["user_id"].isin(kept_users)]

if current_df.empty:
    st.info("无符合条件的专家推荐。")
    st.stop()

current_df["playtype_name"] = current_df["playtype_id"].apply(
    lambda pid: playtype_map.get(str(pid), pid)
)

if include_digits or exclude_digits:
    digit_include = set(include_digits)
    digit_exclude = set(exclude_digits)

    def _digit_filter(numbers: str) -> bool:
        digits = set("".join(parse_tokens(numbers)))
        if digit_include and not digit_include.issubset(digits):
            return False
        if digit_exclude and digit_exclude.intersection(digits):
            return False
        return True

    current_df = current_df[current_df["numbers"].apply(_digit_filter)]

    if current_df.empty:
        st.info("数字包含/排除条件过滤后无符合的推荐。")
        st.stop()

# 频次统计
freq_counter = collections.Counter()
for numbers in current_df["numbers"]:
    for token in parse_tokens(numbers):
        freq_counter.update(token)

freq_df = pd.DataFrame(
    {"digit": list(freq_counter.keys()), "count": list(freq_counter.values())}
).sort_values(by="count", ascending=False)

st.subheader("推荐数字频次")
st.dataframe(freq_df, use_container_width=True)

freq_chart = (
    alt.Chart(freq_df)
    .mark_bar()
    .encode(
        x=alt.X("digit:N", title="数字"),
        y=alt.Y("count:Q", title="频次"),
        tooltip=["digit", "count"],
    )
    .properties(width=600, height=300)
)
st.altair_chart(freq_chart, use_container_width=True)

download_csv_button(freq_df, "下载频次统计", "filter_tool_miss_v2_freq")

# 专家列表
user_clause, user_params = make_in_clause(
    "user_id", current_df["user_id"].unique().tolist(), "user"
)
sql_experts = f"""
    SELECT user_id, nick_name
    FROM expert_info
    WHERE {user_clause}
"""
expert_rows = cached_query(query_db, sql_experts, params=user_params, ttl=300)
expert_map = {row["user_id"]: row.get("nick_name") for row in expert_rows}

experts_summary = (
    current_df.groupby("user_id")["numbers"]
    .apply(lambda values: "; ".join(sorted(set(values))))
    .reset_index()
)
experts_summary["nick_name"] = experts_summary["user_id"].apply(
    lambda uid: expert_map.get(uid, "未知")
)

st.subheader("参与统计的专家")
experts_view = experts_summary[["user_id", "nick_name", "numbers"]]
st.dataframe(experts_view, use_container_width=True)
download_csv_button(experts_view, "下载专家列表", "filter_tool_miss_v2_experts")
