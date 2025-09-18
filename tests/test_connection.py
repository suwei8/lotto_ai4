"""Basic integration tests for database access and utilities."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from db.connection import get_db_engine
from utils.pagination import paginate


@pytest.mark.integration
def test_database_connection():
    """Ensure that a database connection can be established.

    The test attempts to run a trivial ``SELECT 1`` against the configured
    database.  When executed in environments without access to MySQL the test is
    skipped rather than failed so that local development without a database
    remains possible.
    """

    engine = get_db_engine()

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            assert result.scalar() == 1
    except OperationalError as exc:  # pragma: no cover - depends on env setup
        pytest.skip(f"Database unavailable: {exc}")


@pytest.mark.parametrize(
    "page,page_size,expected_limit,expected_offset",
    [
        (1, 10, 10, 0),
        (2, 25, 25, 25),
        (5, 50, 50, 200),
    ],
)
def test_paginate(page: int, page_size: int, expected_limit: int, expected_offset: int):
    """Verify pagination calculations."""

    pagination = paginate(page=page, page_size=page_size)

    assert pagination.limit == expected_limit
    assert pagination.offset == expected_offset
    assert pagination.page == page
    assert pagination.page_size == page_size


def test_paginate_invalid_arguments():
    """Invalid pagination arguments should raise :class:`ValueError`."""

    with pytest.raises(ValueError):
        paginate(0, 10)
    with pytest.raises(ValueError):
        paginate(1, 0)
