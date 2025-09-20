from __future__ import annotations

import logging
from collections import Counter
from typing import Iterable, Mapping, Sequence

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    default_issue_window,
    fetch_experts,
    fetch_issue_dataframe,
    fetch_lottery_info,
    fetch_playtypes,
    fetch_predicted_issues,
    fetch_recent_issues,
)

logger = logging.getLogger(__name__)


def issue_picker(
    key: str,
    *,
    mode: str = "single",
    source: str = "lottery",
    default: str | Sequence[str] | None = None,
    label: str | None = None,
    max_issues: int = 200,
    options: Sequence[str] | None = None,
) -> str | None | list[str]:
    """Unified issue selector supporting single or multi-select modes.

    Args:
        key: Streamlit widget key.
        mode: "single" | "multi" | "range". Range delegates to issue_range_selector.
        source: "lottery" uses lottery_results, "predictions" uses expert_predictions.
        default: default selection(s). For multi-mode, accepts iterable or "all".
        label: optional label override.
        max_issues: number of issues to load.

    Returns:
        Selected issue(s) according to the mode.
    """

    if mode == "range":
        start_issue, end_issue, _ = issue_range_selector(
            key_prefix=key,
            default_window=30,
            recent_limits=(10, 30, 50, 100),
            source=source,
            max_issues=max_issues,
        )
        return [issue for issue in (start_issue, end_issue) if issue]

    if options is not None:
        issues = list(options)
    else:
        if source == "predictions":
            issues = fetch_predicted_issues(limit=max_issues)
        else:
            issues = fetch_recent_issues(limit=max_issues)
    if not issues:
        st.warning("无法获取期号列表。")
        return [] if mode == "multi" else None

    if label is None:
        label = "选择期号" if mode != "multi" else "选择期号（可多选）"

    if mode == "multi":
        if default is None or default == "all":
            default_values = issues
        else:
            default_values = (
                [val for val in default if val in issues]
                if isinstance(default, (list, tuple, set))
                else [default]
            )
        return st.multiselect(
            label,
            options=issues,
            default=default_values,
            key=f"{key}_issues",
        )

    default_value: str | None
    if isinstance(default, str) and default in issues:
        default_value = default
    elif default and isinstance(default, (list, tuple)):
        default_value = next((item for item in default if item in issues), issues[0])
    else:
        default_value = issues[0]
    return st.selectbox(
        label,
        options=issues,
        index=issues.index(default_value) if default_value in issues else 0,
        key=f"{key}_issue",
    )


def issue_range_selector(
    key_prefix: str,
    default_window: int = 30,
    recent_limits: Sequence[int] = (10, 30, 50, 100),
    *,
    source: str = "lottery",
    max_issues: int = 200,
) -> tuple[str | None, str | None, list[str]]:
    """Render a configurable issue range selector.

    Returns the start issue, end issue, and the list of known issues (newest first).
    When the issue list cannot be obtained, all values are returned as ``None``.
    """

    limits = list(recent_limits)
    if not limits:
        limits = [default_window]
    limits = sorted(limits)

    if source == "predictions":
        issues = fetch_predicted_issues(limit=max(max_issues, limits[-1]))
    else:
        issues = fetch_recent_issues(limit=max(max_issues, limits[-1], default_window))
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

    start_issue: str | None
    end_issue: str | None

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
            end_index = all_options.index(latest_end) if latest_end in all_options else 0
        except ValueError:
            end_index = 0
        try:
            start_index = all_options.index(latest_start) if latest_start in all_options else 0
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


def playtype_picker(
    key: str,
    *,
    mode: str = "multi",
    label: str | None = None,
    default: str | Sequence[str] | None = None,
    include: Sequence[str | int] | None = None,
    exclude: Sequence[str | int] | None = None,
    group_labels: Mapping[str, str] | None = None,
) -> list[str] | str | None:
    playtypes = fetch_playtypes()
    if playtypes.empty:
        st.warning("玩法列表为空，无法筛选玩法。")
        return [] if mode == "multi" else None

    playtypes["id"] = playtypes["playtype_id"].astype(str)
    if include:
        include_set = {str(item) for item in include}
        playtypes = playtypes[playtypes["id"].isin(include_set)]
    if exclude:
        exclude_set = {str(item) for item in exclude}
        playtypes = playtypes[~playtypes["id"].isin(exclude_set)]

    if playtypes.empty:
        st.warning("筛选条件下玩法列表为空。")
        return [] if mode == "multi" else None

    group_text_map = {str(k): v for k, v in (group_labels or {}).items()}

    options = playtypes["id"].tolist()
    labels = dict(zip(playtypes["id"], playtypes["playtype_name"].astype(str)))

    def display_label(value: str) -> str:
        group = group_text_map.get(value)
        base = labels.get(value, value)
        return f"[{group}] {base}" if group else base

    options.sort(key=lambda value: (group_text_map.get(value, ""), labels.get(value, value)))

    if label is None:
        label = "玩法选择" if mode == "multi" else "玩法"

    if mode == "multi":
        if default is None or default == "all":
            default_values = options
        else:
            default_values = (
                [val for val in default if str(val) in options]
                if isinstance(default, (list, tuple, set))
                else [str(default)]
            )
        return st.multiselect(
            label,
            options=options,
            default=default_values,
            format_func=display_label,
            key=f"{key}_playtypes",
        )

    default_value: str | None
    if isinstance(default, str) and default in options:
        default_value = default
    elif default and isinstance(default, (list, tuple)):
        default_value = next((str(item) for item in default if str(item) in options), options[0])
    else:
        default_value = options[0]
    return st.selectbox(
        label,
        options=options,
        index=options.index(default_value) if default_value in options else 0,
        format_func=display_label,
        key=f"{key}_playtype",
    )


