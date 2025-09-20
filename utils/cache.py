import hashlib
import json

import streamlit as st

from utils.cache_control import get_cache_token


def _make_key(
    sql: str,
    params: dict | None,
    extra: str | None,
    token: str | None,
) -> str:
    blob = json.dumps(
        {
            "sql": sql,
            "params": params or {},
            "extra": extra or "",
            "token": token or "",
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def cached_query(
    run_fn,
    sql: str,
    params: dict | None = None,
    ttl: int = 300,
    *,
    extra_key: str | None = None,
    include_global_token: bool = True,
):
    global_token = get_cache_token() if include_global_token else ""
    key = _make_key(sql, params, extra_key, global_token)

    @st.cache_data(ttl=ttl, show_spinner=False)
    def _do(k: str):
        return run_fn(sql, params)

    return _do(key)
