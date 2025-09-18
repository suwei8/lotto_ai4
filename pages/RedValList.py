from __future__ import annotations

import collections

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_playtypes, fetch_recent_issues
from utils.numbers import parse_tokens
from utils.sql import make_in_clause
from utils.ui import download_csv_button

st.header("RedValList - 选号分布")

issues = fetch_recent_issues(limit=200)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

lottery = fetch_lottery_info(selected_issue)
if lottery:
    st.caption(
        f"开奖号码：{lottery.get('open_code') or '未开奖'}丨和值：{lottery.get('sum')}丨跨度：{lottery.get('span')}"
    )

# 获取当期出现的玩法
sql_playtypes = """
    SELECT DISTINCT ep.playtype_id, pd.playtype_name
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.issue_name = :issue
    ORDER BY ep.playtype_id
"""

try:
    playtype_rows = cached_query(
        query_db, sql_playtypes, params={"issue": selected_issue}, ttl=300
    )
except Exception as exc:
    st.warning(f"获取玩法列表失败：{exc}")
    playtype_rows = []

if not playtype_rows:
    st.info("当前期未找到玩法数据。")
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

clause, params = make_in_clause(
    "playtype_id", [int(pid) for pid in selected_playtypes], "pt"
)
params.update({"issue": selected_issue})
sql = f"""
    SELECT playtype_id, user_id, num, val, id
    FROM red_val_list
    WHERE issue_name = :issue
      AND {clause}
    ORDER BY id DESC, playtype_id ASC
    LIMIT 1000
"""

try:
    rows = cached_query(query_db, sql, params=params, ttl=300)
except Exception as exc:
    st.warning(f"查询选号分布失败：{exc}")
    rows = []

if not rows:
    st.info("未查询到选号分布数据。")
    st.stop()

result_df = pd.DataFrame(rows)
result_df["playtype_name"] = result_df["playtype_id"].apply(
    lambda pid: playtype_map.get(str(pid), pid)
)

st.subheader("选号分布明细")
detail_view = result_df[["playtype_name", "num", "val", "user_id"]]
st.dataframe(detail_view, use_container_width=True)
download_csv_button(detail_view, "下载选号分布", "red_val_list_detail")

if lottery:
    st.subheader("开奖信息")
    st.json(lottery)

st.subheader("排行榜位置数字统计器")
digit_counter = collections.Counter()
for num in result_df["num"]:
    for digit in parse_tokens(num):
        digit_counter.update(digit)

if digit_counter:
    stats_df = pd.DataFrame(
        {"digit": list(digit_counter.keys()), "count": list(digit_counter.values())}
    ).sort_values(by="count", ascending=False)
    st.dataframe(stats_df, use_container_width=True)
    download_csv_button(stats_df, "下载数字统计", "red_val_list_digits")
    digit_chart = (
        alt.Chart(stats_df)
        .mark_bar()
        .encode(
            x=alt.X("digit:N", title="数字"),
            y=alt.Y("count:Q", title="出现次数"),
            color=alt.value("#1f77b4"),
            tooltip=["digit", "count"],
        )
        .properties(width=600, height=320)
    )
    st.altair_chart(digit_chart, use_container_width=True)
else:
    st.info("无法解析号码集合为数字。")
