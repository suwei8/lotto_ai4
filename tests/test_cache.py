from __future__ import annotations

from types import SimpleNamespace

import pytest

from utils import cache


@pytest.fixture(autouse=True)
def patch_cache(monkeypatch):
    store = {}

    def fake_cache_data(ttl=None, show_spinner=False):
        def decorator(func):
            def wrapper(key: str):
                if key not in store:
                    store[key] = func(key)
                return store[key]

            return wrapper

        return decorator

    monkeypatch.setattr(cache, "st", SimpleNamespace(cache_data=fake_cache_data))


def test_cached_query_hits_once():
    calls = {"count": 0}

    def runner(sql: str, params: dict | None):
        calls["count"] += 1
        return params["value"]

    result1 = cache.cached_query(runner, "SELECT :value", {"value": 1})
    result2 = cache.cached_query(runner, "SELECT :value", {"value": 1})

    assert result1 == result2 == 1
    assert calls["count"] == 1


def test_cached_query_cache_miss_on_params_change():
    calls = {"count": 0}

    def runner(sql: str, params: dict | None):
        calls["count"] += 1
        return params["value"]

    first = cache.cached_query(runner, "SELECT :value", {"value": 1})
    second = cache.cached_query(runner, "SELECT :value", {"value": 2})

    assert first == 1
    assert second == 2
    assert calls["count"] == 2
