from __future__ import annotations

from collections import Counter

import pandas as pd
import streamlit as st
st.set_page_config(page_title="Lotto AI", layout="wide")

from db.connection import query_db
from utils.cache import cached_query
from utils.numbers import normalize_code
from utils.charts import render_digit_frequency_chart

st.header("HotCold - 开奖冷热分析")

recent_n = st.slider("统计最近多少期", min_value=10, max_value=200, value=30, step=5)

sql = """
    SELECT issue_name, open_code, `sum`, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    ORDER BY open_time DESC, issue_name DESC
    LIMIT :limit
"""

try:
    rows = cached_query(query_db, sql, params={"limit": int(recent_n)}, ttl=120)
except Exception as exc:
    st.warning(f"查询开奖数据失败：{exc}")
    rows = []

if not rows:
    st.info("无法获取开奖数据。")
    st.stop()

lottery_df = pd.DataFrame(rows)
lottery_df["open_code"] = lottery_df["open_code"].apply(normalize_code)
lottery_df = lottery_df[lottery_df["open_code"].str.len() >= 3]
lottery_df["digits"] = lottery_df["open_code"].apply(lambda code: list(code[:3]))
lottery_df["hundreds"] = lottery_df["digits"].apply(lambda values: values[0])
lottery_df["tens"] = lottery_df["digits"].apply(lambda values: values[1])
lottery_df["units"] = lottery_df["digits"].apply(lambda values: values[2])

st.caption(
    f"统计范围：最近 {len(lottery_df)} 期（最新期 {lottery_df.iloc[0]['issue_name']}）"
)

history_view = lottery_df[
    ["issue_name", "open_code", "sum", "span", "odd_even_ratio", "big_small_ratio"]
].copy()
history_view.rename(
    columns={
        "issue_name": "期号",
        "open_code": "开奖号码",
        "sum": "和值",
        "span": "跨度",
        "odd_even_ratio": "奇偶比",
        "big_small_ratio": "大小比",
    },
    inplace=True,
)

st.subheader(f"所选近{len(lottery_df)}期的开奖信息")
st.dataframe(history_view, width="stretch")

# Overall hot/cold
all_digits = [digit for digits in lottery_df["digits"] for digit in digits]
overall_counter = Counter(all_digits)
all_total = sum(overall_counter.values())
overall_df = pd.DataFrame(
    [
        {"digit": digit, "count": count, "ratio": count / all_total if all_total else 0}
        for digit, count in sorted(overall_counter.items())
    ]
)

st.subheader("总体冷热分布")
st.dataframe(overall_df, width="stretch")

chart = render_digit_frequency_chart(
    overall_df.rename(columns={"digit": "数字", "count": "出现次数"}),
    digit_column="数字",
    count_column="出现次数",
    tooltip_columns=["ratio"],
)
if chart is not None:
    st.altair_chart(chart, use_container_width=True)

top_k = st.slider("热榜 TopK", min_value=3, max_value=10, value=5)

hot_list = overall_df.sort_values(by="count", ascending=False).head(top_k)
cold_list = overall_df.sort_values(by="count", ascending=True).head(top_k)

st.write(
    "热号：", ", ".join(f"{row.digit}({row.count})" for row in hot_list.itertuples())
)
st.write(
    "冷号：", ", ".join(f"{row.digit}({row.count})" for row in cold_list.itertuples())
)


# Position specific analysis
def position_analysis(column: str) -> pd.DataFrame:
    counter = Counter(lottery_df[column].tolist())
    total = sum(counter.values())
    return pd.DataFrame(
        [
            {"digit": digit, "count": count, "ratio": count / total if total else 0}
            for digit, count in sorted(counter.items())
        ]
    )


positions = {
    "百位": position_analysis("hundreds"),
    "十位": position_analysis("tens"),
    "个位": position_analysis("units"),
}

st.subheader("分位冷热分析")
cols = st.columns(3)
for col, (title, data) in zip(cols, positions.items()):
    display_df = data.rename(columns={"digit": "数字", "count": "出现次数"})
    col.dataframe(display_df, width="stretch")
    chart = render_digit_frequency_chart(
        display_df,
        digit_column="数字",
        count_column="出现次数",
        tooltip_columns=["ratio"],
        width=240,
        height=240,
    )
    if chart is not None:
        col.altair_chart(chart, use_container_width=True)

st.caption("冷热分析仅供参考，不构成投注建议。")
