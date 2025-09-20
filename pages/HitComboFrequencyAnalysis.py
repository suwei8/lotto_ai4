from __future__ import annotations

import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_playtypes
from utils.ui import issue_picker, playtype_picker
from utils.numbers import match_prediction_hit
from utils.sql import make_in_clause


st.header("HitComboFrequencyAnalysis - 命中组合统计")

selected_issues = issue_picker(
    "hit_combo_issues",
    mode="multi",
    label="选择期号",
    max_issues=120,
)
if not selected_issues:
    st.warning("请选择至少一个期号。")
    st.stop()

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtype_map = {
    str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()
}
selected_playtype = playtype_picker(
    "hit_combo_playtype",
    mode="single",
    label="选择玩法",
    include=list(playtype_map.keys()),
)
if not selected_playtype:
    st.stop()
playtype_name = playtype_map.get(selected_playtype, selected_playtype)

issue_clause, issue_params = make_in_clause("issue_name", selected_issues, "issue")
sql_predictions = f"""
    SELECT issue_name, user_id, numbers
    FROM expert_predictions
    WHERE {issue_clause}
      AND playtype_id = :playtype_id
"""
issue_params.update({"playtype_id": int(selected_playtype)})

try:
    prediction_rows = cached_query(
        query_db, sql_predictions, params=issue_params, ttl=300
    )
except Exception as exc:
    st.warning(f"查询预测数据失败：{exc}")
    prediction_rows = []

if not prediction_rows:
    st.info("未获取到预测数据。")
    st.stop()

prediction_df = pd.DataFrame(prediction_rows)
prediction_df.drop_duplicates(subset=["issue_name", "user_id", "numbers"], inplace=True)

triggered = st.button("查询命中组合出现次数")

if triggered:
    lottery_clause, lottery_params = make_in_clause(
        "issue_name", selected_issues, "lottery"
    )
    sql_lottery = f"""
        SELECT issue_name, open_code
        FROM lottery_results
        WHERE {lottery_clause}
    """
    lottery_rows = cached_query(
        query_db, sql_lottery, params=lottery_params, ttl=300
    )
    open_map = {row["issue_name"]: row.get("open_code") for row in lottery_rows}

    records = []
    for issue_name, group in prediction_df.groupby("issue_name"):
        open_code = open_map.get(issue_name)
        combo_counts = (
            group.groupby("numbers").agg(count=("user_id", "nunique")).reset_index()
        )
        for row in combo_counts.itertuples():
            hit = match_prediction_hit(playtype_name, row.numbers, open_code or "")
            if hit:
                records.append(
                    {
                        "issue_name": issue_name,
                        "numbers": row.numbers,
                        "occurrences": int(row.count),
                        "open_code": open_code or "",
                    }
                )

    if not records:
        st.info("未找到命中组合。")
    else:
        result_df = pd.DataFrame(records)
        result_df.sort_values(
            by=["issue_name", "occurrences"],
            ascending=[False, False],
            inplace=True,
        )
        result_df.rename(
            columns={
                "issue_name": "期号",
                "numbers": "命中组合",
                "occurrences": "出现次数",
                "open_code": "开奖号码",
            },
            inplace=True,
        )
        st.markdown(f"### 命中组合统计（共 {len(result_df)} 个）")
        st.dataframe(result_df, width="stretch")
else:
    st.info("点击上方按钮开始统计命中组合。")