def playtype_multiselect(key_prefix: str, label: str = "玩法选择") -> list[str]:
    selection = playtype_picker(
        key=key_prefix,
        mode="multi",
        label=label,
        default="all",
    )
    return list(selection)


def playtype_select(key_prefix: str, label: str = "玩法") -> str | None:
    return playtype_picker(
        key=key_prefix,
        mode="single",
        label=label,
    )


def render_open_info(
    issue: str | None,
    *,
    key: str,
    show_metrics: bool = True,
    caption: bool = True,
) -> dict | None:
    if not issue:
        st.info("未选择期号，无法展示开奖信息。")
        return None
    info = fetch_lottery_info(issue)
    if not info:
        st.warning("未能获取该期的开奖信息。")
        return None

    open_code = info.get("open_code") or "未开奖"
    sum_value = info.get("sum", "-")
    span_value = info.get("span", "-")

    if show_metrics:
        cols = st.columns(3)
        cols[0].metric("开奖号码", open_code)
        cols[1].metric("和值", sum_value)
        cols[2].metric("跨度", span_value)
    if caption:
        st.caption(f"开奖号码：{open_code}丨和值：{sum_value}丨跨度：{span_value}")
    return info


def expert_picker(
    key: str,
    *,
    issue: str | None = None,
    allow_manual: bool = True,
    label: str = "选择专家 user_id",
    manual_label: str | None = None,
    limit: int = 500,
) -> tuple[str | None, dict[str, str]]:
    experts = fetch_experts(limit=limit)
    expert_map = (
        {str(row.user_id): row.nick_name or "" for row in experts.itertuples()}
        if not experts.empty
        else {}
    )

    issue_user_ids: list[str] = []
    if issue:
        try:
            result = cached_query(
                query_db,
                """
                SELECT DISTINCT user_id
                FROM expert_predictions
                WHERE issue_name = :issue
                ORDER BY user_id
                """,
                params={"issue": issue},
                ttl=120,
            )
        except Exception:
            logger.exception("获取期号 %s 的专家列表失败", issue)
            result = []
        issue_user_ids = [
            str(row.get("user_id")) for row in result if row.get("user_id") is not None
        ]

    options = issue_user_ids or sorted(expert_map.keys())
    selection: str | None = None
    if options:
        selection = st.selectbox(
            label,
            options=options,
            key=f"{key}_select",
            format_func=lambda uid: f"{uid} ({expert_map.get(uid, '未知')})" if uid else uid,
        )
    elif not allow_manual:
        st.warning("未找到可选专家。")
        return None, expert_map

    user_id = selection
    if allow_manual:
        manual_label = manual_label or "或手动输入专家 user_id"
        manual_value = st.text_input(
            manual_label,
            value=selection or "",
            key=f"{key}_manual",
        )
        user_id = manual_value.strip() or selection

    return user_id if user_id else None, expert_map


def render_rank_position_calculator(
    entries: list[tuple[str, list[str]]],
    *,
    key: str,
    max_position: int = 10,
    title: str = "🧮 排行榜位置数字计算器",
    default_positions: Sequence[int] = (1, 2),
) -> None:
    with st.expander(title, expanded=False):
        if not entries:
            st.info("暂无数据可供计算。")
            return
        available_playtypes = sorted({name for name, _ in entries})
        default_playtypes = [name for name in available_playtypes if not name.startswith("杀")]
        selected_playtypes = st.multiselect(
            "选择玩法",
            options=available_playtypes,
            default=default_playtypes or available_playtypes,
            key=f"{key}_playtypes",
        )
        selected_positions = st.multiselect(
            "选择排行榜位置",
            options=list(range(1, max_position + 1)),
            default=list(default_positions),
            format_func=lambda pos: f"第 {pos} 位",
            key=f"{key}_positions",
        )
        if st.button("计算出现次数", key=f"{key}_calc"):
            counter = Counter()
            for playtype_name, digits in entries:
                if selected_playtypes and playtype_name not in selected_playtypes:
                    continue
                for pos in selected_positions:
                    if 1 <= pos <= len(digits):
                        counter[digits[pos - 1]] += 1
            if counter:
                result_df = (
                    pd.DataFrame(counter.items(), columns=["数字", "出现次数"])
                    .sort_values("出现次数", ascending=False)
                    .reset_index(drop=True)
                )
                st.dataframe(result_df, hide_index=True, use_container_width=True)
            else:
                st.warning("未得到统计结果，请检查玩法或位置选择。")


def dataframe_with_pagination(
    df: pd.DataFrame, page_size: int, key_prefix: str
) -> tuple[pd.DataFrame, int, int]:
    from utils.pagination import paginate

    subset, page, pages = paginate(df, page_size=page_size, key=f"{key_prefix}_pager")
    st.caption(f"第 {page}/{pages} 页 | 共 {len(df)} 行")
    return subset, page, pages


def download_csv_button(df: pd.DataFrame, label: str, key: str) -> None:
    if df.empty:
        return
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(label=label, data=csv_data, file_name=f"{key}.csv", mime="text/csv")


def display_issue_summary(start_issue: str | None, end_issue: str | None) -> None:
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
        st.dataframe(issue_df, width="stretch")


def multi_select_from_dataframe(
    df: pd.DataFrame,
    value_column: str,
    label_column: str | None = None,
    default: Iterable[str] | None = None,
    key: str = "multi_select",
) -> list[str]:
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
) -> list[str]:
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
