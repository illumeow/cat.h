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
    assert await archive.mark_deleted(fresh_db, message_id=5, deleted_at=3000) is True

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
    assert await archive.mark_deleted(fresh_db, message_id=6, deleted_at=3000) is True
    assert await archive.mark_deleted(fresh_db, message_id=6, deleted_at=4000) is False

    async with fresh_db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (6,)
    ) as cur:
        (deleted_at,) = await cur.fetchone()
    assert deleted_at == 3000  # preserved


@pytest.mark.asyncio
async def test_mark_deleted_unknown_message_returns_false(fresh_db):
    from core import archive

    assert await archive.mark_deleted(fresh_db, message_id=999_999, deleted_at=1234) is False


def test_cutoff_ts_is_roughly_ttl_days_ago():
    from core import archive

    now = int(time.time())
    cutoff = archive.cutoff_ts()
    expected = now - archive.TTL_DAYS * 86400
    # ±60s slack for the call straddling a clock tick.
    assert abs(cutoff - expected) < 60


@pytest.mark.asyncio
async def test_get_returns_archived_message(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=10,
        channel_id=11,
        guild_id=111,
        author_id=222,
        content="hi",
        created_at=500,
        attachments=[],
    )

    msg = await archive.get(fresh_db, 10)
    assert msg == archive.ArchivedMessage(
        id=10,
        channel_id=11,
        guild_id=111,
        author_id=222,
        content="hi",
        created_at=500,
        edited_at=None,
        deleted_at=None,
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(fresh_db):
    from core import archive

    assert await archive.get(fresh_db, 99_999) is None


@pytest.mark.asyncio
async def test_get_edits_newest_first(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=20,
        channel_id=1,
        guild_id=1,
        author_id=1,
        content="v1",
        created_at=0,
        attachments=[],
    )
    await archive.record_edit(
        fresh_db, message_id=20, prior_content="v1", new_content="v2",
        edited_at=100,
    )
    await archive.record_edit(
        fresh_db, message_id=20, prior_content="v2", new_content="v3",
        edited_at=200,
    )

    edits = await archive.get_edits(fresh_db, 20)
    assert edits == [
        archive.Edit(content="v2", edited_at=200),
        archive.Edit(content="v1", edited_at=100),
    ]


@pytest.mark.asyncio
async def test_get_attachments_full_and_restricted(fresh_db):
    from core import archive

    await archive.record(
        fresh_db,
        message_id=30,
        channel_id=1,
        guild_id=1,
        author_id=1,
        content=None,
        created_at=0,
        attachments=[
            archive.AttachmentSpec("a.png", "https://x/a", "image/png", 100),
            archive.AttachmentSpec("b.png", "https://x/b", "image/png", 200),
            archive.AttachmentSpec("c.png", "https://x/c", "image/png", 300),
        ],
    )

    all_atts = await archive.get_attachments(fresh_db, 30)
    assert [a.filename for a in all_atts] == ["a.png", "b.png", "c.png"]
    a_id, b_id, _c_id = [a.id for a in all_atts]

    only_ab = await archive.get_attachments(
        fresh_db, 30, restrict_to_db_ids={a_id, b_id}
    )
    assert {a.filename for a in only_ab} == {"a.png", "b.png"}

    empty = await archive.get_attachments(
        fresh_db, 30, restrict_to_db_ids=set()
    )
    assert empty == []


@pytest.mark.asyncio
async def test_list_deleted_filters_and_limit(fresh_db):
    """Each filter combination (user, channel, both, neither) plus
    ordering by deleted_at DESC and the limit."""
    from core import archive

    rows = [
        # (id, channel, author, deleted_at)
        (1, 100, 10, 1000),
        (2, 100, 11, 2000),
        (3, 200, 10, 3000),
        (4, 200, 11, 4000),
        (5, 100, 10, 5000),
    ]
    for mid, ch, au, dt in rows:
        await archive.record(
            fresh_db, message_id=mid, channel_id=ch, guild_id=1,
            author_id=au, content=f"m{mid}", created_at=0, attachments=[],
        )
        await archive.mark_deleted(
            fresh_db, message_id=mid, deleted_at=dt
        )
    # Insert one undeleted row to confirm it never shows up.
    await archive.record(
        fresh_db, message_id=6, channel_id=100, guild_id=1,
        author_id=10, content="alive", created_at=0, attachments=[],
    )

    no_filter = await archive.list_deleted(fresh_db, limit=10)
    assert [r.id for r in no_filter] == [5, 4, 3, 2, 1]

    user_only = await archive.list_deleted(fresh_db, user_id=10)
    assert [r.id for r in user_only] == [5, 3, 1]

    chan_only = await archive.list_deleted(fresh_db, channel_id=100)
    assert [r.id for r in chan_only] == [5, 2, 1]

    both = await archive.list_deleted(fresh_db, user_id=10, channel_id=100)
    assert [r.id for r in both] == [5, 1]

    capped = await archive.list_deleted(fresh_db, limit=2)
    assert [r.id for r in capped] == [5, 4]


@pytest.mark.asyncio
async def test_pending_attachments_filters_saved_and_skipped(fresh_db):
    """Only rows where local_path IS NULL AND skipped_reason IS NULL
    are pending; rows updated to either state must drop out."""
    from core import archive

    await archive.record(
        fresh_db, message_id=40, channel_id=1, guild_id=1, author_id=1,
        content=None, created_at=0,
        attachments=[
            archive.AttachmentSpec("p.txt", "https://x/p", None, 10),
            archive.AttachmentSpec("s.txt", "https://x/s", None, 10),
            archive.AttachmentSpec("k.txt", "https://x/k", None, 10),
        ],
    )

    await fresh_db.execute(
        "UPDATE attachments SET local_path = ? WHERE filename = ?",
        ("/tmp/saved", "s.txt"),
    )
    await fresh_db.execute(
        "UPDATE attachments SET skipped_reason = ? WHERE filename = ?",
        ("too_large", "k.txt"),
    )
    await fresh_db.commit()

    pending = await archive.pending_attachments(fresh_db, 40)
    assert [p.filename for p in pending] == ["p.txt"]


@pytest.mark.asyncio
async def test_pending_attachments_restrict_empty_short_circuits(fresh_db):
    from core import archive

    await archive.record(
        fresh_db, message_id=41, channel_id=1, guild_id=1, author_id=1,
        content=None, created_at=0,
        attachments=[archive.AttachmentSpec("x.txt", "https://x/x", None, 10)],
    )
    assert await archive.pending_attachments(
        fresh_db, 41, restrict_to_db_ids=set()
    ) == []
