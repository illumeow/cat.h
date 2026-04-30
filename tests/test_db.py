"""Characterization tests for `db.init_db` and `db._migrate`.

Async because aiosqlite is. We don't want these tests touching the real
`data/bot.db`, so each test gets a fresh tempfile path via pytest's
`tmp_path` fixture and we monkeypatch `db.DATA_DIR` / `db.DB_PATH` for
the duration.

Two flows worth pinning down:

1. `init_db` on an empty filesystem produces the schema the cogs expect
   (every table the bot writes to + the `original_message_id` column the
   link embedder added later).

2. `_migrate` is the project's "no migration framework" answer: it has
   to be safe to re-run on every startup, and it has to upgrade legacy
   databases (that were created before `original_message_id` existed)
   without losing data.
"""

import aiosqlite
import pytest

from core import db


async def _table_columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        return {row[1] for row in await cur.fetchall()}


async def _all_tables(conn: aiosqlite.Connection) -> set[str]:
    async with conn.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ) as cur:
        return {row[0] for row in await cur.fetchall()}


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Point db.DATA_DIR / db.DB_PATH at a tempdir for this test only.
    init_db() uses these module-level constants directly, so this is the
    cleanest way to keep tests off the real data/bot.db file."""
    monkeypatch.setattr(db, "DATA_DIR", tmp_path)
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "bot.db")
    return tmp_path / "bot.db"


# --- init_db: schema shape -------------------------------------------


@pytest.mark.asyncio
async def test_init_db_creates_all_expected_tables(tmp_db):
    conn = await db.init_db()
    try:
        tables = await _all_tables(conn)
    finally:
        await conn.close()
    assert tables == {
        "birthdays",
        "messages",
        "message_edits",
        "attachments",
        "webhook_reposts",
    }


@pytest.mark.asyncio
async def test_init_db_messages_table_has_expected_columns(tmp_db):
    conn = await db.init_db()
    try:
        cols = await _table_columns(conn, "messages")
    finally:
        await conn.close()
    assert {
        "id",
        "channel_id",
        "guild_id",
        "author_id",
        "content",
        "created_at",
        "edited_at",
        "deleted_at",
    } <= cols


@pytest.mark.asyncio
async def test_init_db_webhook_reposts_includes_original_message_id(tmp_db):
    # The whole point of the migration we're characterizing: every fresh
    # DB should have this column from the get-go (it's in _SCHEMA), and
    # legacy DBs get it via _migrate. This test guards the fresh-install
    # path; the migrate tests below guard the legacy path.
    conn = await db.init_db()
    try:
        cols = await _table_columns(conn, "webhook_reposts")
    finally:
        await conn.close()
    assert "original_message_id" in cols


@pytest.mark.asyncio
async def test_init_db_is_idempotent(tmp_db):
    # Running twice over the same file shouldn't error — bot startup
    # always calls init_db() and the file usually exists.
    conn1 = await db.init_db()
    await conn1.close()
    conn2 = await db.init_db()
    try:
        tables = await _all_tables(conn2)
    finally:
        await conn2.close()
    assert "webhook_reposts" in tables


# --- _migrate: legacy upgrade ----------------------------------------


@pytest.mark.asyncio
async def test_migrate_adds_original_message_id_to_legacy_table(tmp_db):
    # Stand up a webhook_reposts table the way it looked *before* the
    # original_message_id column was added, including a row, then run
    # _migrate and verify the column appeared and the row survived.
    legacy = await aiosqlite.connect(tmp_db)
    try:
        await legacy.execute(
            """
            CREATE TABLE webhook_reposts (
                webhook_message_id  INTEGER PRIMARY KEY,
                channel_id          INTEGER NOT NULL,
                original_author_id  INTEGER NOT NULL,
                cleaned_content     TEXT,
                posted_at           INTEGER NOT NULL
            )
            """
        )
        await legacy.execute(
            "INSERT INTO webhook_reposts VALUES (?, ?, ?, ?, ?)",
            (1, 100, 200, "hello", 12345),
        )
        await legacy.commit()
    finally:
        await legacy.close()

    conn = await aiosqlite.connect(tmp_db)
    try:
        await db._migrate(conn)
        await conn.commit()
        cols = await _table_columns(conn, "webhook_reposts")
        async with conn.execute(
            "SELECT webhook_message_id, original_message_id "
            "FROM webhook_reposts WHERE webhook_message_id = 1"
        ) as cur:
            row = await cur.fetchone()
    finally:
        await conn.close()

    assert "original_message_id" in cols
    assert row == (1, None)  # legacy row preserved, new column NULL


@pytest.mark.asyncio
async def test_migrate_is_noop_when_column_already_exists(tmp_db):
    # Idempotency: a freshly init'd DB already has the column, so calling
    # _migrate again must not raise (SQLite errors on ADD COLUMN if it
    # already exists). This test fails loudly if the pragma-check guard
    # in _migrate ever regresses.
    conn = await db.init_db()
    try:
        await db._migrate(conn)  # should be a no-op, not an error
        await db._migrate(conn)  # really, really not an error
        cols = await _table_columns(conn, "webhook_reposts")
    finally:
        await conn.close()
    assert "original_message_id" in cols


@pytest.mark.asyncio
async def test_init_db_on_legacy_file_runs_migration_end_to_end(tmp_db):
    # Simulate the actual upgrade flow: an existing bot DB is on disk,
    # the operator pulls the new code and starts the bot, init_db() runs
    # against the legacy file. The legacy row should still be there with
    # the new column NULL.
    legacy = await aiosqlite.connect(tmp_db)
    try:
        await legacy.execute(
            """
            CREATE TABLE webhook_reposts (
                webhook_message_id  INTEGER PRIMARY KEY,
                channel_id          INTEGER NOT NULL,
                original_author_id  INTEGER NOT NULL,
                cleaned_content     TEXT,
                posted_at           INTEGER NOT NULL
            )
            """
        )
        await legacy.execute(
            "INSERT INTO webhook_reposts VALUES (?, ?, ?, ?, ?)",
            (42, 100, 200, "before-upgrade", 99999),
        )
        await legacy.commit()
    finally:
        await legacy.close()

    conn = await db.init_db()
    try:
        cols = await _table_columns(conn, "webhook_reposts")
        async with conn.execute(
            "SELECT webhook_message_id, cleaned_content, original_message_id "
            "FROM webhook_reposts WHERE webhook_message_id = 42"
        ) as cur:
            row = await cur.fetchone()
    finally:
        await conn.close()

    assert "original_message_id" in cols
    assert row == (42, "before-upgrade", None)
