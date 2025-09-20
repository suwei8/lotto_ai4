from __future__ import annotations

import re
from collections import Counter
from typing import Dict, Iterable, List, Sequence, Tuple

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import (
    fetch_lottery_info,
    fetch_playtypes,
)
from utils.numbers import match_prediction_hit, normalize_code, parse_tokens
from utils.charts import render_digit_frequency_chart
from utils.sql import make_in_clause


st.set_page_config(page_title="AI 命中统计分析", layout="wide")
st.header("UserExpertHitStat - AI 命中表现分析")
st.caption("固定彩种：福彩3D")

# --------- 常量与辅助配置 ---------
POSITIONAL_PLAYTYPES: Dict[str, int] = {
    "百位定3": 0,
    "十位定3": 1,
    "个位定3": 2,
    "百位定1": 0,
    "十位定1": 1,
    "个位定1": 2,
    "定位3*3*3-百位": 0,
    "定位3*3*3-十位": 1,
    "定位3*3*3-个位": 2,
    "定位4*4*4-百位": 0,
    "定位4*4*4-十位": 1,
    "定位4*4*4-个位": 2,
    "定位5*5*5-百位": 0,
    "定位5*5*5-十位": 1,
    "定位5*5*5-个位": 2,
    "万位杀3": 0,
    "千位杀3": 1,
    "百位杀3": 2,
    "十位杀3": 3,
    "个位杀3": 4,
    "万位杀1": 0,
    "千位杀1": 1,
    "百位杀1": 2,
    "十位杀1": 3,
    "个位杀1": 4,
    "万位定5": 0,
    "千位定5": 1,
    "百位定5": 2,
    "十位定5": 3,
    "个位定5": 4,
    "万位定3": 0,
    "千位定3": 1,
    "万位定1": 0,
    "千位定1": 1,
}

PLAYTYPE_DICT = fetch_playtypes()
PLAYTYPE_NAME_TO_ID: Dict[str, int] = (
    {row.playtype_name: int(row.playtype_id) for row in PLAYTYPE_DICT.itertuples()}
    if not PLAYTYPE_DICT.empty
    else {}
)
PLAYTYPE_ID_TO_NAME: Dict[int, str] = (
    {int(row.playtype_id): row.playtype_name for row in PLAYTYPE_DICT.itertuples()}
    if not PLAYTYPE_DICT.empty
    else {}
)


# --------- 数据查询辅助函数 ---------

def fetch_stat_issues() -> List[str]:
    rows = cached_query(
        query_db,
        "SELECT DISTINCT issue_name FROM expert_hit_stat ORDER BY issue_name DESC",
        params=None,
        ttl=120,
    )
    return [str(row["issue_name"]) for row in rows]


def fetch_playtypes_for_issue(issue: str) -> List[Tuple[int, str]]:
    rows = cached_query(
        query_db,
        """
        SELECT DISTINCT s.playtype_id AS pid, d.playtype_name AS pname
        FROM expert_hit_stat s
        JOIN playtype_dict d ON d.playtype_id = s.playtype_id
        WHERE s.issue_name = :issue
        ORDER BY s.playtype_id
        """,
        params={"issue": issue},
        ttl=120,
    )
    return [
        (int(row["pid"]), row.get("pname") or PLAYTYPE_ID_TO_NAME.get(int(row["pid"]), str(row["pid"])))
        for row in rows
    ]


def fetch_hit_summary(issues: Sequence[str], playtype_id: int) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=["user_id", "total_count", "hit_count", "hit_number_count"])
    clause, params = make_in_clause("issue_name", issues, "issue")
    params["playtype"] = int(playtype_id)
    sql = f"""
        SELECT user_id,
               SUM(total_count) AS total_count,
               SUM(hit_count) AS hit_count,
               SUM(hit_number_count) AS hit_number_count
        FROM expert_hit_stat
        WHERE {clause} AND playtype_id = :playtype
        GROUP BY user_id
    """
    rows = cached_query(query_db, sql, params=params, ttl=120)
    return pd.DataFrame(rows)


