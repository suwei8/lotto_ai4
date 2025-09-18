from __future__ import annotations

from collections import Counter

import altair as alt
import pandas as pd
import streamlit as st

from db.connection import query_db
from utils.cache import cached_query
from utils.numbers import normalize_code
from utils.ui import download_csv_button

st.header("HotCold - 开奖冷热分析")

recent_n = st.slider("统计最近多少期", min_value=10, max_value=200, value=30, step=5)
window_max = max(5, min(50, recent_n // 2))
window_size = st.slider(
    "近态对比滑窗长度", min_value=5, max_value=window_max, value=min(10, window_max)
)

sql = """
    SELECT issue_name, open_code, open_time
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
st.dataframe(overall_df, use_container_width=True)
download_csv_button(overall_df, "下载总体冷热", "hotcold_overall")

chart = (
    alt.Chart(overall_df)
    .mark_bar()
    .encode(
        x=alt.X("digit:N", title="数字"),
        y=alt.Y("count:Q", title="出现次数"),
        tooltip=["digit", "count", alt.Tooltip("ratio:Q", format=".2%")],
    )
    .properties(width=600, height=300)
)
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
    col.dataframe(data, use_container_width=True)
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("digit:N", title=title),
            y=alt.Y("count:Q"),
            tooltip=["digit", "count", alt.Tooltip("ratio:Q", format=".2%")],
        )
        .properties(width=240, height=240)
    )
    col.altair_chart(chart, use_container_width=True)

# Trend comparison
if len(lottery_df) >= window_size * 2:
    recent_window = lottery_df.iloc[:window_size]
    previous_window = lottery_df.iloc[window_size : window_size * 2]

    def window_counter(df: pd.DataFrame) -> Counter:
        digits = [digit for digits in df["digits"] for digit in digits]
        return Counter(digits)

    recent_counter = window_counter(recent_window)
    previous_counter = window_counter(previous_window)
    trend_records = []
    for digit in map(str, range(10)):
        diff = recent_counter.get(digit, 0) - previous_counter.get(digit, 0)
        trend_records.append({"digit": digit, "diff": diff})
    trend_df = pd.DataFrame(trend_records)
    st.subheader("近态对比（总位）")
    trend_chart = (
        alt.Chart(trend_df)
        .mark_bar()
        .encode(
            x="digit:N",
            y="diff:Q",
            color=alt.condition(
                "datum.diff>0", alt.value("#ff7f0e"), alt.value("#1f77b4")
            ),
        )
        .properties(width=600, height=300)
    )
    st.altair_chart(trend_chart, use_container_width=True)

    position_trend_records = []
    position_columns = [("hundreds", "百位"), ("tens", "十位"), ("units", "个位")]
    for column, label in position_columns:
        recent_counter = Counter(recent_window[column])
        previous_counter = Counter(previous_window[column])
        for digit in map(str, range(10)):
            diff = recent_counter.get(digit, 0) - previous_counter.get(digit, 0)
            position_trend_records.append(
                {"digit": digit, "diff": diff, "position": label}
            )
    position_trend_df = pd.DataFrame(position_trend_records)
    pos_chart = (
        alt.Chart(position_trend_df)
        .mark_bar()
        .encode(
            x=alt.X("digit:N", title="数字"),
            y=alt.Y("diff:Q", title="频次差"),
            column=alt.Column("position:N", title="位置"),
            color=alt.condition(
                "datum.diff>0", alt.value("#2ca02c"), alt.value("#d62728")
            ),
            tooltip=["position", "digit", "diff"],
        )
        .properties(width=160, height=260)
    )
    st.altair_chart(pos_chart, use_container_width=True)
else:
    st.info("样本不足，无法计算近态对比。")

st.caption("冷热分析仅供参考，不构成投注建议。")
