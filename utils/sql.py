from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple


def make_in_clause(
    column: str, values: Iterable[Any], prefix: str
) -> Tuple[str, Dict[str, Any]]:
    values = list(values)
    if not values:
        return "1=1", {}
    placeholders = []
    params: Dict[str, Any] = {}
    for idx, value in enumerate(values):
        key = f"{prefix}_{idx}"
        placeholders.append(f":{key}")
        params[key] = value
    clause = f"{column} IN ({', '.join(placeholders)})"
    return clause, params


def apply_limit_offset(limit: int, page: int) -> Dict[str, Any]:
    return {"limit": int(limit), "offset": max(0, int(limit) * max(page - 1, 0))}
