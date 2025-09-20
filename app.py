from __future__ import annotations

import logging

import streamlit as st

from components import (
    render_connection_overview,
    render_data_board,
    render_error_log,
    render_operations_panel,
    render_table_overview,
)
from config.settings import configure_logging
from db.connection import query_db

configure_logging()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Lotto AI 4 诊断", layout="wide")


def _show_collection_feedback() -> None:
    feedback = st.session_state.pop("collection_feedback")
    if feedback.get("state") == "success":
        stats = feedback.get("stats", {})
        inserted = stats.get("inserted", 0)
        updated = stats.get("updated", 0)
        st.toast(f"开奖采集成功：新增 {inserted} 条，更新 {updated} 条。", icon="✅")
    elif feedback.get("state") == "error":
        st.toast(f"开奖采集失败：{feedback.get('error', '未知错误')}", icon="⚠️")


def create_safe_query(status_messages: list[tuple[str, str]]):
    def safe_query(sql: str, params: dict[str, object] | None = None):
        try:
            return query_db(sql, params or {})
        except Exception as exc:  # pragma: no cover - 依赖外部数据库
            logger.exception("数据库查询失败: %s", sql)
            status_messages.append((sql, str(exc)))
            return []

    return safe_query


def main() -> None:
    if "collection_feedback" in st.session_state:
        _show_collection_feedback()

    st.title("系统诊断 / 探活")
    st.caption("数据源：Docker MySQL 容器 `mysql:3306` (db: lotto_3d)")

    status_messages: list[tuple[str, str]] = []
    safe_query = create_safe_query(status_messages)

    connection_info = render_connection_overview(safe_query)
    render_data_board(safe_query)
    render_table_overview(safe_query, connection_info.get("db_name"))
    render_operations_panel(safe_query)
    render_error_log(status_messages)

    st.divider()
    st.caption("提示：侧边栏可进入其它分析页面。")


if __name__ == "__main__":  # pragma: no cover - Streamlit handles execution
    main()
