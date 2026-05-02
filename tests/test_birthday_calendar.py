"""Tests for the Birthday calendar — the `birthdays` table interface."""

from datetime import date

import pytest

from core import birthday_calendar
from core.birthday_calendar import Birthday


# --- register --------------------------------------------------------


@pytest.mark.asyncio
async def test_register_inserts_new_row(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=42, month=7, day=15)
    async with fresh_db.execute(
        "SELECT month, day FROM birthdays WHERE user_id = ?", (42,)
    ) as cur:
        row = await cur.fetchone()
    assert row == (7, 15)


@pytest.mark.asyncio
async def test_register_upserts_existing_row(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=42, month=7, day=15)
    await birthday_calendar.register(fresh_db, user_id=42, month=12, day=25)
    async with fresh_db.execute(
        "SELECT month, day FROM birthdays WHERE user_id = ?", (42,)
    ) as cur:
        row = await cur.fetchone()
    assert row == (12, 25)


# --- remove ----------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_returns_true_when_row_existed(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=42, month=7, day=15)
    assert await birthday_calendar.remove(fresh_db, user_id=42) is True
    async with fresh_db.execute(
        "SELECT 1 FROM birthdays WHERE user_id = ?", (42,)
    ) as cur:
        assert await cur.fetchone() is None


@pytest.mark.asyncio
async def test_remove_returns_false_when_no_row(fresh_db):
    assert await birthday_calendar.remove(fresh_db, user_id=999) is False


# --- get -------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_returns_birthday_when_registered(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=42, month=7, day=15)
    bday = await birthday_calendar.get(fresh_db, user_id=42)
    assert bday == Birthday(month=7, day=15)


@pytest.mark.asyncio
async def test_get_returns_none_when_not_registered(fresh_db):
    assert await birthday_calendar.get(fresh_db, user_id=999) is None


# --- users_with_birthday_on (the leap-year rule) ---------------------


@pytest.mark.asyncio
async def test_users_with_birthday_on_normal_day(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=1, month=7, day=15)
    await birthday_calendar.register(fresh_db, user_id=2, month=7, day=16)
    await birthday_calendar.register(fresh_db, user_id=3, month=7, day=15)
    ids = await birthday_calendar.users_with_birthday_on(fresh_db, date(2025, 7, 15))
    assert sorted(ids) == [1, 3]


@pytest.mark.asyncio
async def test_users_with_birthday_on_leap_year_feb_29(fresh_db):
    """On a real Feb-29 (leap year), Feb-29 entries fire directly."""
    await birthday_calendar.register(fresh_db, user_id=1, month=2, day=29)
    await birthday_calendar.register(fresh_db, user_id=2, month=2, day=28)
    ids = await birthday_calendar.users_with_birthday_on(fresh_db, date(2024, 2, 29))
    assert ids == [1]


@pytest.mark.asyncio
async def test_users_with_birthday_on_non_leap_feb_28_includes_feb_29_users(fresh_db):
    """The rule: Feb-29 users get their announcement on Feb-28 in non-leap years."""
    await birthday_calendar.register(fresh_db, user_id=1, month=2, day=28)
    await birthday_calendar.register(fresh_db, user_id=2, month=2, day=29)
    await birthday_calendar.register(fresh_db, user_id=3, month=3, day=1)
    ids = await birthday_calendar.users_with_birthday_on(fresh_db, date(2025, 2, 28))
    assert sorted(ids) == [1, 2]


@pytest.mark.asyncio
async def test_users_with_birthday_on_leap_year_feb_28_excludes_feb_29_users(fresh_db):
    """Control: in a leap year, Feb-28 lookup does NOT pull in Feb-29 entries
    (those will fire on the 29th)."""
    await birthday_calendar.register(fresh_db, user_id=1, month=2, day=28)
    await birthday_calendar.register(fresh_db, user_id=2, month=2, day=29)
    ids = await birthday_calendar.users_with_birthday_on(fresh_db, date(2024, 2, 28))
    assert ids == [1]


@pytest.mark.asyncio
async def test_users_with_birthday_on_returns_empty_when_no_matches(fresh_db):
    await birthday_calendar.register(fresh_db, user_id=1, month=7, day=15)
    ids = await birthday_calendar.users_with_birthday_on(fresh_db, date(2025, 12, 25))
    assert ids == []
