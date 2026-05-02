"""Unit tests for `core/archive.py` — the Archive store + vault."""

import time

import pytest


@pytest.mark.asyncio
async def test_record_inserts_message_and_attachments(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=1,
        channel_id=10,
        guild_id=100,
        author_id=42,
        content="hello",
        created_at=1000,
        attachments=[
            archive.AttachmentSpec(
                filename="a.png",
                url="https://cdn/a.png",
                content_type="image/png",
                size=12345,
            ),
        ],
    )

    async with fresh_db.execute(
        "SELECT channel_id, guild_id, author_id, content, created_at "
        "FROM messages WHERE id = ?",
        (1,),
    ) as cur:
        row = await cur.fetchone()
    assert row == (10, 100, 42, "hello", 1000)

    async with fresh_db.execute(
        "SELECT filename, url, content_type, size FROM attachments "
        "WHERE message_id = ?",
        (1,),
    ) as cur:
        atts = await cur.fetchall()
    assert atts == [("a.png", "https://cdn/a.png", "image/png", 12345)]


@pytest.mark.asyncio
async def test_record_no_attachments(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=2,
        channel_id=10,
        guild_id=100,
        author_id=42,
        content="plain",
        created_at=1000,
        attachments=[],
    )

    async with fresh_db.execute(
        "SELECT COUNT(*) FROM attachments WHERE message_id = ?", (2,)
    ) as cur:
        (n,) = await cur.fetchone()
    assert n == 0


@pytest.mark.asyncio
async def test_record_is_idempotent_on_message_row(fresh_db):
    """Duplicate gateway events shouldn't error; INSERT OR IGNORE on
    the parent row preserves the original. (Attachments would still
    re-insert — callers are expected to call once per message; this
    test only locks the parent-row idempotency.)"""
    from core import archive

    for _ in range(2):
        await archive.record(
            fresh_db,
            message_id=3,
            channel_id=10,
            guild_id=100,
            author_id=42,
            content="first",
            created_at=1000,
            attachments=[],
        )

    async with fresh_db.execute(
        "SELECT content FROM messages WHERE id = ?", (3,)
    ) as cur:
        (content,) = await cur.fetchone()
    assert content == "first"


@pytest.mark.asyncio
async def test_record_edit_appends_history_and_updates_message(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=4,
        channel_id=10,
        guild_id=100,
        author_id=42,
        content="v1",
        created_at=1000,
        attachments=[],
    )
    await archive.record_edit(
        fresh_db,
        message_id=4,
        prior_content="v1",
        new_content="v2",
        edited_at=2000,
    )

    async with fresh_db.execute(
        "SELECT content, edited_at FROM messages WHERE id = ?", (4,)
    ) as cur:
        row = await cur.fetchone()
    assert row == ("v2", 2000)

    async with fresh_db.execute(
        "SELECT content, edited_at FROM message_edits WHERE message_id = ?",
        (4,),
    ) as cur:
        edits = await cur.fetchall()
    assert edits == [("v1", 2000)]


@pytest.mark.asyncio
async def test_mark_deleted_first_call_returns_true(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=5,
        channel_id=10,
        guild_id=100,
        author_id=42,
        content="x",
        created_at=1000,
        attachments=[],
    )
    assert await archive.mark_deleted(fresh_db, 5, 3000) is True

    async with fresh_db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (5,)
    ) as cur:
        (deleted_at,) = await cur.fetchone()
    assert deleted_at == 3000


@pytest.mark.asyncio
async def test_mark_deleted_second_call_returns_false(fresh_db):
    """Idempotency guard: once deleted_at is set, a second call must
    not overwrite it and must return False so callers can short-circuit."""
    from core import archive

    await archive.record(
        fresh_db,
        message_id=6,
        channel_id=10,
        guild_id=100,
        author_id=42,
        content="x",
        created_at=1000,
        attachments=[],
    )
    assert await archive.mark_deleted(fresh_db, 6, 3000) is True
    assert await archive.mark_deleted(fresh_db, 6, 4000) is False

    async with fresh_db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (6,)
    ) as cur:
        (deleted_at,) = await cur.fetchone()
    assert deleted_at == 3000  # preserved


@pytest.mark.asyncio
async def test_mark_deleted_unknown_message_returns_false(fresh_db):
    from core import archive

    assert await archive.mark_deleted(fresh_db, 999_999, 1234) is False


def test_cutoff_ts_is_roughly_ttl_days_ago():
    from core import archive

    now = int(time.time())
    cutoff = archive.cutoff_ts()
    expected = now - archive.TTL_DAYS * 86400
    # ±60s slack for the call straddling a clock tick.
    assert abs(cutoff - expected) < 60
