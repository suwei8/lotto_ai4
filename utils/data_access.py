from __future__ import annotations

import logging
from typing import Iterable, Sequence

import pandas as pd

from db.connection import query_db
from utils.cache import cached_query

logger = logging.getLogger(__name__)


def fetch_recent_issues(limit: int = 200) -> list[str]:
    marker = ""
    try:
        latest = query_db("SELECT MAX(issue_name) AS max_issue FROM expert_predictions")
        marker = (latest[0]["max_issue"] or "") if latest else ""
    except Exception:
        marker = ""

    sql = f"""
    /* latest_prediction: {marker} */
    SELECT issue_name
    FROM (
        SELECT issue_name, open_time
        FROM lottery_results
        UNION ALL
        SELECT issue_name, NULL AS open_time
        FROM expert_predictions
    ) AS merged
    GROUP BY issue_name
    ORDER BY issue_name DESC, COALESCE(MAX(open_time), '1970-01-01') DESC
    LIMIT :limit
    """
    try:
        rows = cached_query(
            query_db,
            sql,
            params={"limit": int(limit)},
            ttl=300,
            extra_key=marker,
        )
    except Exception:
        logger.exception("fetch_recent_issues failed (limit=%s)", limit)
        return []
    return [row["issue_name"] for row in rows]


def fetch_latest_issue() -> str | None:
    issues = fetch_recent_issues(limit=1)
    return issues[0] if issues else None


def default_issue_window(
    recent: list[str] | None = None, window: int = 50
) -> tuple[str | None, str | None]:
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
        logger.exception("fetch_playtypes failed")
        return pd.DataFrame(columns=["playtype_id", "playtype_name"])
    return pd.DataFrame(rows)


def playtype_options() -> list[tuple[str, str]]:
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
        logger.exception("fetch_issue_dataframe failed (limit=%s)", limit)
        return pd.DataFrame(columns=["issue_name", "open_code", "open_time"])
    return pd.DataFrame(rows)


def fetch_playtype_name_map() -> dict[str, str]:
    frame = fetch_playtypes()
    if frame.empty:
        return {}
    return {str(row.playtype_id): row.playtype_name for row in frame.itertuples()}


def playtype_name_to_id_map() -> dict[str, str]:
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
        logger.exception("fetch_experts failed (limit=%s)", limit)
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
        logger.exception("fetch_playtypes_for_issue failed (issue=%s)", issue)
        return pd.DataFrame(columns=["playtype_id", "playtype_name"])
    return pd.DataFrame(rows)


def fetch_predicted_issues(limit: int = 200) -> list[str]:
    sql = """
    SELECT DISTINCT issue_name
    FROM expert_predictions
    ORDER BY issue_name DESC
    LIMIT :limit
    """
    try:
        rows = cached_query(query_db, sql, params={"limit": int(limit)}, ttl=300)
    except Exception:
        logger.exception("fetch_predicted_issues failed (limit=%s)", limit)
        return []
    return [row["issue_name"] for row in rows]


def fetch_lottery_info(issue: str, ttl: int | None = 120) -> dict[str, object] | None:
    sql = """
    SELECT issue_name, open_code, `sum`, span, odd_even_ratio, big_small_ratio, open_time
    FROM lottery_results
    WHERE issue_name = :issue
    LIMIT 1
    """
    try:
        if ttl is None:
            rows = query_db(sql, {"issue": issue})
        else:
            rows = cached_query(query_db, sql, params={"issue": issue}, ttl=ttl)
    except Exception:
        logger.exception("fetch_lottery_info failed (issue=%s)", issue)
        return None
    return rows[0] if rows else None


def fetch_lottery_infos(
    issues: Sequence[str], ttl: int | None = 120
) -> dict[str, dict[str, object]]:
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
        if ttl is None:
            rows = query_db(sql, params)
        else:
            rows = cached_query(query_db, sql, params=params, ttl=ttl)
    except Exception:
        logger.exception("fetch_lottery_infos failed (issues=%s)", list(issues))
        return {}
    return {row["issue_name"]: row for row in rows}


def fetch_predictions(
    issues: Sequence[str],
    playtype_ids: Iterable[int] | None = None,
    user_ids: Iterable[int] | None = None,
    columns: Sequence[str] | None = None,
    *,
    limit: int | None = None,
    order_by: str = "issue_name DESC",
    ttl: int | None = 300,
) -> pd.DataFrame:
    default_columns = ["issue_name", "playtype_id", "user_id", "numbers"]
    if not issues:
        return pd.DataFrame(columns=columns or default_columns)

    select_columns = list(columns) if columns else default_columns
    allowed_columns = {"issue_name", "playtype_id", "user_id", "numbers"}
    invalid_columns = set(select_columns) - allowed_columns
    if invalid_columns:
        raise ValueError(f"Unsupported columns requested: {sorted(invalid_columns)}")

    issue_values = list(dict.fromkeys(issues))
    issue_placeholders = ", ".join([":issue_" + str(idx) for idx in range(len(issue_values))])
    params: dict[str, object] = {f"issue_{idx}": issue for idx, issue in enumerate(issue_values)}
    conditions = [f"issue_name IN ({issue_placeholders})"]

    if playtype_ids is not None:
        playtype_list = [int(pid) for pid in playtype_ids]
        if not playtype_list:
            return pd.DataFrame(columns=select_columns)
        pt_placeholders = ", ".join([":pt_" + str(idx) for idx in range(len(playtype_list))])
        conditions.append(f"playtype_id IN ({pt_placeholders})")
        params.update({f"pt_{idx}": pid for idx, pid in enumerate(playtype_list)})

    if user_ids is not None:
        user_list = [int(uid) for uid in user_ids]
        if not user_list:
            return pd.DataFrame(columns=select_columns)
        user_placeholders = ", ".join([":uid_" + str(idx) for idx in range(len(user_list))])
        conditions.append(f"user_id IN ({user_placeholders})")
        params.update({f"uid_{idx}": uid for idx, uid in enumerate(user_list)})

    limit_clause = ""
    if limit is not None:
        limit_clause = "LIMIT :limit"
        params["limit"] = int(limit)

    sql = """
    SELECT {select_clause}
    FROM expert_predictions
    WHERE {conditions}
    ORDER BY {order_by}
    {limit_clause}
    """.format(
        select_clause=", ".join(select_columns),
        conditions=" AND ".join(conditions),
        order_by=order_by,
        limit_clause=limit_clause,
    )

    try:
        if ttl is None:
            rows = query_db(sql, params)
        else:
            rows = cached_query(query_db, sql, params=params, ttl=ttl)
    except Exception:
        logger.exception(
            "fetch_predictions failed (issues=%s, playtype_ids=%s, user_ids=%s, limit=%s)",
            issue_values,
            playtype_ids,
            user_ids,
            limit,
        )
        return pd.DataFrame(columns=select_columns)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=select_columns)
    return frame.reindex(columns=select_columns)
