from __future__ import annotations

import logging
from collections import Counter, defaultdict
from typing import Sequence

from db.connection import query_db
from utils.cache import cached_query
from utils.numbers import normalize_code, parse_tokens
from utils.sql import make_in_clause

logger = logging.getLogger(__name__)


def build_prediction_distribution(
    issue: str,
    playtype_ids: Sequence[int],
    *,
    ttl: int = 60,
) -> list[dict[str, str]]:
    """Aggregate expert predictions into fallback distributions by playtype."""
    ids = [int(pid) for pid in playtype_ids if int(pid)]
    if not issue or not ids:
        return []

    clause, params = make_in_clause("playtype_id", ids, "pt")
    params.update({"issue": issue})
    sql = f"""
        SELECT playtype_id, numbers
        FROM expert_predictions
        WHERE issue_name = :issue AND {clause}
    """
    try:
        rows = cached_query(query_db, sql, params=params, ttl=ttl)
    except Exception:
        logger.exception(
            "build_prediction_distribution failed (issue=%s, playtypes=%s)", issue, ids
        )
        rows = []
    if not rows:
        return []

    buckets: defaultdict[int, Counter[str]] = defaultdict(Counter)
    for row in rows:
        pid = int(row.get("playtype_id", 0) or 0)
        if not pid:
            continue
        for token in parse_tokens(row.get("numbers")):
            normalized = normalize_code(token)
            if not normalized:
                continue
            for digit in normalized:
                buckets[pid][digit] += 1

    fallback_rows: list[dict[str, str]] = []
    for pid in ids:
        counter = buckets.get(pid)
        if not counter:
            continue
        ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
        digits = [digit for digit, _ in ordered]
        if digits:
            fallback_rows.append({"playtype_id": pid, "num": ",".join(digits)})
    return fallback_rows
