import hashlib
import json

import streamlit as st


def _make_key(sql: str, params: dict | None) -> str:
    blob = json.dumps(
        {"sql": sql, "params": params or {}}, sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cached_query(run_fn, sql: str, params: dict | None = None, ttl: int = 300):
    key = _make_key(sql, params)

    @st.cache_data(ttl=ttl, show_spinner=False)
    def _do(k: str):
        return run_fn(sql, params)

    return _do(key)
