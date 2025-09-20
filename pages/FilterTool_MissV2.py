from __future__ import annotations

import collections

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.charts import render_digit_frequency_chart
from utils.data_access import (
    fetch_playtypes_for_issue,
)
from utils.numbers import match_prediction_hit, normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import issue_picker, playtype_picker, render_open_info

st.set_page_config(page_title="Lotto AI", layout="wide")

st.header("FilterTool_MissV2 - 组合缺失筛选")

selected_issue = issue_picker(
    "filter_miss_issue",
    mode="single",
    label="当前期号",
    max_issues=300,
)
if not selected_issue:
    st.stop()

render_open_info(selected_issue, key="filter_miss_open", show_metrics=False)

playtype_df = fetch_playtypes_for_issue(selected_issue)
if playtype_df.empty:
    st.info("当前期暂无专家推荐。")
    st.stop()

playtype_map: dict[int, str] = {
    int(row.playtype_id): row.playtype_name for row in playtype_df.itertuples()
}
playtype_ids = list(playtype_map.keys())

raw_playtypes = playtype_picker(
    "filter_miss_current_playtypes",
    mode="multi",
    label="🎮 当前期统计玩法（可多选）",
    include=[str(pid) for pid in playtype_ids],
    default=[str(playtype_ids[0])] if playtype_ids else [],
)
selected_playtypes = [int(pid) for pid in raw_playtypes]

issue_rows = cached_query(
    query_db,
    """
    SELECT DISTINCT issue_name
    FROM expert_predictions
    ORDER BY issue_name DESC
    LIMIT 500
    """,
    params=None,
    ttl=300,
)
issue_list_all = [row["issue_name"] for row in issue_rows]
if selected_issue not in issue_list_all:
    issue_list_all.insert(0, selected_issue)

if not issue_list_all:
    st.warning("暂无专家历史期号数据。")
    st.stop()

with st.expander("🔎 筛除连续未命中AI智体设置", expanded=True):
    try:
        current_index = issue_list_all.index(selected_issue)
    except ValueError:
        current_index = 0

    if current_index + 1 < len(issue_list_all):
        default_end_issue = issue_list_all[current_index + 1]
    else:
        default_end_issue = issue_list_all[current_index]

    ref_issue = st.selectbox(
        "🗕️ 回溯统计截至期号",
        options=issue_list_all,
        index=issue_list_all.index(default_end_issue) if default_end_issue in issue_list_all else 0,
    )

    ref_index = issue_list_all.index(ref_issue)
    max_lookback_n = len(issue_list_all) - ref_index
    max_lookback_n = max(max_lookback_n, 1)

    lookback_n = st.slider("📅 回溯期数（Lookback N期）", 1, max_lookback_n, 1)

    enable_miss_threshold_config = st.checkbox("✏️ 手动设置未命中次数筛选区间", value=False)

    if enable_miss_threshold_config:
        if "miss_threshold_low" not in st.session_state:
            st.session_state["miss_threshold_low"] = 0
        if "miss_threshold_high" not in st.session_state:
            st.session_state["miss_threshold_high"] = 0

        low_default = min(int(st.session_state["miss_threshold_low"]), lookback_n)
        high_default = min(int(st.session_state["miss_threshold_high"]), lookback_n)
        if high_default < low_default:
            high_default = low_default

        miss_threshold_low = st.slider(
            "📉 最少未命中次数（低区间）",
            min_value=0,
            max_value=lookback_n,
            value=low_default,
            key="miss_threshold_low",
        )
        miss_threshold_high = st.slider(
            "📈 最大未命中次数（高区间）",
            min_value=0,
            max_value=lookback_n,
            value=high_default,
            key="miss_threshold_high",
        )
    else:
        miss_threshold_low = 0
        miss_threshold_high = 0

    remove_duplicates = st.checkbox("🧹 是否去重同专家同玩法记录", value=True)

    raw_ref_playtypes = playtype_picker(
        "filter_miss_ref_playtypes",
        mode="multi",
        label="🎯 回溯玩法（可多选）",
        include=[str(pid) for pid in playtype_ids],
        default=(
            [str(pid) for pid in selected_playtypes]
            if selected_playtypes
            else [str(playtype_ids[0])] if playtype_ids else []
        ),
    )
    ref_playtypes = [int(pid) for pid in raw_ref_playtypes]

    filter_mode = st.selectbox(
        "🎯 筛选模式",
        options=[
            f"保留未命中次数 ≤ {miss_threshold_high} 的专家（高命中）",
            f"保留 {miss_threshold_low} ≤ 未命中次数 ≤ {miss_threshold_high} 的专家（中命中）",
            "保留连续必中专家（未命中=0）",
            f"保留连续未命中专家（未命中={lookback_n}）",
        ],
    )

    enable_filter = st.checkbox("🧊 启用筛选", value=True)


