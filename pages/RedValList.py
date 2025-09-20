from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_playtypes_for_issue
from utils.predictions import build_prediction_distribution
from utils.ui import issue_picker, playtype_picker, render_rank_position_calculator
from utils.numbers import parse_tokens
from utils.sql import make_in_clause


st.header("RedValList - 选号分布")

selected_issue = issue_picker(
    "red_val_issue",
    mode="single",
    label="期号",
)
if not selected_issue:
    st.stop()


playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期号下无推荐数据。")
    st.stop()

playtype_map = {
    int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()
}
playtype_ids = [str(pid) for pid in playtype_map.keys()]
raw_selection = playtype_picker(
    "red_val_playtype",
    mode="multi",
    label="玩法",
    include=playtype_ids,
    default=playtype_ids,
)
selected_playtypes = [int(pid) for pid in raw_selection]

if not selected_playtypes:
    st.warning("请至少选择一个玩法。")
    st.stop()

clause, params = make_in_clause("playtype_id", selected_playtypes, "pt")
params.update({"issue": selected_issue})
sql = f"""
    SELECT playtype_id, user_id, num
    FROM red_val_list
    WHERE issue_name = :issue
      AND {clause}
    ORDER BY id DESC
"""

try:
    rows = cached_query(query_db, sql, params=params, ttl=120)
except Exception as exc:  # pragma: no cover - 依赖外部数据库
    st.warning(f"查询选号分布失败：{exc}")
    rows = []


if not rows:
    fallback_rows = build_prediction_distribution(selected_issue, selected_playtypes)
    if fallback_rows:
        st.info("未查询到选号分布数据，已根据专家推荐实时生成分布，仅供参考。")
        rows = fallback_rows
    else:
        st.info("当前期号暂无选号分布或预测汇总数据。")

df = pd.DataFrame(rows)
if df.empty or "playtype_id" not in df:
    st.info("当前期号暂无选号分布或预测数据可展示。")
else:
    df["玩法"] = df["playtype_id"].map(playtype_map)
    df["号码集合"] = df.get("num", "").astype(str)

    display_df = df[["玩法", "号码集合"]]

    display_df.sort_values(by=["玩法"], inplace=True)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    rank_entries: list[tuple[str, list[str]]] = []
    for _, row in display_df.iterrows():
        digits = [n.strip() for n in str(row["号码集合"]).split(",") if n.strip()]
        if digits:
            rank_entries.append((row["玩法"], digits))

    render_rank_position_calculator(rank_entries, key="red_val_rank")

