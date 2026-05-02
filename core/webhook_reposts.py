"""The Webhook-reposts store — persistent record of cleaned-link reposts.

Owns the `webhook_reposts` table interface. Each row tracks one
webhook message that the link embedder posted to replace a user's
original message that contained a tracked URL. Rows live for 90 days
or until the original poster reacts ✅/❌; the TTL rule itself is
shared with the archive (caller passes `before_ts` to
`purge_expired`)."""

from typing import NamedTuple

import aiosqlite


class WebhookRepost(NamedTuple):
    webhook_message_id: int
    channel_id: int
    original_author_id: int
    cleaned_content: str | None
    posted_at: int
    original_message_id: int | None  # NULL on legacy rows written before the column existed


async def record(
    db: aiosqlite.Connection,
    *,
    webhook_message_id: int,
    channel_id: int,
    original_author_id: int,
    cleaned_content: str | None,
    posted_at: int,
    original_message_id: int | None,
) -> None:
    """Insert a tracking row for a freshly-posted webhook repost."""
    await db.execute(
        "INSERT INTO webhook_reposts "
        "(webhook_message_id, channel_id, original_author_id, "
        "cleaned_content, posted_at, original_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            webhook_message_id,
            channel_id,
            original_author_id,
            cleaned_content,
            posted_at,
            original_message_id,
        ),
    )
    await db.commit()


async def get(
    db: aiosqlite.Connection, webhook_message_id: int
) -> WebhookRepost | None:
    async with db.execute(
        "SELECT webhook_message_id, channel_id, original_author_id, "
        "cleaned_content, posted_at, original_message_id "
        "FROM webhook_reposts WHERE webhook_message_id = ?",
        (webhook_message_id,),
    ) as cur:
        row = await cur.fetchone()
    return None if row is None else WebhookRepost(*row)


async def delete(
    db: aiosqlite.Connection, webhook_message_id: int
) -> None:
    """Drop the tracking row. Idempotent — DELETE on a missing row is a
    no-op in SQLite, no exception. Used by the ✅ confirm path, the
    message-already-gone branch, and inside `_finalize_repost`."""
    await db.execute(
        "DELETE FROM webhook_reposts WHERE webhook_message_id = ?",
        (webhook_message_id,),
    )
    await db.commit()


async def purge_expired(
    db: aiosqlite.Connection, *, before_ts: int
) -> int:
    """Delete rows older than `before_ts` (strict `<`). Returns the
    count purged. Caller decides the cutoff — this module doesn't
    own a TTL rule; the canonical 90-day window comes from
    `core.archive.cutoff_ts()`."""
    cursor = await db.execute(
        "DELETE FROM webhook_reposts WHERE posted_at < ?", (before_ts,)
    )
    await db.commit()
    return cursor.rowcount
