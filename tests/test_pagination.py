from __future__ import annotations

import pandas as pd

from utils.pagination import paginate


def test_paginate_first_page():
    df = pd.DataFrame({"value": list(range(100))})
    subset, page, pages = paginate(df, page_size=10, page=1)
    assert page == 1
    assert pages == 10
    assert subset.iloc[0]["value"] == 0
    assert len(subset) == 10


def test_paginate_last_page_partial():
    df = pd.DataFrame({"value": list(range(95))})
    subset, page, pages = paginate(df, page_size=20, page=5)
    assert pages == 5
    assert page == 5
    assert len(subset) == 15
    assert subset.iloc[-1]["value"] == 94
