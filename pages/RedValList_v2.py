from __future__ import annotations

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.sql import make_in_clause
from utils.ui import (
    issue_picker,
    playtype_picker,
    render_open_info,
    render_rank_position_calculator,
)

st.set_page_config(page_title="Lotto AI", layout="wide")

st.header("RedValList_v2 - 选号分布 (V2)")

sql_issues = """
    SELECT DISTINCT issue_name
    FROM red_val_list_v2
    ORDER BY issue_name DESC
    LIMIT 200
"""

try:
    issue_rows = cached_query(query_db, sql_issues, params=None, ttl=600)
except Exception as exc:
    st.warning(f"获取期号列表失败：{exc}")
    issue_rows = []

if not issue_rows:
    st.info("v2 数据表暂无期号。")
    st.stop()

issues = [row["issue_name"] for row in issue_rows]
selected_issue = issue_picker(
    "red_val_v2_issue",
    mode="single",
    options=issues,
    label="选择期号",
)
if not selected_issue:
    st.stop()

render_open_info(selected_issue, key="red_val_v2_open", show_metrics=False)

sql_playtypes = """
    SELECT DISTINCT v2.playtype_id, pd.playtype_name
    FROM red_val_list_v2 v2
    JOIN playtype_dict pd ON pd.playtype_id = v2.playtype_id
    WHERE v2.issue_name = :issue
    ORDER BY v2.playtype_id
"""
playtype_rows = cached_query(query_db, sql_playtypes, params={"issue": selected_issue}, ttl=600)
if not playtype_rows:
    st.info("该期未找到玩法数据。")
    st.stop()

playtype_df = pd.DataFrame(playtype_rows)
playtype_map = {str(row.playtype_id): row.playtype_name for row in playtype_df.itertuples()}
raw_playtypes = playtype_picker(
    "red_val_v2_playtypes",
    mode="multi",
    label="选择玩法",
    include=list(playtype_map.keys()),
    default=list(playtype_map.keys()),
)
selected_playtypes = [int(pid) for pid in raw_playtypes]

if not selected_playtypes:
    st.warning("请选择至少一个玩法。")
    st.stop()

clause, params = make_in_clause("playtype_id", [int(pid) for pid in selected_playtypes], "pt")
params.update({"issue": selected_issue})

sql = f"""
    SELECT id, user_id, playtype_id, num, val, type,
           rank_count,
           hit_count_map,
           serial_hit_count_map,
           series_not_hit_count_map,
           max_serial_hit_count_map,
           max_series_not_hit_count_map,
           his_max_serial_hit_count_map,
           his_max_series_not_hit_count_map
    FROM red_val_list_v2
    WHERE issue_name = :issue
      AND {clause}
    ORDER BY id DESC, playtype_id ASC
    LIMIT 1000
"""

try:
    rows = cached_query(query_db, sql, params=params, ttl=300)
except Exception as exc:
    st.warning(f"查询 v2 数据失败：{exc}")
    rows = []

if not rows:
    st.info("v2 表中无匹配数据。")
    st.stop()

result_df = pd.DataFrame(rows)
result_df["playtype_name"] = result_df["playtype_id"].apply(
    lambda pid: playtype_map.get(str(pid), pid)
)

st.subheader("选号分布 V2 明细")
display_columns = [
    "playtype_name",
    "num",
    "val",
    "rank_count",
    "hit_count_map",
    "serial_hit_count_map",
    "series_not_hit_count_map",
    "max_serial_hit_count_map",
    "max_series_not_hit_count_map",
    "his_max_serial_hit_count_map",
    "his_max_series_not_hit_count_map",
]
detail_view = result_df[display_columns]
st.dataframe(detail_view, width="stretch")

rank_entries: list[tuple[str, list[str]]] = []
for _, row in result_df.iterrows():
    digits = [n.strip() for n in str(row["num"]).split(",") if n.strip()]
    if digits:
        rank_entries.append((row["playtype_name"], digits))

render_rank_position_calculator(rank_entries, key="red_val_v2_rank")
