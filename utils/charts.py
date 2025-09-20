from __future__ import annotations

from typing import Iterable, Optional

import altair as alt
import pandas as pd


def render_digit_frequency_chart(
    freq_df: pd.DataFrame,
    *,
    digit_column: str = "数字",
    count_column: str = "被推荐次数",
    hit_digits: Optional[Iterable[str]] = None,
    height: Optional[int] = None,
    width: Optional[int] = None,
    tooltip_columns: Optional[Sequence[str]] = None,
) -> Optional[alt.Chart]:
    if freq_df is None or freq_df.empty:
        return None
    chart_df = freq_df.copy()
    chart_df[digit_column] = chart_df[digit_column].astype(str)
    if hit_digits is not None:
        hit_set = {str(d) for d in hit_digits}
        chart_df["命中状态"] = chart_df[digit_column].apply(
            lambda digit: "命中" if digit in hit_set else "未命中"
        )
        color = alt.Color(
            "命中状态:N",
            title="命中状态",
            scale=alt.Scale(domain=["命中", "未命中"], range=["#1f77b4", "#d62728"]),
        )
    else:
        color = alt.value("#1f77b4")

    tooltip_fields = [digit_column, count_column]
    if "命中状态" in chart_df.columns and "命中状态" not in tooltip_fields:
        tooltip_fields.append("命中状态")
    if tooltip_columns:
        for col in tooltip_columns:
            if col not in tooltip_fields:
                tooltip_fields.append(col)

    base = (
        alt.Chart(chart_df)
        .mark_bar()
        .encode(
            y=alt.Y(f"{digit_column}:N", sort="-x", axis=alt.Axis(labelFontSize=13)),
            x=alt.X(f"{count_column}:Q", title=count_column),
            color=color,
            tooltip=tooltip_fields,
        )
    )
    if width is not None:
        base = base.properties(width=width)
    if height is not None:
        base = base.properties(height=height)
    else:
        base = base.properties(height=max(320, 28 * len(chart_df)))

    text = (
        alt.Chart(chart_df)
        .mark_text(align="left", baseline="middle", dx=4, color="#333")
        .encode(
            y=alt.Y(f"{digit_column}:N", sort="-x"),
            x=alt.X(f"{count_column}:Q"),
            text=f"{count_column}:Q",
        )
    )
    return base + text
