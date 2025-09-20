from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st
from collections import Counter

from db.connection import query_db
from utils.cache import cached_query
from utils.data_access import fetch_lottery_info, fetch_playtypes_for_issue
from utils.ui import issue_picker, playtype_picker, render_rank_position_calculator
from utils.numbers import normalize_code, parse_tokens
from utils.sql import make_in_clause
from utils.charts import render_digit_frequency_chart


st.set_page_config(page_title="推荐号码热力图（简版）", layout="wide")
st.header("NumberHeatmap_Simplified - 推荐号码热力图（简版）")


def render_digit_chart(freq_df: pd.DataFrame, open_digits: list[str]) -> alt.Chart | None:
    return render_digit_frequency_chart(
        freq_df,
        hit_digits=open_digits,
        digit_column="数字",
        count_column="被推荐次数",
        width=320,
    )


selected_issue = issue_picker(
    "heatmap_issue",
    mode="single",
    label="期号",
)
if not selected_issue:
    st.stop()

lottery_info = fetch_lottery_info(selected_issue)
open_digits = []
if lottery_info:
    open_code = lottery_info.get("open_code") or ""
    normalized_open = normalize_code(open_code)
    open_digits = list(normalized_open)
    st.caption(
        f"开奖号码：{open_code or '未开奖'}丨和值：{lottery_info.get('sum')}丨跨度：{lottery_info.get('span')}"
    )

playtypes_df = fetch_playtypes_for_issue(selected_issue)
if playtypes_df.empty:
    st.info("当前期号无推荐记录。")
    st.stop()

playtype_map = {
    int(row.playtype_id): row.playtype_name for row in playtypes_df.itertuples()
}
raw_playtypes = playtype_picker(
    "heatmap_playtypes",
    mode="multi",
    label="玩法",
    include=[str(pid) for pid in playtype_map.keys()],
    default=[str(pid) for pid in playtype_map.keys()],
)
selected_playtypes = [int(pid) for pid in raw_playtypes]

if not selected_playtypes:
    st.warning("请至少选择一个玩法。")
    st.stop()

clause, params = make_in_clause("playtype_id", selected_playtypes, "pt")
params.update({"issue": selected_issue})
sql_predictions = f"""
    SELECT playtype_id, numbers
    FROM expert_predictions
    WHERE issue_name = :issue
      AND {clause}
"""

try:
    rows = cached_query(query_db, sql_predictions, params=params, ttl=120)
except Exception as exc:  # pragma: no cover - 外部资源
    st.warning(f"查询推荐数据失败：{exc}")
    rows = []

if not rows:
    st.info("未找到符合条件的推荐记录。")
    st.stop()

playtype_counters: dict[int, Counter[str]] = {pid: Counter() for pid in selected_playtypes}
for row in rows:
    playtype_id = int(row["playtype_id"])
    counter = playtype_counters.get(playtype_id)
    if counter is None:
        continue
    tokens = parse_tokens(row["numbers"])
    digits: list[str] = []
    for token in tokens:
        digits.extend(list(token))
    counter.update(digits)

rank_pool: dict[int, list[str]] = {}
charts: list[tuple[str, pd.DataFrame, alt.Chart]] = []

for playtype_id in selected_playtypes:
    counter = playtype_counters.get(playtype_id)
    if not counter:
        continue
    freq_df = (
        pd.DataFrame(counter.items(), columns=["数字", "被推荐次数"])
        .sort_values("被推荐次数", ascending=False)
        .reset_index(drop=True)
    )
    if open_digits:
        freq_df["命中状态"] = freq_df["数字"].apply(lambda d: "命中" if d in open_digits else "未命中")
    else:
        freq_df["命中状态"] = "未开奖"

    chart = render_digit_chart(freq_df, open_digits)

    playtype_name = playtype_map.get(playtype_id, str(playtype_id))
    charts.append((playtype_name, freq_df, chart))
    rank_pool[playtype_id] = freq_df["数字"].tolist()

st.subheader("各玩法推荐数字热力图")
if not charts:
    st.info("所选玩法暂无推荐数据。")
else:
    for idx in range(0, len(charts), 4):
        chunk = charts[idx : idx + 4]
        cols = st.columns(len(chunk))
        for col, (playtype_name, _freq_df, chart) in zip(cols, chunk):
            col.markdown(f"**{playtype_name}**")
            if chart is not None:
                col.altair_chart(chart, use_container_width=True)
            else:
                col.info("无可视化数据。")

st.subheader("排行榜命中检测")
if not rank_pool:
    st.info("暂无数据用于命中检测。")
else:
    playtype_names = [playtype_map.get(pid, str(pid)) for pid in rank_pool.keys()]
    selected_name = st.selectbox("玩法", options=playtype_names)
    selected_id = next(
        (pid for pid, name in playtype_map.items() if name == selected_name),
        None,
    )
    range_label = st.selectbox(
        "历史范围",
        options=["最近2期", "最近10期", "最近20期", "所有历史"],
        index=1,
    )
    range_limit = {"最近2期": 2, "最近10期": 10, "最近20期": 20}.get(range_label)

    if st.button("开始检测"):
        if selected_id is None:
            st.warning("无法确定所选玩法编号。")
        else:
            history_rows = cached_query(
                query_db,
                """
                    SELECT DISTINCT issue_name
                    FROM expert_predictions
                    WHERE playtype_id = :playtype_id AND issue_name < :current_issue
                    ORDER BY issue_name DESC
                """,
                params={"playtype_id": selected_id, "current_issue": selected_issue},
                ttl=120,
            )
            history_issues = [row["issue_name"] for row in history_rows]
            if range_limit:
                history_issues = history_issues[:range_limit]

            if not history_issues:
                st.warning("缺少历史期号用于检测。")
            else:
                pos_counter = {i: 0 for i in range(1, 11)}
                for issue in history_issues:
                    rows = cached_query(
                        query_db,
                        """
                            SELECT numbers
                            FROM expert_predictions
                            WHERE issue_name = :issue AND playtype_id = :playtype_id
                        """,
                        params={"issue": issue, "playtype_id": selected_id},
                        ttl=120,
                    )
                    if not rows:
                        continue
                    digits: list[str] = []
                    for row in rows:
                        for token in parse_tokens(row["numbers"]):
                            digits.extend(list(token))
                    if not digits:
                        continue

                    series = pd.Series(digits).value_counts().head(10)
                    info = fetch_lottery_info(issue)
                    drawn = []
                    if info:
                        drawn = list(normalize_code(info.get("open_code")))
                    for rank, digit in enumerate(series.index.tolist(), start=1):
                        if rank > 10:
                            break
                        if drawn and digit in drawn:
                            pos_counter[rank] += 1

                result_df = pd.DataFrame(
                    {
                        "排行榜位置": list(pos_counter.keys()),
                        "命中次数": list(pos_counter.values()),
                    }
                )
                st.bar_chart(result_df.set_index("排行榜位置"))

render_rank_position_calculator(
    [
        (playtype_map.get(pid, str(pid)), digits)
        for pid, digits in rank_pool.items()
    ],
    key="heatmap_rank",
)