def fetch_nick_map(user_ids: Iterable[int]) -> Dict[int, str]:
    ids = list(user_ids)
    if not ids:
        return {}
    clause, params = make_in_clause("user_id", ids, "uid")
    sql = f"SELECT user_id, nick_name FROM expert_info WHERE {clause}"
    rows = cached_query(query_db, sql, params=params, ttl=300)
    return {int(row["user_id"]): row.get("nick_name") or "未知" for row in rows}


def fetch_query_issues() -> List[str]:
    sql = """
        SELECT issue_name
        FROM (
            SELECT DISTINCT issue_name FROM expert_hit_stat
            UNION
            SELECT DISTINCT issue_name FROM expert_predictions
        ) AS merged
        ORDER BY issue_name DESC
    """
    rows = cached_query(query_db, sql, params=None, ttl=120)
    return [str(row["issue_name"]) for row in rows]


def fetch_last_hit_status(issue: str, playtype_id: int) -> Tuple[set[int], set[int]]:
    rows = cached_query(
        query_db,
        """
        SELECT user_id, hit_count
        FROM expert_hit_stat
        WHERE issue_name = :issue AND playtype_id = :playtype
        """,
        params={"issue": issue, "playtype": int(playtype_id)},
        ttl=120,
    )
    hit_users = {int(row["user_id"]) for row in rows if row.get("hit_count", 0)}
    miss_users = {int(row["user_id"]) for row in rows if not row.get("hit_count", 0)}
    return hit_users, miss_users


def fetch_predictions_for_users(issue: str, playtype_id: int, user_ids: Sequence[int]) -> pd.DataFrame:
    ids = list(user_ids)
    if not ids:
        return pd.DataFrame(columns=["user_id", "numbers"])
    clause, params = make_in_clause("user_id", ids, "uid")
    params.update({"issue": issue, "playtype": int(playtype_id)})
    sql = f"""
        SELECT user_id, numbers
        FROM expert_predictions
        WHERE issue_name = :issue AND playtype_id = :playtype AND {clause}
    """
    rows = cached_query(query_db, sql, params=params, ttl=120)
    return pd.DataFrame(rows)


# --------- 页面主流程 ---------

issues = fetch_stat_issues()
if not issues:
    st.warning("无法获取期号列表。")
    st.stop()

selected_issues = st.multiselect(
    "📅 选择期号（默认全选）",
    options=issues,
    default=issues,
)
if not selected_issues:
    st.warning("请至少选择一个期号。")
    st.stop()

first_issue = selected_issues[0]
playtype_pairs = fetch_playtypes_for_issue(first_issue)
if not playtype_pairs:
    st.info("所选期号暂无玩法数据。")
    st.stop()

playtype_ids = [pid for pid, _ in playtype_pairs]
playtype_name_map = {pid: name for pid, name in playtype_pairs}

selected_playtype_id = st.selectbox(
    "🎮 选择玩法",
    options=playtype_ids,
    format_func=lambda pid: playtype_name_map.get(pid, PLAYTYPE_ID_TO_NAME.get(pid, str(pid))),
)
selected_playtype_name = playtype_name_map.get(
    selected_playtype_id, PLAYTYPE_ID_TO_NAME.get(selected_playtype_id, str(selected_playtype_id))
)

if st.button("📊 分析 AI 命中表现"):
    summary_df = fetch_hit_summary(selected_issues, selected_playtype_id)
    if summary_df.empty:
        st.info("所选条件下无命中统计数据。")
    else:
        summary_df["user_id"] = summary_df["user_id"].astype(int)
        nick_map = fetch_nick_map(summary_df["user_id"].tolist())
        summary_df["预测期数"] = summary_df["total_count"].fillna(0).astype(int)
        summary_df["命中期数"] = summary_df["hit_count"].fillna(0).astype(int)
        summary_df["命中数字数量"] = summary_df["hit_number_count"].fillna(0).astype(int)
        summary_df["命中率"] = summary_df.apply(
            lambda row: round(row["命中数字数量"] / row["预测期数"], 4)
            if row["预测期数"]
            else 0,
            axis=1,
        )
        summary_df["AI昵称"] = summary_df["user_id"].map(nick_map).fillna("未知")
        result_df = summary_df[
            ["user_id", "AI昵称", "命中期数", "预测期数", "命中数字数量", "命中率"]
        ].sort_values(by="命中率", ascending=False)
        st.session_state["uehs_summary"] = {
            "result": result_df.reset_index(drop=True),
            "issues": list(selected_issues),
            "playtype_id": int(selected_playtype_id),
            "playtype_name": selected_playtype_name,
            "playtype_options": playtype_pairs,
        }

