from __future__ import annotations

import platform
from typing import Dict, List

import pandas as pd
import streamlit as st
from streamlit import column_config

from collector.lottery_results import collect_lottery_results
from db.connection import query_db

st.set_page_config(page_title="Lotto AI 4 诊断", layout="wide")

if "collection_feedback" in st.session_state:
    feedback = st.session_state.pop("collection_feedback")
    if feedback.get("state") == "success":
        stats = feedback.get("stats", {})
        inserted = stats.get("inserted", 0)
        updated = stats.get("updated", 0)
        st.toast(f"开奖采集成功：新增 {inserted} 条，更新 {updated} 条。", icon="✅")
    elif feedback.get("state") == "error":
        st.toast(f"开奖采集失败：{feedback.get('error', '未知错误')}", icon="⚠️")

st.title("系统诊断 / 探活")
st.caption("数据源：Docker MySQL 容器 `mysql:3306` (db: lotto_3d)")


status_messages: List[tuple[str, str]] = []


def safe_query(sql: str, params: Dict[str, object] | None = None):
    try:
        return query_db(sql, params or {})
    except Exception as exc:  # pragma: no cover - 依赖外部数据库
        status_messages.append((sql, str(exc)))
        return []


def load_issue_summary():
    summary_row = safe_query(
        """
        SELECT MAX(issue_name) AS latest_issue,
               COUNT(DISTINCT issue_name) AS total_issues
        FROM lottery_results
        """
    )
    latest_issue = summary_row[0].get("latest_issue") if summary_row else None
    total_raw = summary_row[0].get("total_issues") if summary_row else 0
    total_issues = int(total_raw or 0)
    return {
        "latest_issue": latest_issue,
        "total_issues": total_issues,
    }


def load_user_summary() -> int:
    row = safe_query("SELECT COUNT(DISTINCT user_id) AS total_users FROM expert_info")
    if row:
        return int(row[0].get("total_users", 0) or 0)
    return 0


def load_top_hits() -> pd.DataFrame:
    rows = safe_query(
        """
        WITH aggregated AS (
            SELECT playtype_id, user_id, SUM(hit_count) AS total_hits
            FROM expert_hit_stat
            GROUP BY playtype_id, user_id
        ), ranked AS (
            SELECT a.playtype_id,
                   a.user_id,
                   a.total_hits,
                   ROW_NUMBER() OVER (PARTITION BY a.playtype_id ORDER BY a.total_hits DESC, a.user_id) AS rank_pos
            FROM aggregated a
        )
        SELECT r.playtype_id,
               IFNULL(d.playtype_name, CONCAT('玩法 ', r.playtype_id)) AS playtype_name,
               r.user_id,
               r.total_hits,
               r.rank_pos
        FROM ranked r
        LEFT JOIN playtype_dict d ON d.playtype_id = r.playtype_id
        WHERE r.rank_pos <= 10
        ORDER BY r.playtype_id, r.rank_pos
        """
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(
        columns={
            "playtype_name": "玩法",
            "user_id": "用户ID",
            "total_hits": "命中总数",
            "rank_pos": "排名",
        }
    )
    df["玩法"] = df["玩法"].fillna(df["playtype_id"].astype(str))
    df["命中总数"] = df["命中总数"].fillna(0).astype(int)
    df["排名"] = df["排名"].fillna(0).astype(int)
    return df


SPECIAL_PLAYTYPES = {
    1003: "三胆",
    3016: "百位定1",
}


def load_special_hits() -> pd.DataFrame:
    issue_row = safe_query(
        """
        SELECT MAX(issue_name) AS latest_issue
        FROM expert_hit_stat
        WHERE playtype_id IN (1003, 3016)
        """
    )
    issue = issue_row[0].get("latest_issue") if issue_row else None
    if not issue:
        data = [
            {"期号": "-", "玩法": name, "命中人数": 0, "命中 user_id": []}
            for name in SPECIAL_PLAYTYPES.values()
        ]
        return pd.DataFrame(data)

    rows = safe_query(
        """
        SELECT playtype_id, user_id
        FROM expert_hit_stat
        WHERE issue_name = :issue
          AND playtype_id IN (1003, 3016)
          AND hit_count > 0
        ORDER BY playtype_id, user_id
        """,
        {"issue": issue},
    )
    if not rows:
        fallback_issue_row = safe_query(
            """
            SELECT MAX(issue_name) AS latest_issue
            FROM expert_hit_stat
            WHERE playtype_id IN (1003, 3016)
              AND hit_count > 0
            """
        )
        fallback_issue = fallback_issue_row[0].get("latest_issue") if fallback_issue_row else None
        if fallback_issue and fallback_issue != issue:
            issue = fallback_issue
            rows = safe_query(
                """
                SELECT playtype_id, user_id
                FROM expert_hit_stat
                WHERE issue_name = :issue
                  AND playtype_id IN (1003, 3016)
                  AND hit_count > 0
                ORDER BY playtype_id, user_id
                """,
                {"issue": issue},
            )
    hits_map: Dict[int, List[str]] = {pid: [] for pid in SPECIAL_PLAYTYPES}
    for row in rows:
        pid = int(row.get("playtype_id"))
        hits_map.setdefault(pid, []).append(str(row.get("user_id")))
    data = []
    for pid, name in SPECIAL_PLAYTYPES.items():
        users = hits_map.get(pid, [])
        data.append(
            {
                "期号": issue,
                "玩法": name,
                "命中人数": len(users),
                "命中 user_id": users,
            }
        )
    return pd.DataFrame(data)


connect_rows = safe_query("SELECT 1 AS ok")
if connect_rows:
    st.success("数据库连接正常")
else:
    st.warning("数据库连接不可用或未启动")

version_rows = safe_query("SELECT VERSION() AS version")
database_rows = safe_query("SELECT DATABASE() AS db")

db_version = version_rows[0].get("version") if version_rows else None
db_name = database_rows[0].get("db") if database_rows else None

version_cols = st.columns(3)
version_cols[0].metric("Python 版本", platform.python_version())
version_cols[1].metric("Streamlit 版本", st.__version__)
version_cols[2].metric("数据库版本", db_version or "未知")

st.subheader("数据展板")
issue_summary = load_issue_summary()
user_total = load_user_summary()
top_hits_df = load_top_hits()
special_hits_df = load_special_hits()

overview_tab, hits_tab, special_tab = st.tabs(["开奖概览", "命中榜单", "上期开奖命中"])

with overview_tab:
    overview_cols = st.columns([1, 1, 1])
    latest_issue = issue_summary.get("latest_issue")
    overview_cols[0].metric("最新期号", latest_issue or "-")
    overview_cols[1].metric("累计期数", issue_summary.get("total_issues", 0))
    overview_cols[2].metric("专家总数", user_total)
    if not latest_issue:
        st.info("暂无开奖数据，请先采集。")

with hits_tab:
    if not top_hits_df.empty:
        playtype_options = top_hits_df["玩法"].unique().tolist()
        default_playtype = playtype_options[0] if playtype_options else None
        selected_playtype = st.selectbox(
            "选择玩法查看 TOP 10",
            options=playtype_options,
            index=0 if default_playtype else None,
        )
        if selected_playtype:
            filtered = top_hits_df[top_hits_df["玩法"] == selected_playtype][
                ["排名", "用户ID", "命中总数"]
            ]
            if filtered.empty:
                st.info("当前玩法暂无命中数据。")
            else:
                st.dataframe(
                    filtered,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "排名": column_config.NumberColumn("排名", width="small"),
                        "用户ID": column_config.TextColumn("用户ID", width="medium"),
                        "命中总数": column_config.ProgressColumn(
                            "命中总数",
                            min_value=0,
                            max_value=int(filtered["命中总数"].max() or 1),
                        ),
                    },
                )
        with st.expander("查看全部玩法榜单"):
            st.dataframe(
                top_hits_df[["玩法", "排名", "用户ID", "命中总数"]],
                hide_index=True,
                use_container_width=True,
                column_config={
                    "排名": column_config.NumberColumn("排名", width="small"),
                    "用户ID": column_config.TextColumn("用户ID", width="medium"),
                    "命中总数": column_config.NumberColumn("命中总数"),
                },
            )
    else:
        st.info("暂无命中统计数据。")

