from __future__ import annotations

from typing import Optional, Dict, Any

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

DB_URL = "mysql+pymysql://root:sw63828@mysql:3306/lotto_3d?charset=utf8mb4"

_engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    future=True,
)


def get_engine():
    """Return the shared SQLAlchemy engine for the application."""
    return _engine


def query_db(sql: str, params: Optional[Dict[str, Any]] = None):
    """Execute a parameterised SQL statement and return rows or metadata."""
    with _engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        if result.returns_rows:
            return [dict(r._mapping) for r in result]
        return {"rowcount": result.rowcount}
