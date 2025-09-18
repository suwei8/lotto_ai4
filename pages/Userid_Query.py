from __future__ import annotations

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_experts, fetch_recent_issues
from utils.ui import download_csv_button

PLAYTYPE_ORDER = [
    "独胆",
    "双胆",
    "三胆",
    "杀一码",
    "杀二码",
    "杀三码",
    "百位定",
    "十位定",
    "个位定",
    "和值",
    "跨度",
]


def _playtype_sort_key(name: str) -> int:
    try:
        return PLAYTYPE_ORDER.index(name)
    except ValueError:
        return len(PLAYTYPE_ORDER)


st.header("Userid_Query - 按期号查看专家推荐")

issues = fetch_recent_issues(limit=200)
if not issues:
    st.warning("未能获取期号列表。")
    st.stop()

selected_issue = st.selectbox("选择期号", options=issues)

experts = fetch_experts(limit=500)
expert_map = {str(row.user_id): row.nick_name for row in experts.itertuples()}
default_user = next(iter(expert_map.keys()), "")
user_id = st.text_input("输入专家 user_id", value=default_user)
if not user_id:
    st.info("请输入专家 user_id。")
    st.stop()

nick_name = expert_map.get(user_id)
if nick_name:
    st.caption(f"专家昵称：{nick_name}")

sql_predictions = """
    SELECT
        pd.playtype_name,
        ep.numbers
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.issue_name = :issue_name
      AND ep.user_id = :user_id
    ORDER BY pd.playtype_id
"""
pred_params = {"issue_name": selected_issue, "user_id": user_id}

try:
    predictions = cached_query(query_db, sql_predictions, params=pred_params, ttl=300)
except Exception as exc:
    st.warning(f"查询专家推荐失败：{exc}")
    predictions = []

if predictions:
    df = pd.DataFrame(predictions).drop_duplicates()
    df["sort_key"] = df["playtype_name"].apply(_playtype_sort_key)
    df.sort_values(by=["sort_key", "playtype_name"], inplace=True)
    df.drop(columns=["sort_key"], inplace=True)
    st.dataframe(df, use_container_width=True)
    download_csv_button(df, "下载推荐", "userid_query_recommendations")
else:
    st.info("未查询到该专家在该期的推荐记录。")

sql_lottery = """
    SELECT open_code, `sum`, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    WHERE issue_name = :issue_name
    LIMIT 1
"""
try:
    lottery_rows = cached_query(
        query_db, sql_lottery, params={"issue_name": selected_issue}, ttl=300
    )
except Exception as exc:
    st.warning(f"获取开奖信息失败：{exc}")
    lottery_rows = []

if lottery_rows:
    st.subheader("开奖信息")
    st.json(lottery_rows[0])
else:
    st.info("未找到该期的开奖信息。")
