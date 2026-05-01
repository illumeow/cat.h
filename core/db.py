from pathlib import Path

import aiosqlite

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "bot.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS birthdays (
    user_id INTEGER PRIMARY KEY,
    month   INTEGER NOT NULL,
    day     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY,
    channel_id  INTEGER NOT NULL,
    guild_id    INTEGER NOT NULL,
    author_id   INTEGER NOT NULL,
    content     TEXT,
    created_at  INTEGER NOT NULL,
    edited_at   INTEGER,
    deleted_at  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_messages_channel_deleted
    ON messages(channel_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_messages_author_deleted
    ON messages(author_id, deleted_at);
CREATE INDEX IF NOT EXISTS idx_messages_created
    ON messages(created_at);

CREATE TABLE IF NOT EXISTS message_edits (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    content     TEXT,
    edited_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edits_message ON message_edits(message_id);

CREATE TABLE IF NOT EXISTS attachments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id      INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    url             TEXT NOT NULL,
    content_type    TEXT,
    size            INTEGER,
    local_path      TEXT,
    skipped_reason  TEXT
);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);

CREATE TABLE IF NOT EXISTS webhook_reposts (
    webhook_message_id   INTEGER PRIMARY KEY,
    channel_id           INTEGER NOT NULL,
    original_author_id   INTEGER NOT NULL,
    cleaned_content      TEXT,
    posted_at            INTEGER NOT NULL,
    -- ID of the user's original message (the one the bot deleted). Used
    -- to surface a /archive-show-able ID in the mod-log "Deleted" notice
    -- when the original poster reacts ❌. Nullable: rows written before
    -- this column was added have no value.
    original_message_id  INTEGER
);
CREATE INDEX IF NOT EXISTS idx_reposts_posted ON webhook_reposts(posted_at);
"""


async def _migrate(conn: aiosqlite.Connection) -> None:
    """Idempotent column additions for already-deployed databases. SQLite
    has no ADD COLUMN IF NOT EXISTS, so we read the table pragma first."""
    async with conn.execute("PRAGMA table_info(webhook_reposts)") as cur:
        cols = {row[1] for row in await cur.fetchall()}
    if "original_message_id" not in cols:
        await conn.execute(
            "ALTER TABLE webhook_reposts ADD COLUMN original_message_id INTEGER"
        )


async def init_db() -> aiosqlite.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    # WAL gives readers + the single writer better concurrency; foreign keys
    # are off by default in SQLite and need to be enabled per-connection.
    await conn.execute("PRAGMA journal_mode = WAL;")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.executescript(_SCHEMA)
    await _migrate(conn)
    await conn.commit()
    return conn
