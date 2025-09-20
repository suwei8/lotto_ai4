from __future__ import annotations

import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")

from db.connection import query_db
from utils.cache import cached_query
from utils.ui import issue_picker, expert_picker, render_open_info

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

selected_issue = issue_picker(
    "userid_query_issue",
    mode="single",
    label="选择期号",
)
if not selected_issue:
    st.stop()

render_open_info(selected_issue, key="userid_query_open", show_metrics=False)

user_id, expert_map = expert_picker(
    "userid_query_expert",
    issue=selected_issue,
    allow_manual=True,
    manual_label="或手动输入专家 user_id",
)
if not user_id:
    st.info("请输入专家 user_id。")
    st.stop()

nick_name = expert_map.get(user_id)
if nick_name:
    st.caption(f"专家昵称：{nick_name}")
else:
    st.caption("专家昵称：未收录，仍可查询推荐记录")

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
    st.dataframe(df, width="stretch")
else:
    st.info("未查询到该专家在该期的推荐记录。")

