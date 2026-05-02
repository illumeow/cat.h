"""The Archive — persistent record of every message the bot sees in
non-excluded channels, plus the on-disk attachment vault under
`data/attachments/<message_id>/`. Owns the `messages`,
`message_edits`, and `attachments` tables and the 90-day retention
window."""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple

import aiosqlite

log = logging.getLogger(__name__)

ATTACHMENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB
TTL_DAYS = 90


class AttachmentSpec(NamedTuple):
    """Input shape for `record` — one row's worth of attachment metadata
    at archival time, before we've tried to download bytes."""

    filename: str
    url: str
    content_type: str | None
    size: int | None


def cutoff_ts() -> int:
    """Unix timestamp marking the start of the retention window.
    Anything with `created_at < cutoff_ts()` is older than TTL_DAYS."""
    return int(
        (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)).timestamp()
    )


async def record(
    db: aiosqlite.Connection,
    *,
    message_id: int,
    channel_id: int,
    guild_id: int,
    author_id: int,
    content: str | None,
    created_at: int,
    attachments: list[AttachmentSpec],
) -> None:
    """Insert a new message row plus its attachment children. Uses
    INSERT OR IGNORE on the parent so duplicate gateway events don't
    error; attachment rows are inserted unconditionally — call once
    per message."""
    await db.execute(
        "INSERT OR IGNORE INTO messages "
        "(id, channel_id, guild_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (message_id, channel_id, guild_id, author_id, content, created_at),
    )
    for att in attachments:
        await db.execute(
            "INSERT INTO attachments "
            "(message_id, filename, url, content_type, size) "
            "VALUES (?, ?, ?, ?, ?)",
            (message_id, att.filename, att.url, att.content_type, att.size),
        )
    await db.commit()


async def record_edit(
    db: aiosqlite.Connection,
    *,
    message_id: int,
    prior_content: str | None,
    new_content: str | None,
    edited_at: int,
) -> None:
    """Append `prior_content` to the edit history and update the
    messages row's content + edited_at. Single transaction."""
    await db.execute(
        "INSERT INTO message_edits (message_id, content, edited_at) "
        "VALUES (?, ?, ?)",
        (message_id, prior_content, edited_at),
    )
    await db.execute(
        "UPDATE messages SET content = ?, edited_at = ? WHERE id = ?",
        (new_content, edited_at, message_id),
    )
    await db.commit()


async def mark_deleted(
    db: aiosqlite.Connection, *, message_id: int, deleted_at: int
) -> bool:
    """Atomically stamp `deleted_at` iff the row exists and the
    column is NULL. Returns True if a row transitioned; False on
    no-op (row missing or already deleted)."""
    cursor = await db.execute(
        "UPDATE messages SET deleted_at = ? "
        "WHERE id = ? AND deleted_at IS NULL",
        (deleted_at, message_id),
    )
    await db.commit()
    return cursor.rowcount > 0
