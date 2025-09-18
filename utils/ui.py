from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd
import streamlit as st

from utils.data_access import (
    default_issue_window,
    fetch_issue_dataframe,
    fetch_playtypes,
    fetch_predicted_issues,
    fetch_recent_issues,
)


def issue_range_selector(
    key_prefix: str,
    default_window: int = 30,
    recent_limits: Sequence[int] = (10, 30, 50, 100),
) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Render a configurable issue range selector.

    Returns the start issue, end issue, and the list of known issues (newest first).
    When the issue list cannot be obtained, all values are returned as ``None``.
    """

    limits = list(recent_limits)
    if not limits:
        limits = [default_window]
    limits = sorted(limits)

    issues = fetch_recent_issues(limit=max(limits[-1], default_window))
    if not issues:
        st.warning("无法获取期号列表，请检查数据库连接。")
        return None, None, []

    latest_start, latest_end = default_issue_window(issues, window=default_window)

    mode = st.radio(
        "期号范围选择",
        options=("近N期", "自定义区间"),
        horizontal=True,
        key=f"{key_prefix}_issue_mode",
    )

    start_issue: Optional[str]
    end_issue: Optional[str]

    if mode == "近N期":
        default_value = default_window if default_window in limits else limits[-1]
        n = st.select_slider(
            "选择最近多少期",
            options=limits,
            value=default_value,
            key=f"{key_prefix}_issue_recent",
        )
        start_issue, end_issue = default_issue_window(issues, window=int(n))
    else:
        all_options = [""] + issues
        try:
            end_index = (
                all_options.index(latest_end) if latest_end in all_options else 0
            )
        except ValueError:
            end_index = 0
        try:
            start_index = (
                all_options.index(latest_start) if latest_start in all_options else 0
            )
        except ValueError:
            start_index = 0
        end_issue = (
            st.selectbox(
                "结束期号（最新在上）",
                options=all_options,
                index=end_index,
                key=f"{key_prefix}_issue_end",
            )
            or None
        )
        start_issue = (
            st.selectbox(
                "起始期号（最新在上）",
                options=all_options,
                index=start_index,
                key=f"{key_prefix}_issue_start",
            )
            or None
        )
    return start_issue, end_issue, issues


def playtype_multiselect(key_prefix: str, label: str = "玩法选择") -> List[str]:
    playtypes = fetch_playtypes()
    if playtypes.empty:
        st.warning("玩法列表为空，无法筛选玩法。")
        return []

    options = [str(row.playtype_id) for row in playtypes.itertuples()]
    labels = {str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()}
    selection = st.multiselect(
        label,
        options=options,
        default=options,
        format_func=lambda value: labels.get(value, value),
        key=f"{key_prefix}_playtypes",
    )
    return list(selection)


def playtype_select(key_prefix: str, label: str = "玩法") -> Optional[str]:
    playtypes = fetch_playtypes()
    if playtypes.empty:
        st.warning("玩法列表为空，无法筛选玩法。")
        return None
    options = [str(row.playtype_id) for row in playtypes.itertuples()]
    labels = {str(row.playtype_id): row.playtype_name for row in playtypes.itertuples()}
    return st.selectbox(
        label,
        options=options,
        format_func=lambda value: labels.get(value, value),
        key=f"{key_prefix}_playtype_select",
    )


def dataframe_with_pagination(
    df: pd.DataFrame, page_size: int, key_prefix: str
) -> Tuple[pd.DataFrame, int, int]:
    from utils.pagination import paginate

    subset, page, pages = paginate(df, page_size=page_size, key=f"{key_prefix}_pager")
    st.caption(f"第 {page}/{pages} 页 | 共 {len(df)} 行")
    return subset, page, pages


def download_csv_button(df: pd.DataFrame, label: str, key: str) -> None:
    if df.empty:
        return
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=label, data=csv_data, file_name=f"{key}.csv", mime="text/csv"
    )


def display_issue_summary(start_issue: Optional[str], end_issue: Optional[str]) -> None:
    if start_issue and end_issue:
        st.info(f"当前统计范围：{start_issue} 至 {end_issue}")
    elif end_issue:
        st.info(f"当前统计范围：截至 {end_issue}")
    else:
        st.info("未选择期号范围，默认显示最新数据。")


def render_issue_table(limit: int = 50) -> None:
    issue_df = fetch_issue_dataframe(limit=limit)
    if issue_df.empty:
        st.warning("无法获取开奖信息。")
    else:
        st.dataframe(issue_df, use_container_width=True)


def multi_select_from_dataframe(
    df: pd.DataFrame,
    value_column: str,
    label_column: Optional[str] = None,
    default: Optional[Iterable[str]] = None,
    key: str = "multi_select",
) -> List[str]:
    if df.empty or value_column not in df:
        return []
    options = df[value_column].astype(str).tolist()
    labels = (
        df.set_index(value_column)[label_column].astype(str).to_dict()
        if label_column and label_column in df
        else {}
    )
    default_values = list(default) if default is not None else options
    return st.multiselect(
        "选择专家",
        options,
        default=default_values,
        format_func=lambda value: labels.get(value, value),
        key=key,
    )


def issue_multiselect(
    key_prefix: str,
    label: str = "选择期号",
    max_default: int = 10,
    source: str = "lottery",
) -> List[str]:
    if source == "predictions":
        issues = fetch_predicted_issues(limit=200)
    else:
        issues = fetch_recent_issues(limit=200)
    if not issues:
        st.warning("无法获取期号列表。")
        return []
    default_values = issues[:max_default]
    return st.multiselect(
        label,
        options=issues,
        default=default_values,
        key=f"{key_prefix}_issues",
    )