if "uehs_summary" not in st.session_state:
    st.stop()

state = st.session_state["uehs_summary"]
result_df: pd.DataFrame = state["result"]
history_issues: List[str] = state["issues"]
selected_playtype_id: int = state["playtype_id"]
selected_playtype_name: str = state.get(
    "playtype_name", PLAYTYPE_ID_TO_NAME.get(selected_playtype_id, str(selected_playtype_id))
)
playtype_pairs = state.get("playtype_options", [])
if not playtype_pairs:
    playtype_pairs = fetch_playtypes_for_issue(history_issues[0])

st.markdown(f"### 📋 AI 命中表现统计表（共 {len(result_df)} 位）")
if result_df.empty:
    st.info("无统计数据。")
    st.stop()

# 分布统计 - 命中期数
hit_counts = result_df["命中期数"].value_counts().sort_index()
total_users = len(result_df)
hit_lines = [
    f"<b>命中期数 {val}</b>：{count} 人（占比 {round(count / total_users * 100, 2)}%）"
    for val, count in hit_counts.items()
]
columns = [[], [], [], []]
for idx, line in enumerate(hit_lines):
    columns[idx % 4].append(line)
block = "".join(
    f"<div style='flex:1'>{'<br>'.join(col)}</div>" for col in columns if col
)
st.markdown("**命中期数分布统计：**", unsafe_allow_html=True)
st.markdown(f"<div style='display:flex;gap:24px'>{block}</div>", unsafe_allow_html=True)

# 分布统计 - 命中数字数量
hit_num_counts = result_df["命中数字数量"].value_counts().sort_index()
num_lines = [
    f"<b>命中数字数量 {val}</b>：{count} 人（占比 {round(count / total_users * 100, 2)}%）"
    for val, count in hit_num_counts.items()
]
columns2 = [[], [], [], []]
for idx, line in enumerate(num_lines):
    columns2[idx % 4].append(line)
block2 = "".join(
    f"<div style='flex:1'>{'<br>'.join(col)}</div>" for col in columns2 if col
)
st.markdown("**命中数字数量分布统计：**", unsafe_allow_html=True)
st.markdown(f"<div style='display:flex;gap:24px'>{block2}</div>", unsafe_allow_html=True)

st.dataframe(
    result_df[["user_id", "AI昵称", "命中期数", "预测期数", "命中数字数量", "命中率"]],
    use_container_width=True,
    hide_index=True,
)

# --------- 推荐记录反查与可视化 ---------
st.markdown("---")
st.markdown("### 🔍 按命中条件筛选专家并反查推荐记录")

hit_options = sorted(result_df["命中期数"].unique())
num_hit_options = sorted(result_df["命中数字数量"].unique())
selected_hit_values = st.multiselect(
    "🎯 命中期数筛选",
    options=hit_options,
    default=hit_options,
)
selected_num_hit_values = st.multiselect(
    "🎯 命中数字数量筛选",
    options=num_hit_options,
    default=num_hit_options,
)
hit_status_filter = st.radio(
    "🎯 上期命中状态",
    options=["不过滤", "上期命中", "上期未命中"],
    horizontal=True,
)

query_issue_options = fetch_query_issues()
if not query_issue_options:
    query_issue_options = history_issues
query_issue = st.selectbox("📅 查询期号", options=query_issue_options)

query_playtype_ids = [pid for pid, _ in playtype_pairs]
query_playtype_name_map = {pid: name for pid, name in playtype_pairs}
default_index = query_playtype_ids.index(selected_playtype_id) if selected_playtype_id in query_playtype_ids else 0
query_playtype_id = st.selectbox(
    "🎮 查询玩法",
    options=query_playtype_ids,
    index=default_index,
    format_func=lambda pid: query_playtype_name_map.get(pid, PLAYTYPE_ID_TO_NAME.get(pid, str(pid))),
)
query_playtype_name = query_playtype_name_map.get(
    query_playtype_id, PLAYTYPE_ID_TO_NAME.get(query_playtype_id, str(query_playtype_id))
)

