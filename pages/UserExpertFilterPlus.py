from __future__ import annotations

from collections import Counter
from typing import Sequence

import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.charts import render_digit_frequency_chart
from utils.data_access import (
    fetch_lottery_info,
    fetch_lottery_infos,
    fetch_playtypes_for_issue,
    fetch_predicted_issues,
    fetch_predictions,
)
from utils.numbers import match_prediction_hit, normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.ui import issue_picker, playtype_picker, render_open_info

st.set_page_config(page_title="🎯 专家推荐筛选器 Pro", layout="wide")
st.title("🎯 专家推荐筛选器 Pro")


def clear_cached_result():
    st.session_state.pop("uefp_result", None)


def fetch_expert_names(user_ids: Sequence[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    clause, params = make_in_clause("user_id", user_ids, "uid")
    if clause == "1=1":
        return {}
    sql = f"SELECT user_id, nick_name FROM expert_info WHERE {clause}"
    rows = cached_query(query_db, sql, params=params, ttl=300)
    return {int(row["user_id"]): row.get("nick_name") or "未知" for row in rows}


def extract_digit_set(numbers: str) -> set[str]:
    tokens = parse_tokens(numbers)
    digits: list[str] = []
    for token in tokens:
        digits.extend(list(token))
    return set(digits)


def render_horizontal_chart(freq_df: pd.DataFrame, open_digits: Sequence[str]):
    return render_digit_frequency_chart(
        freq_df,
        digit_column="数字",
        count_column="被推荐次数",
        hit_digits=open_digits,
        width=320,
    )


def users_matching_number_conditions(
    df: pd.DataFrame,
    conditions: list[dict[str, object]],
) -> set[int]:
    all_users = set(df["user_id"].unique())
    if not conditions:
        return all_users

    candidate = all_users.copy()
    for cond in conditions:
        digits: list[str] = cond.get("digits", [])  # type: ignore[assignment]
        playtypes: list[int] = cond.get("playtypes", [])  # type: ignore[assignment]
        mode: str = cond.get("mode", "包含")  # type: ignore[assignment]
        match_mode: str = cond.get("match", "任意匹配")  # type: ignore[assignment]

        if not digits or not playtypes:
            continue

        relevant = df[df["playtype_id"].isin(playtypes)]
        if relevant.empty:
            candidate.clear()
            break

        cond_users: set[int] = set()
        for user_id, group in relevant.groupby("user_id"):
            if mode == "包含":
                for digit_set in group["digit_set"]:
                    if match_mode == "任意匹配":
                        if any(d in digit_set for d in digits):
                            cond_users.add(user_id)
                            break
                    else:  # 全部匹配
                        if all(d in digit_set for d in digits):
                            cond_users.add(user_id)
                            break
            else:  # 不包含
                for digit_set in group["digit_set"]:
                    if not any(d in digit_set for d in digits):
                        cond_users.add(user_id)
                        break

        candidate &= cond_users
        if not candidate:
            break

    return candidate


def gather_hit_records(
    issue_sequence: Sequence[str], playtype_id: int, playtype_name: str
) -> dict[int, dict[str, bool]]:
    if not issue_sequence:
        return {}

    predictions_df = fetch_predictions(
        issue_sequence,
        playtype_ids=[playtype_id],
        columns=["issue_name", "user_id", "numbers"],
        ttl=None,
    )
    if predictions_df.empty:
        return {}

    info_map = fetch_lottery_infos(issue_sequence, ttl=None)
    records: dict[int, dict[str, bool]] = {}

    for (user_id, issue_name), group in predictions_df.groupby(["user_id", "issue_name"]):
        open_info = info_map.get(issue_name)
        open_code = open_info.get("open_code") if open_info else None
        hit = False
        if open_code:
            for numbers in group["numbers"]:
                if match_prediction_hit(playtype_name, numbers, open_code):
                    hit = True
                    break
        records.setdefault(int(user_id), {})[issue_name] = hit

    return records


def users_matching_hit_conditions(
    conditions: list[dict[str, object]],
    issues: list[str],
    selected_issue: str,
    playtype_map: dict[int, str],
) -> set[int]:
    if not conditions:
        return set()

    try:
        current_index = issues.index(selected_issue)
    except ValueError:
        return set()

    available_history = issues[current_index + 1 :]
    if not available_history:
        return set()

    candidate: set[int] | None = None

    for cond in conditions:
        playtype_id = int(cond.get("playtype", available_history and 0))
        playtype_name = playtype_map.get(playtype_id, str(playtype_id))
        mode: str = cond.get("mode", "上期命中")  # type: ignore[assignment]

        if mode in {"上期命中", "上期未命中"}:
            sequence = available_history[:1]
        else:  # 近N期命中M次
            recent_n = int(cond.get("recent_n", 5))
            sequence = available_history[:recent_n]

        if not sequence:
            cond_users: set[int] = set()
        else:
            records = gather_hit_records(sequence, playtype_id, playtype_name)
            if not records:
                cond_users = set()
            else:
                if mode == "上期命中":
                    issue = sequence[0]
                    cond_users = {
                        user_id
                        for user_id, issues_hits in records.items()
                        if issues_hits.get(issue, False)
                    }
                elif mode == "上期未命中":
                    issue = sequence[0]
                    cond_users = {
                        user_id
                        for user_id, issues_hits in records.items()
                        if issue in issues_hits and not issues_hits.get(issue, False)
                    }
                else:  # 近N期命中M次
                    issue_order = sequence
                    operator = cond.get("operator", ">=")
                    expected = int(cond.get("expected", 1))
                    op_map = {
                        ">": lambda a, b: a > b,
                        ">=": lambda a, b: a >= b,
                        "=": lambda a, b: a == b,
                        "<": lambda a, b: a < b,
                        "<=": lambda a, b: a <= b,
                    }
                    compare = op_map.get(operator, op_map[">="])
                    cond_users = set()
                    for user_id, issues_hits in records.items():
                        hit_count = sum(1 for issue in issue_order if issues_hits.get(issue, False))
                        if compare(hit_count, expected):
                            cond_users.add(user_id)

        if candidate is None:
            candidate = cond_users
        else:
            candidate &= cond_users

        if candidate is not None and not candidate:
            break

    return candidate or set()


issues = fetch_predicted_issues(limit=200)
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

st.markdown("## 📌 基础筛选条件")
previous_issue = st.session_state.get("uefp_issue_last")
issue_name = issue_picker(
    "uefp_issue",
    mode="single",
    source="predictions",
    options=issues,
    default=previous_issue or issues[0],
)
if not issue_name:
    st.stop()
if issue_name != previous_issue:
    st.session_state["uefp_issue_last"] = issue_name
    clear_cached_result()

render_open_info(issue_name, key="uefp_open", show_metrics=False)

playtypes_df = fetch_playtypes_for_issue(issue_name)
if playtypes_df.empty:
    clear_cached_result()
    st.info("当前期号下无推荐数据。")
    st.stop()

playtype_map = {int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()}
playtype_ids = list(playtype_map.keys())

previous_playtype = st.session_state.get("uefp_playtype_last")
target_playtype_id_str = playtype_picker(
    "uefp_target_playtype",
    mode="single",
    label="🎮 本期查询玩法（用于热力图与详情）",
    include=[str(pid) for pid in playtype_ids],
    default=str(previous_playtype) if previous_playtype else str(playtype_ids[0]),
)
if not target_playtype_id_str:
    st.stop()
target_playtype_id = int(target_playtype_id_str)
if target_playtype_id != previous_playtype:
    st.session_state["uefp_playtype_last"] = target_playtype_id
    clear_cached_result()
target_playtype_name = playtype_map.get(int(target_playtype_id), str(target_playtype_id))

st.markdown("## 🧠 推荐数字条件过滤器")

if "filter_conditions" not in st.session_state:
    st.session_state["filter_conditions"] = []
if "hit_conditions" not in st.session_state:
    st.session_state["hit_conditions"] = []

if st.button("➕ 添加筛选条件"):
    st.session_state["filter_conditions"].append(
        {
            "playtypes": list(playtype_ids),
            "mode": "包含",
            "match_mode": "全部匹配",
            "numbers": [],
        }
    )
    clear_cached_result()

for idx, cond in enumerate(st.session_state["filter_conditions"]):
    cols = st.columns([4, 3, 2, 1])

    key_playtypes = f"uefp_filter_playtypes_{idx}"
    if key_playtypes not in st.session_state:
        st.session_state[key_playtypes] = list(cond.get("playtypes", playtype_ids))
    selected_playtypes = cols[0].multiselect(
        f"玩法 {idx + 1}",
        options=playtype_ids,
        format_func=lambda pid: playtype_map.get(pid, str(pid)),
        key=key_playtypes,
        on_change=clear_cached_result,
    )
    cond["playtypes"] = [int(pid) for pid in selected_playtypes]

    key_mode = f"uefp_filter_mode_{idx}"
    if key_mode not in st.session_state:
        st.session_state[key_mode] = cond.get("mode", "包含")
    mode_value = cols[1].selectbox(
        "条件",
        ["包含", "不包含"],
        key=key_mode,
        on_change=clear_cached_result,
    )
    cond["mode"] = mode_value

    key_match = f"uefp_filter_match_{idx}"
    if mode_value == "包含":
        if key_match not in st.session_state:
            st.session_state[key_match] = cond.get("match_mode", "全部匹配")
        match_value = cols[1].selectbox(
            "匹配方式",
            ["全部匹配", "任意匹配"],
            key=key_match,
            on_change=clear_cached_result,
        )
        cond["match_mode"] = match_value
    else:
        cond["match_mode"] = "全部匹配"
        st.session_state.pop(key_match, None)
        cols[1].markdown("匹配方式：`全部匹配`")

    key_numbers = f"uefp_filter_numbers_{idx}"
    if key_numbers not in st.session_state:
        st.session_state[key_numbers] = cond.get("numbers", [])
    selected_numbers = cols[2].multiselect(
        "推荐数字",
        options=[str(n) for n in range(10)],
        key=key_numbers,
        on_change=clear_cached_result,
    )
    cond["numbers"] = [str(num) for num in selected_numbers]

    cols[2].caption("ℹ️ 多选多个推荐数字时，'包含'表示任意包含其一；'不包含'表示全部不包含这些数字")

    if cols[3].button("❌ 删除", key=f"uefp_filter_delete_{idx}"):
        st.session_state["filter_conditions"].pop(idx)
        st.session_state.pop(key_playtypes, None)
        st.session_state.pop(key_mode, None)
        st.session_state.pop(key_match, None)
        st.session_state.pop(key_numbers, None)
        clear_cached_result()
        st.rerun()

if st.session_state["filter_conditions"]:
    st.info(f"🎯 当前已添加 {len(st.session_state['filter_conditions'])} 个筛选条件")

st.markdown("## 🔎 往期命中特征过滤器")

if st.button("➕ 添加命中特征条件"):
    default_playtype = playtype_ids[0] if playtype_ids else None
    st.session_state["hit_conditions"].append(
        {
            "playtype": default_playtype,
            "mode": "上期命中",
            "recent_n": 5,
            "hit_n": 3,
            "op": "≥",
        }
    )
    clear_cached_result()

for idx, cond in enumerate(st.session_state["hit_conditions"]):
    cols = st.columns([3, 3, 2, 2, 1])

    key_playtype = f"uefp_hit_playtype_{idx}"
    if key_playtype not in st.session_state:
        st.session_state[key_playtype] = cond.get("playtype", playtype_ids[0])
    playtype_value = cols[0].selectbox(
        f"玩法 {idx + 1}",
        options=playtype_ids,
        format_func=lambda pid: playtype_map.get(pid, str(pid)),
        key=key_playtype,
        on_change=clear_cached_result,
    )
    cond["playtype"] = int(playtype_value)

    key_mode = f"uefp_hit_mode_{idx}"
    if key_mode not in st.session_state:
        st.session_state[key_mode] = cond.get("mode", "上期命中")
    mode_value = cols[1].selectbox(
        "命中特征",
        ["上期命中", "上期未命中", "近N期命中M次"],
        key=key_mode,
        on_change=clear_cached_result,
    )
    cond["mode"] = mode_value

    if mode_value == "近N期命中M次":
        key_op = f"uefp_hit_op_{idx}"
        key_recent = f"uefp_hit_recent_{idx}"
        key_hit_n = f"uefp_hit_count_{idx}"

        if key_op not in st.session_state:
            st.session_state[key_op] = cond.get("op", "≥")
        cond["op"] = cols[2].selectbox(
            "运算符",
            ["≥", "=", ">", "<", "<="],
            key=key_op,
            on_change=clear_cached_result,
        )

        if key_recent not in st.session_state:
            st.session_state[key_recent] = int(cond.get("recent_n", 5))
        cond["recent_n"] = int(
            cols[3].number_input(
                "近 N 期",
                min_value=1,
                max_value=30,
                step=1,
                key=key_recent,
                on_change=clear_cached_result,
            )
        )

        if key_hit_n not in st.session_state:
            st.session_state[key_hit_n] = int(cond.get("hit_n", 3))
        cond["hit_n"] = int(
            cols[4].number_input(
                "命中次数",
                min_value=1,
                max_value=30,
                step=1,
                key=key_hit_n,
                on_change=clear_cached_result,
            )
        )
    else:
        cond["op"] = cond.get("op", "≥")

    if cols[4].button("❌ 删除", key=f"uefp_hit_delete_{idx}"):
        st.session_state["hit_conditions"].pop(idx)
        st.session_state.pop(f"uefp_hit_op_{idx}", None)
        st.session_state.pop(f"uefp_hit_recent_{idx}", None)
        st.session_state.pop(f"uefp_hit_count_{idx}", None)
        st.session_state.pop(key_playtype, None)
        st.session_state.pop(key_mode, None)
        clear_cached_result()
        st.rerun()

if st.session_state["hit_conditions"]:
    st.success(f"✅ 当前共设置 {len(st.session_state['hit_conditions'])} 条命中特征筛选条件")

st.markdown("---")
st.markdown("## 🧾 查询推荐记录")

if st.button("📥 执行筛选并查询推荐"):
    issue_predictions = fetch_predictions(
        [issue_name],
        playtype_ids=playtype_ids,
        columns=["issue_name", "playtype_id", "user_id", "numbers"],
        ttl=None,
    )
    if issue_predictions.empty:
        clear_cached_result()
        st.info("当前期暂无推荐记录。")
    else:
        issue_predictions = issue_predictions.copy()
        issue_predictions["playtype_id"] = issue_predictions["playtype_id"].astype(int)
        issue_predictions["user_id"] = issue_predictions["user_id"].astype(int)
        issue_predictions["digit_set"] = issue_predictions["numbers"].apply(extract_digit_set)

        number_conditions_payload: list[dict[str, object]] = []
        for cond in st.session_state["filter_conditions"]:
            digits = [d for d in cond.get("numbers", []) if d]
            playtypes = [int(pid) for pid in cond.get("playtypes", []) if pid is not None]
            if not digits or not playtypes:
                continue
            mode = cond.get("mode", "包含") or "包含"
            match_mode = cond.get("match_mode", "全部匹配") or "全部匹配"
            if mode == "不包含":
                match_mode = "全部匹配"
            if match_mode == "任意包含":
                match_mode = "任意匹配"
            number_conditions_payload.append(
                {
                    "digits": digits,
                    "playtypes": playtypes,
                    "mode": mode,
                    "match": match_mode,
                }
            )

        number_users = users_matching_number_conditions(
            issue_predictions, number_conditions_payload
        )

        hit_conditions_payload: list[dict[str, object]] = []
        for cond in st.session_state["hit_conditions"]:
            playtype_value = cond.get("playtype")
            if playtype_value is None:
                continue
            mode = cond.get("mode", "上期命中") or "上期命中"
            payload: dict[str, object] = {
                "playtype": int(playtype_value),
                "mode": mode,
            }
            if mode == "近N期命中M次":
                payload["recent_n"] = int(cond.get("recent_n", 5) or 5)
                payload["expected"] = int(cond.get("hit_n", 3) or 3)
                op_value = cond.get("op", "≥") or "≥"
                op_map = {"≥": ">=", "=": "=", ">": ">", "<": "<", "<=": "<="}
                payload["operator"] = op_map.get(op_value, ">=")
            else:
                payload["recent_n"] = int(cond.get("recent_n", 5) or 5)
                payload["expected"] = int(cond.get("hit_n", 1) or 1)
                payload["operator"] = cond.get("op", ">=") or ">="
            hit_conditions_payload.append(payload)

        hit_users = (
            users_matching_hit_conditions(
                hit_conditions_payload,
                issues,
                issue_name,
                playtype_map,
            )
            if hit_conditions_payload
            else None
        )

        final_users = set(number_users)
        if hit_conditions_payload:
            if not hit_users:
                st.info("命中特征条件无满足用户。")
                final_users = set()
            else:
                final_users &= hit_users

        if not final_users:
            clear_cached_result()
            st.warning("⚠️ 没有符合条件的推荐记录")
        else:
            target_df = issue_predictions[
                (issue_predictions["playtype_id"] == int(target_playtype_id))
                & (issue_predictions["user_id"].isin(final_users))
            ][["user_id", "numbers"]].copy()

            if target_df.empty:
                clear_cached_result()
                st.warning("⚠️ 没有符合条件的推荐记录")
            else:
                open_info = fetch_lottery_info(issue_name) or {}
                nick_map = fetch_expert_names(sorted(final_users))
                st.session_state["uefp_result"] = {
                    "issue_name": issue_name,
                    "target_playtype_name": target_playtype_name,
                    "records": target_df,
                    "user_ids": sorted(final_users),
                    "open_info": open_info,
                    "nick_map": nick_map,
                }

if "uefp_result" in st.session_state:
    cached = st.session_state["uefp_result"]
    rec_df: pd.DataFrame = cached["records"]
    if rec_df.empty:
        st.warning("⚠️ 没有符合条件的推荐记录")
    else:
        issue_name = cached["issue_name"]
        target_playtype_name = cached["target_playtype_name"]
        user_ids: list[int] = cached["user_ids"]
        open_info = cached.get("open_info") or {}
        nick_map = cached.get("nick_map") or {}

        st.markdown(f"### 📋 本期推荐记录（{issue_name}期） - 共 {len(rec_df)} 条")
        st.info(f"共筛选出 {len(user_ids)} 位专家，生成推荐记录 {len(rec_df)} 条")

        open_code = open_info.get("open_code") if open_info else None
        blue_code = open_info.get("blue_code") if open_info else None
        has_open_code = bool(open_code)

        if has_open_code:
            st.markdown("### 🧧 开奖信息", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style='font-size: 18px; line-height: 1.8; display: flex; align-items: center;'>
                    🏆 <b>开奖号码：</b>
                    <span style='color: green; font-weight: bold;'>{open_code}</span>
                    <span style='margin-left: 40px;'>🔵 <b>蓝球：</b>
                    <span style='color: blue; font-weight: bold;'>{blue_code or '无'}</span></span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.warning("⚠️ 当前期号还没有开奖号码，将跳过命中判断，仅展示推荐频次统计")

        normalized_open = normalize_code(open_code) if open_code else ""
        open_digits = list(normalized_open)
        open_digit_set = set(open_digits)

        number_counter: Counter[str] = Counter()
        for numbers in rec_df["numbers"]:
            for token in parse_tokens(numbers):
                number_counter.update(list(token))

        if number_counter:
            freq_df = (
                pd.DataFrame(
                    [
                        {"数字": digit, "被推荐次数": count}
                        for digit, count in number_counter.items()
                    ]
                )
                .sort_values("被推荐次数", ascending=False)
                .reset_index(drop=True)
            )
            hit_digit_count = (
                sum(1 for digit in freq_df["数字"] if digit in open_digit_set)
                if has_open_code
                else 0
            )
            st.markdown(
                f"#### 🎯 推荐数字热力图（共 {len(freq_df)} 个数字，命中：{hit_digit_count} 个）"
            )
            chart = render_horizontal_chart(freq_df, open_digits if has_open_code else [])
            if chart is not None:
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("暂无可视化数据。")
        else:
            st.info("暂无推荐数字统计数据。")

        rows = []
        for row in rec_df.itertuples():
            uid = int(row.user_id)
            numbers = row.numbers
            digits = set("".join(parse_tokens(numbers)))
            hit_digits = open_digit_set & digits if has_open_code else set()
            hit_count = len(hit_digits) if has_open_code else None
            is_hit = (
                match_prediction_hit(target_playtype_name, numbers, open_code)
                if has_open_code and open_code
                else None
            )
            rows.append(
                {
                    "user_id": uid,
                    "AI昵称": nick_map.get(uid, "未知"),
                    "推荐号码": numbers,
                    "命中数量": hit_count,
                    "是否命中": "✅" if is_hit else ("❌" if is_hit is False else "-"),
                }
            )

        detail_df = pd.DataFrame(rows)
        if has_open_code and not detail_df.empty:
            detail_df = detail_df.sort_values(by="命中数量", ascending=False)
        detail_df["命中数量"] = detail_df["命中数量"].apply(
            lambda value: value if value is not None else "-"
        )
        if not has_open_code:
            detail_df["是否命中"] = "-"
        st.markdown("### 👤 推荐详情表格")
        st.dataframe(detail_df.reset_index(drop=True), use_container_width=True)
