from __future__ import annotations

import os

import pytest

from db.connection import query_db

run_live = os.getenv("RUN_DB_TESTS") == "1"


@pytest.mark.skipif(not run_live, reason="set RUN_DB_TESTS=1 to run live DB tests")
def test_select_one():
    rows = query_db("SELECT 1 AS ok")
    assert rows and rows[0]["ok"] == 1


@pytest.mark.skipif(not run_live, reason="set RUN_DB_TESTS=1 to run live DB tests")
def test_parameterised_echo():
    rows = query_db("SELECT :value AS echo", {"value": 42})
    assert rows[0]["echo"] == 42