if st.button("🚀 查询推荐数字频次"):
    if not selected_playtypes:
        st.warning("⚠️ 请选择至少一个玩法。")
        st.stop()

    if enable_filter and not ref_playtypes:
        st.warning("⚠️ 请选择至少一个回溯玩法用于筛选。")
        st.stop()

    with st.spinner("查询中..."):
        try:
            current_clause, current_params = make_in_clause(
                "playtype_id", [int(pid) for pid in selected_playtypes], "cur"
            )
            current_params.update({"issue": selected_issue})
            sql_current = f"""
                SELECT user_id, playtype_id, numbers
                FROM expert_predictions
                WHERE issue_name = :issue
                  AND {current_clause}
            """
            current_rows = cached_query(query_db, sql_current, params=current_params, ttl=120)
        except Exception as exc:  # pragma: no cover - defensive UI guard
            st.error(f"加载当前期推荐失败：{exc}")
            st.stop()

        current_df = pd.DataFrame(current_rows)
        if current_df.empty:
            st.info("当前期暂无符合条件的专家推荐。")
            st.stop()

        current_df["playtype_id"] = current_df["playtype_id"].astype(int)

        if remove_duplicates:
            current_df.drop_duplicates(subset=["user_id", "playtype_id", "numbers"], inplace=True)

        try:
            issue_rows = cached_query(
                query_db,
                """
                SELECT DISTINCT issue_name
                FROM expert_predictions
                WHERE issue_name <= :ref_issue
                ORDER BY issue_name DESC
                LIMIT :limit
                """,
                params={"ref_issue": ref_issue, "limit": lookback_n},
                ttl=120,
            )
        except Exception as exc:  # pragma: no cover - defensive UI guard
            st.error(f"加载回溯期号失败：{exc}")
            st.stop()

        issue_list = sorted({row["issue_name"] for row in issue_rows})
        if not issue_list:
            st.info("所选回溯范围内无专家推荐记录。")
            st.stop()

        result_clause, result_params = make_in_clause("issue_name", issue_list, "res")
        sql_result = f"""
            SELECT issue_name, open_code
            FROM lottery_results
            WHERE {result_clause}
        """
        result_rows = cached_query(query_db, sql_result, params=result_params, ttl=120)
        result_map = {
            row["issue_name"]: normalize_code(row.get("open_code")) for row in result_rows
        }

        history_df = pd.DataFrame()
        if ref_playtypes:
            history_clause, history_params = make_in_clause("issue_name", issue_list, "hist")
            playtype_clause, playtype_params = make_in_clause(
                "playtype_id", [int(pid) for pid in ref_playtypes], "pt"
            )
            history_params.update(playtype_params)
            sql_history = f"""
                SELECT issue_name, playtype_id, user_id, numbers
                FROM expert_predictions
                WHERE {history_clause}
                  AND {playtype_clause}
            """
            try:
                history_rows = cached_query(query_db, sql_history, params=history_params, ttl=120)
            except Exception as exc:  # pragma: no cover - defensive UI guard
                st.error(f"加载回溯推荐失败：{exc}")
                st.stop()
            history_df = pd.DataFrame(history_rows)
            history_df["playtype_id"] = history_df["playtype_id"].astype(int)

        kept_users: set[str]
        if enable_filter and not history_df.empty:
            kept: list[str] = []
            issue_sequence = sorted(issue_list)
            result_lookup = result_map

            for user_id, group in history_df.groupby("user_id"):
                group = group.drop_duplicates(subset=["issue_name", "playtype_id", "numbers"])
                group = group[group["issue_name"].isin(issue_sequence)]
                if len(group) < lookback_n:
                    continue

                group = group.sort_values("issue_name")
                group_dict = group.set_index("issue_name")
                hits: list[bool] = []

                for issue in issue_sequence:
                    if issue not in group_dict.index:
                        continue
                    row = group_dict.loc[[issue]].iloc[0]
                    open_code = result_lookup.get(issue)
                    if not open_code:
                        continue
                    playtype_name = playtype_map.get(
                        int(row["playtype_id"]), str(row["playtype_id"])
                    )
                    hit = match_prediction_hit(playtype_name, row["numbers"], open_code)
                    hits.append(hit)

                miss_count = hits.count(False)
                if f"未命中次数 ≤ {miss_threshold_high}" in filter_mode:
                    if miss_count <= miss_threshold_high:
                        kept.append(user_id)
                elif f"{miss_threshold_low} ≤ 未命中次数 ≤ {miss_threshold_high}" in filter_mode:
                    if miss_threshold_low <= miss_count <= miss_threshold_high:
                        kept.append(user_id)
                elif "连续必中" in filter_mode:
                    if miss_count == 0:
                        kept.append(user_id)
                elif "连续未命中" in filter_mode:
                    if hits.count(True) == 0:
                        kept.append(user_id)

            kept_users = set(kept)
        elif enable_filter and history_df.empty:
            kept_users = set()
        else:
            kept_users = set(current_df["user_id"].unique())

        if enable_filter:
            current_df = current_df[current_df["user_id"].isin(kept_users)]

        if current_df.empty:
            st.info("无符合筛选条件的专家推荐。")
            st.stop()

        if remove_duplicates and not current_df.empty:
            current_df.drop_duplicates(subset=["user_id", "playtype_id", "numbers"], inplace=True)

        freq_counter = collections.Counter()
        for numbers in current_df["numbers"]:
            for token in parse_tokens(numbers):
                key = normalize_code(token) or token.strip()
                if key:
                    freq_counter[key] += 1

        if not freq_counter:
            st.warning("⚠️ 无推荐数据可用于统计。")
            st.stop()

        freq_df = (
            pd.DataFrame(
                {"数字": list(freq_counter.keys()), "推荐次数": list(freq_counter.values())}
            )
            .sort_values(by="推荐次数", ascending=False)
            .reset_index(drop=True)
        )

        st.subheader("推荐数字频次")
        st.dataframe(freq_df, use_container_width=True)

        chart = render_digit_frequency_chart(
            freq_df,
            digit_column="数字",
            count_column="推荐次数",
        )
        if chart is not None:
            st.altair_chart(chart, use_container_width=True)

        included_user_ids = current_df["user_id"].unique().tolist()
        st.markdown(f"### ✅ 当前期实际参与统计的AI智体（{len(included_user_ids)}个）")

        if included_user_ids:
            user_clause, user_params = make_in_clause("user_id", included_user_ids, "user")
            sql_users = f"""
                SELECT user_id, nick_name
                FROM expert_info
                WHERE {user_clause}
            """
            user_rows = cached_query(query_db, sql_users, params=user_params, ttl=300)
            user_info_df = pd.DataFrame(user_rows)

            current_df["playtype_name"] = current_df["playtype_id"].apply(
                lambda pid: playtype_map.get(pid, str(pid))
            )
            recommend_df = current_df.copy()
            recommend_df["推荐项"] = recommend_df.apply(
                lambda row: f"{row['playtype_name']}: {row['numbers']}", axis=1
            )
            recommend_summary = (
                recommend_df.groupby("user_id")["推荐项"]
                .apply(lambda values: " / ".join(sorted(set(values))))
                .reset_index()
            )

            display_df = user_info_df.merge(recommend_summary, on="user_id", how="left").rename(
                columns={
                    "user_id": "用户ID",
                    "nick_name": "专家昵称",
                    "推荐项": "推荐数字",
                }
            )
            display_df.sort_values("用户ID", inplace=True)

            st.subheader("参与统计的专家")
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("暂无AI智体参与当前统计。")
