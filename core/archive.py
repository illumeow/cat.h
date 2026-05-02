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


class ArchivedMessage(NamedTuple):
    id: int
    channel_id: int
    guild_id: int
    author_id: int
    content: str | None
    created_at: int
    edited_at: int | None
    deleted_at: int | None


class Edit(NamedTuple):
    content: str | None
    edited_at: int


class Attachment(NamedTuple):
    id: int
    filename: str
    url: str
    content_type: str | None
    size: int | None
    local_path: str | None
    skipped_reason: str | None


class DeletedListing(NamedTuple):
    id: int
    channel_id: int
    author_id: int
    content: str | None
    edited_at: int | None
    deleted_at: int


class PendingAttachment(NamedTuple):
    id: int
    filename: str
    url: str
    size: int | None


async def get(
    db: aiosqlite.Connection, message_id: int
) -> ArchivedMessage | None:
    async with db.execute(
        "SELECT id, channel_id, guild_id, author_id, content, "
        "created_at, edited_at, deleted_at FROM messages WHERE id = ?",
        (message_id,),
    ) as cur:
        row = await cur.fetchone()
    return None if row is None else ArchivedMessage(*row)


async def get_edits(
    db: aiosqlite.Connection, message_id: int
) -> list[Edit]:
    """Edit history for a message, newest first."""
    async with db.execute(
        "SELECT content, edited_at FROM message_edits "
        "WHERE message_id = ? ORDER BY edited_at DESC",
        (message_id,),
    ) as cur:
        rows = await cur.fetchall()
    return [Edit(content=c, edited_at=e) for c, e in rows]


async def get_attachments(
    db: aiosqlite.Connection,
    message_id: int,
    *,
    restrict_to_db_ids: set[int] | None = None,
) -> list[Attachment]:
    sql = (
        "SELECT id, filename, url, content_type, size, local_path, "
        "skipped_reason FROM attachments WHERE message_id = ?"
    )
    params: list[object] = [message_id]
    if restrict_to_db_ids is not None:
        if not restrict_to_db_ids:
            return []
        placeholders = ",".join(["?"] * len(restrict_to_db_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(restrict_to_db_ids)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [Attachment(*row) for row in rows]


async def list_deleted(
    db: aiosqlite.Connection,
    *,
    user_id: int | None = None,
    channel_id: int | None = None,
    limit: int = 10,
) -> list[DeletedListing]:
    sql = (
        "SELECT id, channel_id, author_id, content, edited_at, deleted_at "
        "FROM messages WHERE deleted_at IS NOT NULL"
    )
    params: list[object] = []
    if user_id is not None:
        sql += " AND author_id = ?"
        params.append(user_id)
    if channel_id is not None:
        sql += " AND channel_id = ?"
        params.append(channel_id)
    sql += " ORDER BY deleted_at DESC LIMIT ?"
    params.append(limit)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [DeletedListing(*row) for row in rows]


async def pending_attachments(
    db: aiosqlite.Connection,
    message_id: int,
    *,
    restrict_to_db_ids: set[int] | None = None,
) -> list[PendingAttachment]:
    """Attachments not yet downloaded and not yet skipped — the rows
    `download_pending` will act on."""
    sql = (
        "SELECT id, filename, url, size FROM attachments "
        "WHERE message_id = ? "
        "AND local_path IS NULL AND skipped_reason IS NULL"
    )
    params: list[object] = [message_id]
    if restrict_to_db_ids is not None:
        if not restrict_to_db_ids:
            return []
        placeholders = ",".join(["?"] * len(restrict_to_db_ids))
        sql += f" AND id IN ({placeholders})"
        params.extend(restrict_to_db_ids)
    async with db.execute(sql, params) as cur:
        rows = await cur.fetchall()
    return [PendingAttachment(*row) for row in rows]
