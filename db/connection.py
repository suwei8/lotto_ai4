"""Database connection utilities for the lotto_ai4 project.

This module centralises database connectivity logic so that the rest of the
application can work with a single, well tested API.  It uses SQLAlchemy's
engine abstraction to manage pooled connections to the MySQL database and
exposes a helper for executing read-only queries in a safe, parameterised
manner.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result, URL
from sqlalchemy.exc import OperationalError, SQLAlchemyError


class DatabaseConfigurationError(RuntimeError):
    """Raised when the database configuration is incomplete."""


@lru_cache(maxsize=1)
def get_db_engine() -> Engine:
    """Create (or retrieve) a cached SQLAlchemy engine for MySQL.

    The connection settings are read from environment variables so they can be
    customised per deployment.  Defaults are provided to make local development
    straightforward, while still allowing overrides in production.

    Environment variables:
        DB_HOST: MySQL host. Defaults to ``localhost``.
        DB_PORT: MySQL port. Defaults to ``3306``.
        DB_USER: Database username. Defaults to ``root``.
        DB_PASS: Database password. Defaults to an empty string.
        DB_NAME: Database name. Defaults to ``lotto_3d``.

    Returns:
        Engine: A SQLAlchemy engine configured for read-only operations.
    """

    host = os.getenv("DB_HOST", "localhost")
    port_raw = os.getenv("DB_PORT", "3306")
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASS", "")
    database = os.getenv("DB_NAME", "lotto_3d")

    if not user:
        raise DatabaseConfigurationError("DB_USER must be provided")

    try:
        port = int(port_raw)
    except (TypeError, ValueError) as exc:
        raise DatabaseConfigurationError("DB_PORT must be a valid integer") from exc

    url = URL.create(
        "mysql+pymysql",
        username=user,
        password=password or None,
        host=host,
        port=port,
        database=database,
    )

    # ``init_command`` runs for every new connection and sets the session to be
    # read-only. This guards against accidental data modification and enforces
    # the read-only default required by the project.
    connect_args = {
        "charset": "utf8mb4",
        "init_command": "SET SESSION TRANSACTION READ ONLY",
    }

    try:
        engine = create_engine(url, pool_pre_ping=True, connect_args=connect_args)
    except SQLAlchemyError as exc:  # pragma: no cover - failure is propagated
        raise DatabaseConfigurationError("Failed to create database engine") from exc

    return engine


def query_db(sql: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """Execute a parameterised, read-only SQL query.

    Args:
        sql: A SQL statement that must represent a ``SELECT`` query.
        params: Parameter dictionary passed to the SQL statement.  If omitted,
            an empty mapping is used so that SQLAlchemy can still treat the
            execution as parameterised.

    Returns:
        A list of dictionaries where each dictionary represents a row.

    Raises:
        ValueError: If the statement is not a ``SELECT`` query.
        SQLAlchemyError: If there is an error executing the query.
    """

    if not sql:
        raise ValueError("SQL query must not be empty")

    # Enforce read-only access by ensuring the query starts with SELECT.
    if not sql.strip().lower().startswith("select"):
        raise ValueError("Only SELECT queries are permitted in query_db")

    engine = get_db_engine()
    compiled_sql = text(sql)
    bound_params = params or {}

    try:
        with engine.connect() as connection:
            result: Result = connection.execute(compiled_sql, bound_params)
            rows = [dict(row._mapping) for row in result.fetchall()]
    except OperationalError as exc:
        # Re-raise operational errors with the original context so callers can
        # decide how to handle the failure (e.g. retry, surface a message, etc.).
        raise OperationalError(sql, bound_params, exc.orig) from exc

    return rows


__all__ = ["get_db_engine", "query_db", "DatabaseConfigurationError"]
