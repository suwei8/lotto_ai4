import math

import pandas as pd
import streamlit as st


def paginate(df: pd.DataFrame, page_size: int = 50, key: str = "pager", page: int | None = None):
    total = len(df)
    pages = max(1, math.ceil(total / page_size))
    if page is None:
        page = int(st.number_input("Page", min_value=1, max_value=pages, value=1, step=1, key=key))
    else:
        page = max(1, min(page, pages))
    start = (page - 1) * page_size
    end = start + page_size
    return df.iloc[start:end], page, pages