if st.button("📥 查询推荐记录"):
    filtered = result_df[
        result_df["命中期数"].isin(selected_hit_values)
        & result_df["命中数字数量"].isin(selected_num_hit_values)
    ]

    if filtered.empty:
        st.warning("当前筛选条件下没有专家。")
        st.session_state.pop("uehs_records", None)
    else:
        # 上期命中筛选
        if hit_status_filter != "不过滤":
            try:
                issue_idx = query_issue_options.index(query_issue)
            except ValueError:
                issue_idx = -1
            last_issue = query_issue_options[issue_idx + 1] if issue_idx >= 0 and issue_idx + 1 < len(query_issue_options) else None
            hit_users_last: set[int] = set()
            miss_users_last: set[int] = set()
            if last_issue:
                hit_users_last, miss_users_last = fetch_last_hit_status(last_issue, query_playtype_id)
            if hit_status_filter == "上期命中":
                filtered = filtered[filtered["user_id"].isin(hit_users_last)]
            else:
                filtered = filtered[filtered["user_id"].isin(miss_users_last)]
        if filtered.empty:
            st.warning("筛选条件下无专家符合。")
            st.session_state.pop("uehs_records", None)
        else:
            rec_df = fetch_predictions_for_users(
                query_issue, query_playtype_id, filtered["user_id"].tolist()
            )
            st.session_state["uehs_records"] = {
                "records": rec_df,
                "issue": query_issue,
                "playtype_id": int(query_playtype_id),
                "playtype_name": query_playtype_name,
                "nick_map": dict(zip(result_df["user_id"], result_df["AI昵称"])),
            }

