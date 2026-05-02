"""Persistent record of Birthdays — the `birthdays` table interface."""

import calendar as _calendar
from datetime import date
from typing import NamedTuple

import aiosqlite


class Birthday(NamedTuple):
    month: int
    day: int


async def register(
    db: aiosqlite.Connection, user_id: int, month: int, day: int
) -> None:
    await db.execute(
        "INSERT OR REPLACE INTO birthdays (user_id, month, day) VALUES (?, ?, ?)",
        (user_id, month, day),
    )
    await db.commit()


async def remove(db: aiosqlite.Connection, user_id: int) -> bool:
    """True if a row was deleted; False if nothing matched."""
    cursor = await db.execute(
        "DELETE FROM birthdays WHERE user_id = ?", (user_id,)
    )
    await db.commit()
    return cursor.rowcount > 0


async def get(db: aiosqlite.Connection, user_id: int) -> Birthday | None:
    async with db.execute(
        "SELECT month, day FROM birthdays WHERE user_id = ?", (user_id,)
    ) as cursor:
        row = await cursor.fetchone()
    return None if row is None else Birthday(month=row[0], day=row[1])


async def users_with_birthday_on(
    db: aiosqlite.Connection, today: date
) -> list[int]:
    """User IDs whose Birthday falls on `today`; on non-leap Feb-28, also matches Feb-29 entries."""
    feb29_falls_back = (
        today.month == 2 and today.day == 28 and not _calendar.isleap(today.year)
    )
    if feb29_falls_back:
        sql = (
            "SELECT user_id FROM birthdays "
            "WHERE (month = ? AND day = ?) OR (month = 2 AND day = 29)"
        )
    else:
        sql = "SELECT user_id FROM birthdays WHERE month = ? AND day = ?"
    async with db.execute(sql, (today.month, today.day)) as cursor:
        return [row[0] for row in await cursor.fetchall()]
