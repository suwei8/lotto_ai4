from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from sqlalchemy import text

from db.connection import get_engine


@dataclass(slots=True)
class ExpandedScheme:
    playtype_id: int
    playtype_name: str
    numbers: str


def _coerce_numbers(numbers: object) -> str:
    if numbers is None:
        return ""
    if isinstance(numbers, str):
        return numbers
    if isinstance(numbers, Sequence):
        if numbers and isinstance(numbers[0], Sequence):
            parts: list[str] = []
            for group in numbers:  # type: ignore[arg-type]
                parts.append(",".join(str(int(num)) for num in group if num is not None))
            return "|".join(parts)
        return ",".join(str(int(num)) for num in numbers if num is not None)
    return str(numbers)


_POS_SUFFIXES = ["百位", "十位", "个位"]
_SPLIT_PLAYTYPES = {3003, 3004, 3005}


def expand_scheme(
    playtype_id: int, playtype_name: str, numbers: object
) -> Iterable[ExpandedScheme]:
    number_string = _coerce_numbers(numbers)
    if playtype_id in _SPLIT_PLAYTYPES and "|" in number_string:
        parts = number_string.split("|")
        if len(parts) == 3:
            for idx, part in enumerate(parts, start=1):
                suffix = _POS_SUFFIXES[idx - 1]
                child_id = int(f"{playtype_id}{idx}")
                yield ExpandedScheme(
                    playtype_id=child_id,
                    playtype_name=f"{playtype_name}-{suffix}",
                    numbers=part,
                )
            return
    yield ExpandedScheme(
        playtype_id=playtype_id,
        playtype_name=playtype_name,
        numbers=number_string,
    )


def upsert_expert_info(user_id: int, nick_name: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO expert_info (user_id, nick_name)
                VALUES (:user_id, :nick_name)
                ON DUPLICATE KEY UPDATE nick_name = VALUES(nick_name)
                """
            ),
            {"user_id": user_id, "nick_name": nick_name or ""},
        )


def upsert_prediction(
    *,
    user_id: int,
    issue_name: str,
    lottery_id: int,
    scheme: ExpandedScheme,
) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        existing = (
            conn.execute(
                text(
                    """
                SELECT id, numbers
                FROM expert_predictions
                WHERE user_id = :user_id AND issue_name = :issue_name AND playtype_id = :playtype_id
                """
                ),
                {
                    "user_id": user_id,
                    "issue_name": issue_name,
                    "playtype_id": scheme.playtype_id,
                },
            )
            .mappings()
            .first()
        )
        if existing:
            if (existing.get("numbers") or "") == scheme.numbers:
                return
            conn.execute(
                text(
                    """
                    UPDATE expert_predictions
                    SET numbers = :numbers
                    WHERE id = :id
                    """
                ),
                {"numbers": scheme.numbers, "id": existing["id"]},
            )
            return
        conn.execute(
            text(
                """
                INSERT INTO expert_predictions (
                    user_id, issue_name, lottery_id, playtype_id, numbers
                ) VALUES (:user_id, :issue_name, :lottery_id, :playtype_id, :numbers)
                """
            ),
            {
                "user_id": user_id,
                "issue_name": issue_name,
                "lottery_id": lottery_id,
                "playtype_id": scheme.playtype_id,
                "numbers": scheme.numbers,
            },
        )