if "uehs_records" in st.session_state:
    record_state = st.session_state["uehs_records"]
    rec_df: pd.DataFrame = record_state.get("records", pd.DataFrame())
    issue_for_display: str = record_state.get("issue", "")
    playtype_id_for_display: int = record_state.get("playtype_id", selected_playtype_id)
    playtype_name_for_display: str = record_state.get(
        "playtype_name",
        PLAYTYPE_ID_TO_NAME.get(playtype_id_for_display, str(playtype_id_for_display)),
    )
    nick_map: Dict[int, str] = record_state.get("nick_map", {})

    if rec_df.empty:
        st.info("筛选条件下未找到推荐记录。")
    else:
        rec_df["user_id"] = rec_df["user_id"].astype(int)
        open_info = fetch_lottery_info(issue_for_display) or {}
        open_code = open_info.get("open_code")
        blue_code = open_info.get("blue_code")
        has_open_code = bool(open_code)

        st.markdown(f"### 📋 推荐记录（{issue_for_display} 期） - 共 {len(rec_df)} 条")
        if has_open_code:
            st.markdown("### 🧧 开奖信息", unsafe_allow_html=True)
            st.markdown(
                f"""
                <div style='font-size: 18px; line-height: 1.6;'>
                    🏆 <b>开奖号码：</b> <span style='color: green; font-weight: bold;'>{open_code}</span>
                    <span style='margin-left: 32px;'>🔵 <b>蓝球：</b> <span style='color: blue; font-weight: bold;'>{blue_code or '无'}</span></span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        number_counter: Counter[str] = Counter()
        for numbers in rec_df["numbers"]:
            for token in parse_tokens(numbers):
                number_counter.update(list(token))

        if number_counter:
            freq_df = (
                pd.DataFrame(
                    [{"数字": digit, "出现次数": count} for digit, count in number_counter.items()]
                )
                .sort_values("出现次数", ascending=False)
                .reset_index(drop=True)
            )
            normalized_open = normalize_code(open_code) if open_code else ""
            open_digits = list(normalized_open)
            positional_index = POSITIONAL_PLAYTYPES.get(playtype_name_for_display)

            def digit_hit(digit: str) -> bool:
                if not has_open_code:
                    return False
                if positional_index is not None:
                    digits_list = list(normalized_open)
                    if positional_index < len(digits_list):
                        return digit == digits_list[positional_index]
                    return False
                target_set = set(open_digits)
                if blue_code:
                    target_set.update(list(normalize_code(str(blue_code))))
                return digit in target_set

            freq_df["是否命中"] = freq_df["数字"].apply(lambda d: "✅" if digit_hit(d) else "")
            hit_digit_count = int((freq_df["是否命中"] == "✅").sum())
            st.markdown(
                f"#### 🎯 推荐数字出现频次热力图（共 {len(freq_df)} 个数字，命中：{hit_digit_count} 个）"
            )
            chart = render_digit_frequency_chart(
                freq_df.rename(columns={"出现次数": "被推荐次数"}),
                digit_column="数字",
                count_column="被推荐次数",
                hit_digits=open_digits if has_open_code else None,
                height=min(40 * len(freq_df), 800),
            )
            if chart is not None:
                st.altair_chart(chart, use_container_width=True)
        else:
            st.info("暂无推荐数字统计数据。")

        detail_rows: List[Dict[str, object]] = []
        normalized_open_digits = set(list(normalize_code(open_code))) if open_code else set()
        if blue_code:
            normalized_open_digits.update(list(normalize_code(str(blue_code))))

        for row in rec_df.itertuples():
            uid = int(row.user_id)
            numbers = row.numbers
            digits = set("".join(parse_tokens(numbers)))
            hit_digits = normalized_open_digits & digits if has_open_code else set()
            if has_open_code:
                is_hit = match_prediction_hit(playtype_name_for_display, numbers, open_code or "")
            else:
                is_hit = None
            detail_rows.append(
                {
                    "user_id": uid,
                    "AI昵称": nick_map.get(uid, "未知"),
                    "推荐号码": numbers,
                    "命中数量": len(hit_digits) if has_open_code else "-",
                    "是否命中": "✅" if is_hit else ("❌" if is_hit is False else "-"),
                }
            )

        detail_df = pd.DataFrame(detail_rows)
        if has_open_code and not detail_df.empty:
            detail_df = detail_df.sort_values(by="命中数量", ascending=False)
        st.markdown("### 📋 推荐详情表格")
        st.dataframe(detail_df.reset_index(drop=True), use_container_width=True)

        st.markdown("### 🧮 号码组合统计")
        combo_counter = Counter(rec_df["numbers"])
        combo_df = (
            pd.DataFrame(combo_counter.items(), columns=["号码组合", "出现次数"])
            .sort_values("出现次数", ascending=False)
            .reset_index(drop=True)
        )
        digits_options = [str(i) for i in range(10)]
        exclude_digits = st.multiselect("🚫 排除包含以下数字的组合", digits_options)
        include_digits = st.multiselect("✅ 仅保留包含以下数字的组合", digits_options)
        search_keywords = st.text_input(
            "🔍 搜索包含数字（多个数字可用逗号分隔）",
            help="模糊匹配组合中包含的数字，不限制顺序",
        )

        def should_keep(combo: str) -> bool:
            parts = set(combo.split(","))
            if exclude_digits and any(d in parts for d in exclude_digits):
                return False
            if include_digits and not all(d in parts for d in include_digits):
                return False
            if search_keywords:
                keywords = re.findall(r"\d", search_keywords)
                if not all(k in parts for k in keywords):
                    return False
            return True

        filtered_combo_df = combo_df[combo_df["号码组合"].apply(should_keep)]
        st.markdown(f"#### 📋 号码组合统计（共 {len(filtered_combo_df)} 个）")
        st.dataframe(filtered_combo_df.reset_index(drop=True), use_container_width=True)

# Top20 柱状图
st.markdown("---")
chart_df = result_df[["AI昵称", "命中期数"]].head(20)
if not chart_df.empty:
    chart = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            x=alt.X("AI昵称", sort="-y"),
            y=alt.Y("命中期数"),
            tooltip=["AI昵称", "命中期数"],
        )
        .properties(width="container", height=360, title="🎯 命中期数 Top 20")
    )
    st.altair_chart(chart, use_container_width=True)
