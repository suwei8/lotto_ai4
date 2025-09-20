from __future__ import annotations

from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from utils.data_access import (
    fetch_lottery_infos,
    fetch_playtypes,
    fetch_predictions,
)
from utils.numbers import normalize_code, parse_tokens
from utils.ui import issue_picker, playtype_picker

st.set_page_config(page_title="多期推荐数字热力图", layout="wide")
st.header("NumberHeatmap_Simplified_v2_all - 多期推荐数字热力图")

selected_issues = issue_picker(
    "heatmap_v2_issues",
    mode="multi",
    label="期号",
)
selected_issues = [str(issue) for issue in selected_issues]
if not selected_issues:
    st.warning("请至少选择一个期号。")
    st.stop()

playtypes = fetch_playtypes()
if playtypes.empty:
    st.warning("玩法字典为空。")
    st.stop()

playtype_map = {int(row.playtype_id): row.playtype_name for row in playtypes.itertuples()}
raw_playtype = playtype_picker(
    "heatmap_v2_playtype",
    mode="single",
    label="玩法",
    include=[str(pid) for pid in playtype_map.keys()],
)
if not raw_playtype:
    st.stop()
selected_playtype_id = int(raw_playtype)
selected_playtype_name = playtype_map.get(selected_playtype_id, str(selected_playtype_id))

lottery_info_map = fetch_lottery_infos(selected_issues, ttl=None)

predictions_df = fetch_predictions(
    selected_issues,
    playtype_ids=[selected_playtype_id],
    columns=["issue_name", "numbers"],
    ttl=None,
)
if not predictions_df.empty:
    predictions_df["issue_name"] = predictions_df["issue_name"].astype(str)

charts: list[tuple[str, pd.DataFrame, alt.Chart]] = []
if not predictions_df.empty:
    grouped_numbers = {
        issue: group["numbers"].tolist()
        for issue, group in predictions_df.groupby("issue_name")
    }
    for issue in selected_issues:
        numbers_list = grouped_numbers.get(issue)
        if not numbers_list:
            continue

        counter: Counter[str] = Counter()
        for numbers in numbers_list:
            for token in parse_tokens(numbers):
                counter.update(list(token))

        if not counter:
            continue

        freq_df = (
            pd.DataFrame(counter.items(), columns=["数字", "被推荐次数"])
            .sort_values("被推荐次数", ascending=False)
            .reset_index(drop=True)
        )
        open_info = lottery_info_map.get(issue)
        open_digits = []
        if open_info:
            open_digits = list(normalize_code(open_info.get("open_code")))
        open_set = set(open_digits)
        freq_df["命中状态"] = freq_df["数字"].apply(
            lambda digit, open_set=open_set: "命中" if digit in open_set else "未命中"
        )

        chart_df = freq_df.copy()
        chart_df["数字"] = chart_df["数字"].astype(str)
        chart = (
            alt.Chart(chart_df)
            .mark_bar()
            .encode(
                y=alt.Y("数字:N", sort="-x", axis=alt.Axis(labelFontSize=13)),
                x=alt.X("被推荐次数:Q", title="推荐次数"),
                color=alt.Color(
                    "命中状态:N",
                    title="命中状态",
                    scale=alt.Scale(domain=["命中", "未命中"], range=["#1f77b4", "#d62728"]),
                ),
                tooltip=["数字", "被推荐次数", "命中状态"],
            )
            .properties(height=max(320, 28 * len(chart_df)), width=320)
        )
        text = (
            alt.Chart(chart_df)
            .mark_text(align="left", baseline="middle", dx=4, color="#333")
            .encode(y=alt.Y("数字:N", sort="-x"), x=alt.X("被推荐次数:Q"), text="被推荐次数:Q")
        )
        charts.append((issue, chart_df, chart + text))

st.subheader("各期所选玩法推荐数字热力图")
if not charts:
    st.info("所选期号未找到推荐数据。")
else:
    for idx in range(0, len(charts), 4):
        chunk = charts[idx : idx + 4]
        cols = st.columns(len(chunk))
        for col, (issue, _freq_df, chart) in zip(cols, chunk):
            open_code = (
                lottery_info_map.get(issue, {}).get("open_code") if lottery_info_map else None
            )
            title = f"{issue} 期"
            if open_code:
                title += f"｜开奖号码：{open_code}"
            col.markdown(f"**{title}**")
            if chart is not None:
                col.altair_chart(chart, use_container_width=True)
            else:
                col.info("无可视化数据。")

st.caption(f"玩法：{selected_playtype_name}")
