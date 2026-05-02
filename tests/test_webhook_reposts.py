"""Unit tests for `core/webhook_reposts.py` — the Webhook-reposts store."""

import pytest


@pytest.mark.asyncio
async def test_record_inserts_row(fresh_db):
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db,
        webhook_message_id=5000,
        channel_id=200,
        original_author_id=42,
        cleaned_content="cleaned text",
        posted_at=1000,
        original_message_id=42,
    )

    async with fresh_db.execute(
        "SELECT webhook_message_id, channel_id, original_author_id, "
        "cleaned_content, posted_at, original_message_id "
        "FROM webhook_reposts WHERE webhook_message_id = ?",
        (5000,),
    ) as cur:
        row = await cur.fetchone()
    assert row == (5000, 200, 42, "cleaned text", 1000, 42)


@pytest.mark.asyncio
async def test_record_accepts_null_original_message_id(fresh_db):
    """Legacy rows written before the original_message_id column existed
    have NULL there. New writes can also use None — exercise that path."""
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db,
        webhook_message_id=5001,
        channel_id=200,
        original_author_id=42,
        cleaned_content="x",
        posted_at=1000,
        original_message_id=None,
    )

    async with fresh_db.execute(
        "SELECT original_message_id FROM webhook_reposts "
        "WHERE webhook_message_id = ?",
        (5001,),
    ) as cur:
        (omid,) = await cur.fetchone()
    assert omid is None


@pytest.mark.asyncio
async def test_get_returns_named_tuple(fresh_db):
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db,
        webhook_message_id=6000,
        channel_id=300,
        original_author_id=99,
        cleaned_content="hello",
        posted_at=2000,
        original_message_id=12345,
    )

    repost = await webhook_reposts.get(fresh_db, 6000)
    assert repost == webhook_reposts.WebhookRepost(
        webhook_message_id=6000,
        channel_id=300,
        original_author_id=99,
        cleaned_content="hello",
        posted_at=2000,
        original_message_id=12345,
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(fresh_db):
    from core import webhook_reposts

    assert await webhook_reposts.get(fresh_db, 999_999) is None


@pytest.mark.asyncio
async def test_delete_removes_row(fresh_db):
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db,
        webhook_message_id=7000,
        channel_id=1,
        original_author_id=1,
        cleaned_content="x",
        posted_at=0,
        original_message_id=None,
    )

    await webhook_reposts.delete(fresh_db, 7000)
    assert await webhook_reposts.get(fresh_db, 7000) is None


@pytest.mark.asyncio
async def test_delete_unknown_id_is_noop(fresh_db):
    """delete() of a non-existent webhook_message_id should not raise."""
    from core import webhook_reposts

    await webhook_reposts.delete(fresh_db, 999_999)
    # Just confirming no exception; nothing to assert beyond that.


@pytest.mark.asyncio
async def test_purge_expired_drops_old_keeps_fresh(fresh_db):
    """Anything with `posted_at < before_ts` is purged; equal-or-greater
    survives."""
    from core import webhook_reposts

    # Old: posted_at=100, cutoff=500 → purged
    await webhook_reposts.record(
        fresh_db, webhook_message_id=8000, channel_id=1, original_author_id=1,
        cleaned_content="old", posted_at=100, original_message_id=None,
    )
    # Fresh: posted_at=1000, cutoff=500 → kept
    await webhook_reposts.record(
        fresh_db, webhook_message_id=8001, channel_id=1, original_author_id=1,
        cleaned_content="fresh", posted_at=1000, original_message_id=None,
    )

    purged = await webhook_reposts.purge_expired(fresh_db, before_ts=500)
    assert purged == 1
    assert await webhook_reposts.get(fresh_db, 8000) is None
    assert await webhook_reposts.get(fresh_db, 8001) is not None


@pytest.mark.asyncio
async def test_purge_expired_returns_zero_when_nothing_old(fresh_db):
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db, webhook_message_id=8002, channel_id=1, original_author_id=1,
        cleaned_content="x", posted_at=1000, original_message_id=None,
    )
    assert await webhook_reposts.purge_expired(fresh_db, before_ts=500) == 0


@pytest.mark.asyncio
async def test_purge_expired_boundary_is_strict_less_than(fresh_db):
    """posted_at exactly equal to cutoff must NOT be purged (DELETE uses
    `< ?`, not `<= ?`). Pin this so a future tweak to the comparator
    doesn't silently shorten retention by one second."""
    from core import webhook_reposts

    await webhook_reposts.record(
        fresh_db, webhook_message_id=8003, channel_id=1, original_author_id=1,
        cleaned_content="boundary", posted_at=500, original_message_id=None,
    )
    purged = await webhook_reposts.purge_expired(fresh_db, before_ts=500)
    assert purged == 0
    assert await webhook_reposts.get(fresh_db, 8003) is not None