with special_tab:
    if not special_hits_df.empty:
        st.dataframe(
            special_hits_df,
            hide_index=True,
            use_container_width=True,
            column_config={
                "期号": column_config.TextColumn("期号", width="small"),
                "玩法": column_config.TextColumn("玩法", width="medium"),
                "命中人数": column_config.NumberColumn("命中人数", width="small"),
                "命中 user_id": column_config.ListColumn("命中 user_id"),
            },
        )
    else:
        st.info("暂无命中记录。")

st.subheader(f"当前数据库：{db_name or '未知'}，表清单")
tables = safe_query(
    """
    SELECT table_name AS 表名称,
           table_rows AS 行数量
    FROM information_schema.tables
    WHERE table_schema = DATABASE()
    ORDER BY table_name
    """
)
if tables:
    table_df = pd.DataFrame(tables)
    if "行数量" in table_df.columns:
        table_df["行数量"] = table_df["行数量"].fillna(0).astype(int)
    st.dataframe(table_df, use_container_width=True, hide_index=True)
else:
    st.info("无法获取表清单。")

st.subheader("运维工具")
if st.button("采集最近 5 期开奖信息", type="primary", icon="🎯", use_container_width=True):
    with st.status("正在采集最近开奖数据…", expanded=True) as status:
        try:
            stats = collect_lottery_results(max_pages=1, page_size=5)
        except Exception as exc:  # pragma: no cover - 外部依赖
            status.update(label="采集失败", state="error")
            st.session_state["collection_feedback"] = {
                "state": "error",
                "error": str(exc),
            }
        else:
            status.update(label="采集完成", state="complete")
            st.session_state["collection_feedback"] = {
                "state": "success",
                "stats": stats,
            }
    st.rerun()

if status_messages:
    with st.expander("错误日志", expanded=False):
        for sql, error in status_messages:
            st.write(f"SQL: {sql}")
            st.error(error)
else:
    st.success("诊断未记录错误。")

st.divider()
st.caption("提示：侧边栏可进入其它分析页面。")
