from __future__ import annotations

import pandas as pd
import streamlit as st

from db.connection import query_db

st.set_page_config(page_title="Lotto AI 4 诊断", layout="wide")

st.title("系统诊断 / 探活")
st.caption("数据源：Docker MySQL 容器 `mysql:3306` (db: lotto_3d)")

status_messages: list[tuple[str, str]] = []


def safe_query(sql: str, params: dict | None = None):
    try:
        return query_db(sql, params or {})
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        status_messages.append((sql, str(exc)))
        return []


connect_rows = safe_query("SELECT 1 AS ok")
if connect_rows:
    st.success("数据库连接正常")
else:
    st.warning("数据库连接不可用或未启动")

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
    st.dataframe(pd.DataFrame(tables), use_container_width=True)
else:
    st.info("无法获取表清单。")

st.subheader("探活检查")
if st.button("执行探活", use_container_width=True):
    checks = {
        "命中统计示例": "SELECT COUNT(*) AS cnt FROM expert_hit_stat LIMIT 1",
        "专家信息": "SELECT COUNT(*) AS cnt FROM expert_info LIMIT 1",
        "开奖数据": "SELECT COUNT(*) AS cnt FROM lottery_results LIMIT 1",
    }
    results: list[dict[str, object]] = []
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

st.divider()
st.caption("提示：侧边栏可进入其它分析页面。")
