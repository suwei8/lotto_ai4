from __future__ import annotations

from typing import Any, Iterable


def make_in_clause(column: str, values: Iterable[Any], prefix: str) -> tuple[str, dict[str, Any]]:
    values = list(values)
    if not values:
        return "1=1", {}
    placeholders = []
    params: dict[str, Any] = {}
    for idx, value in enumerate(values):
        key = f"{prefix}_{idx}"
        placeholders.append(f":{key}")
        params[key] = value
    clause = f"{column} IN ({', '.join(placeholders)})"
    return clause, params


def apply_limit_offset(limit: int, page: int) -> dict[str, Any]:
    return {"limit": int(limit), "offset": max(0, int(limit) * max(page - 1, 0))}
