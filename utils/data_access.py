from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from db.connection import query_db
from utils.cache import cached_query


def fetch_recent_issues(limit: int = 200) -> List[str]:
    sql = """
    SELECT issue_name
    FROM lottery_results
    ORDER BY open_time DESC, issue_name DESC
    LIMIT :limit
    """
    try:
        rows = cached_query(query_db, sql, params={"limit": int(limit)}, ttl=300)
    except Exception:
        return []
    return [row["issue_name"] for row in rows]


def fetch_latest_issue() -> Optional[str]:
    issues = fetch_recent_issues(limit=1)
    return issues[0] if issues else None


def default_issue_window(
    recent: Optional[List[str]] = None, window: int = 50
) -> Tuple[Optional[str], Optional[str]]:
    issues = recent if recent is not None else fetch_recent_issues(limit=max(window, 1))
    if not issues:
        return None, None
    start_index = min(len(issues) - 1, window - 1)
    return issues[start_index], issues[0]


def fetch_playtypes() -> pd.DataFrame:
    sql = """
    SELECT playtype_id, playtype_name
    FROM playtype_dict
    ORDER BY playtype_id
    """
    try:
        rows = cached_query(query_db, sql, params=None, ttl=1800)
    except Exception:
        return pd.DataFrame(columns=["playtype_id", "playtype_name"])
    return pd.DataFrame(rows)


def playtype_options() -> List[Tuple[str, str]]:
    frame = fetch_playtypes()
    if frame.empty:
        return []
    return [(str(row.playtype_id), row.playtype_name) for row in frame.itertuples()]


def fetch_issue_dataframe(limit: int = 200) -> pd.DataFrame:
    sql = """
    SELECT issue_name, open_code, open_time
    FROM lottery_results
    ORDER BY open_time DESC, issue_name DESC
    LIMIT :limit
    """
    try:
        rows = cached_query(query_db, sql, params={"limit": int(limit)}, ttl=300)
    except Exception:
        return pd.DataFrame(columns=["issue_name", "open_code", "open_time"])
    return pd.DataFrame(rows)


def fetch_playtype_name_map() -> Dict[str, str]:
    frame = fetch_playtypes()
    if frame.empty:
        return {}
    return {str(row.playtype_id): row.playtype_name for row in frame.itertuples()}


def playtype_name_to_id_map() -> Dict[str, str]:
    frame = fetch_playtypes()
    if frame.empty:
        return {}
    return {row.playtype_name: str(row.playtype_id) for row in frame.itertuples()}


def fetch_experts(limit: int = 500) -> pd.DataFrame:
    sql = """
    SELECT user_id, nick_name
    FROM expert_info
    ORDER BY nick_name IS NULL, nick_name
    LIMIT :limit
    """
    try:
        rows = cached_query(query_db, sql, params={"limit": int(limit)}, ttl=600)
    except Exception:
        return pd.DataFrame(columns=["user_id", "nick_name"])
    return pd.DataFrame(rows)


def fetch_playtypes_for_issue(issue: str) -> pd.DataFrame:
    sql = """
    SELECT DISTINCT ep.playtype_id, pd.playtype_name
    FROM expert_predictions ep
    JOIN playtype_dict pd ON pd.playtype_id = ep.playtype_id
    WHERE ep.issue_name = :issue
    ORDER BY ep.playtype_id
    """
    try:
        rows = cached_query(query_db, sql, params={"issue": issue}, ttl=300)
    except Exception:
        return pd.DataFrame(columns=["playtype_id", "playtype_name"])
    return pd.DataFrame(rows)


def fetch_predicted_issues(limit: int = 200) -> List[str]:
    sql = """
    SELECT DISTINCT issue_name
    FROM expert_predictions
    ORDER BY issue_name DESC
    LIMIT :limit
    """
    try:
        rows = cached_query(query_db, sql, params={"limit": int(limit)}, ttl=300)
    except Exception:
        return []
    return [row["issue_name"] for row in rows]


def fetch_lottery_info(issue: str) -> Optional[Dict[str, object]]:
    sql = """
    SELECT issue_name, open_code, `sum`, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    WHERE issue_name = :issue
    LIMIT 1
    """
    try:
        rows = cached_query(query_db, sql, params={"issue": issue}, ttl=120)
    except Exception:
        return None
    return rows[0] if rows else None


def fetch_lottery_infos(issues: Sequence[str]) -> Dict[str, Dict[str, object]]:
    if not issues:
        return {}
    placeholders = ", ".join([":issue_" + str(idx) for idx in range(len(issues))])
    sql = f"""
    SELECT issue_name, open_code, `sum`, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    WHERE issue_name IN ({placeholders})
    """
    params = {f"issue_{idx}": issue for idx, issue in enumerate(issues)}
    try:
        rows = cached_query(query_db, sql, params=params, ttl=120)
    except Exception:
        return {}
    return {row["issue_name"]: row for row in rows}


def fetch_predictions(
    issues: Sequence[str],
    playtype_ids: Optional[Iterable[int]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=["issue_name", "playtype_id", "user_id", "numbers"])

    issue_placeholders = ", ".join([":issue_" + str(idx) for idx in range(len(issues))])
    params: Dict[str, object] = {
        f"issue_{idx}": issue for idx, issue in enumerate(issues)
    }

    conditions = [f"issue_name IN ({issue_placeholders})"]

    if playtype_ids is not None:
        playtype_ids = list(playtype_ids)
        if playtype_ids:
            pt_placeholders = ", ".join(
                [":pt_" + str(idx) for idx in range(len(playtype_ids))]
            )
            conditions.append(f"playtype_id IN ({pt_placeholders})")
            params.update({f"pt_{idx}": pt for idx, pt in enumerate(playtype_ids)})

    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT :limit"
        params["limit"] = int(limit)

    sql = """
    SELECT issue_name, playtype_id, user_id, numbers
    FROM expert_predictions
    WHERE {conditions}
    ORDER BY issue_name DESC
    {limit_clause}
    """
    sql = sql.format(conditions=" AND ".join(conditions), limit_clause=limit_clause)

    try:
        rows = cached_query(query_db, sql, params=params, ttl=300)
    except Exception:
        return pd.DataFrame(columns=["issue_name", "playtype_id", "user_id", "numbers"])
    return pd.DataFrame(rows)
