from __future__ import annotations

import pandas as pd
import streamlit as st

from db.connection import query_db

st.header("系统诊断 / 探活")

status_messages = []


def safe_query(sql: str, params: dict | None = None):
    try:
        return query_db(sql, params or {})
    except Exception as exc:
        status_messages.append((sql, str(exc)))
        return []


version_rows = safe_query("SELECT VERSION() AS version")
database_rows = safe_query("SELECT DATABASE() AS db")

col_version, col_db = st.columns(2)
if version_rows:
    col_version.metric("数据库版本", version_rows[0]["version"])
else:
    col_version.warning("无法获取数据库版本")

if database_rows:
    col_db.metric("当前数据库", database_rows[0]["db"] or "未知")
else:
    col_db.warning("无法获取当前数据库")

st.subheader("表清单")
tables = safe_query("SHOW TABLES")
if tables:
    table_view = pd.DataFrame(tables)
    st.dataframe(table_view, use_container_width=True)
else:
    st.info("无法获取表清单。")

st.subheader("探活检查")
if st.button("执行探活", use_container_width=True):
    checks = {
        "命中统计示例": "SELECT COUNT(*) AS cnt FROM expert_hit_stat LIMIT 1",
        "专家信息": "SELECT COUNT(*) AS cnt FROM expert_info LIMIT 1",
        "开奖数据": "SELECT COUNT(*) AS cnt FROM lottery_results LIMIT 1",
    }
    results = []
    for title, sql in checks.items():
        rows = safe_query(sql)
        if rows:
            results.append({"检查项": title, "返回值": rows[0].get("cnt", rows[0])})
        else:
            results.append({"检查项": title, "返回值": "失败"})
    if results:
        st.table(pd.DataFrame(results))

if status_messages:
    with st.expander("错误日志", expanded=False):
        for sql, error in status_messages:
            st.write(f"SQL: {sql}")
            st.error(error)
else:
    st.success("诊断未记录错误。")
