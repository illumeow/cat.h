"""Cog-level tests for the link embedder.

Constructs a real LinkEmbedderCog wired to an in-memory DB and a
SimpleNamespace bot. Listeners and the shared `_process_message`
helper are invoked directly with hand-built mocks of the discord.py
objects.
"""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from tests.conftest import make_bot_stub


def _build_text_message(*, msg_id: int, channel_id: int, guild_id: int,
                        author_id: int, content: str) -> MagicMock:
    """A MagicMock shaped like the `discord.Message` attributes the
    link embedder reads. Caller can override individual attrs after."""
    msg = MagicMock()
    msg.id = msg_id
    msg.guild = MagicMock()
    msg.guild.id = guild_id
    msg.guild.is_mock = True  # tag for clarity
    msg.author.id = author_id
    msg.author.display_name = "tester"
    msg.author.display_avatar.url = "https://example/avatar.png"
    msg.webhook_id = None
    msg.content = content
    # `isinstance(message.channel, discord.TextChannel)` must be True for
    # the cog's parent-channel resolution to pick the right branch.
    msg.channel = MagicMock(spec=discord.TextChannel)
    msg.channel.id = channel_id
    msg.channel.parent = None
    return msg


@pytest.mark.asyncio
async def test_process_message_inserts_repost_row_before_deleting_original(
    fresh_db, monkeypatch
):
    """Crash-safety: if the bot dies between `message.delete()` and the
    `INSERT INTO webhook_reposts`, the webhook repost is in chat with no
    DB row, and the ❌ flow silently no-ops forever. The fix is to
    INSERT (and commit) BEFORE the delete, so a crash window leaves at
    worst a duplicate visible message — recoverable — rather than a
    permanently-orphaned webhook.

    Verified by hooking `message.delete()` to read the DB at the moment
    delete runs; the row must already be there.
    """
    from cogs.link_embedder import LinkEmbedderCog

    bot = make_bot_stub(db=fresh_db)
    cog = LinkEmbedderCog(bot)
    cog._http = None  # cog_load isn't called under tests

    msg = _build_text_message(
        msg_id=42,
        channel_id=200,
        guild_id=100,
        author_id=5,
        content="https://www.threads.com/@u/post/abc?xmt=foo",
    )

    sent = MagicMock()
    sent.id = 9999
    sent.add_reaction = AsyncMock()

    webhook = MagicMock()
    webhook.send = AsyncMock(return_value=sent)
    monkeypatch.setattr(cog, "_get_webhook", AsyncMock(return_value=webhook))
    monkeypatch.setattr(cog, "_build_preview_embeds", AsyncMock(return_value=[]))

    # Capture whether the webhook_reposts row exists at the moment
    # `message.delete()` is invoked. If the cog deletes first then
    # inserts, the row won't be there yet → assertion below fails.
    observed: dict = {}

    async def check_db_then_delete():
        async with bot.db.execute(
            "SELECT webhook_message_id FROM webhook_reposts "
            "WHERE webhook_message_id = ?",
            (sent.id,),
        ) as cur:
            row = await cur.fetchone()
        observed["row_present_at_delete_time"] = row is not None

    msg.delete = AsyncMock(side_effect=check_db_then_delete)

    await cog._process_message(msg)

    assert observed["row_present_at_delete_time"], (
        "webhook_reposts row should already exist when message.delete() "
        "is called — otherwise a crash between the two steps leaves a "
        "tracked-but-unrecorded webhook in chat."
    )


@pytest.mark.asyncio
async def test_react_x_finalizes_before_deleting_webhook(fresh_db, monkeypatch):
    """The ❌ reaction path must run `_finalize_repost` (which DELETEs
    the webhook_reposts row) BEFORE calling `message.delete()` on the
    webhook. Reasoning: that delete fires a MESSAGE_DELETE event which
    the cog's on_raw_message_delete listener also handles; if the row
    were still there, the listener would call `_finalize_repost` again
    and post the mod-log "Deleted" notice twice. The webhook_reposts
    row's existence is the single point of coordination — once it's
    gone, the second handler no-ops cleanly.
    """
    from cogs.link_embedder import LinkEmbedderCog

    bot = make_bot_stub(db=fresh_db)
    cog = LinkEmbedderCog(bot)
    cog._http = None

    # Pre-existing webhook repost + its original message
    await fresh_db.execute(
        "INSERT INTO messages "
        "(id, channel_id, guild_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (42, 200, 100, 5, "original", 0),
    )
    await fresh_db.execute(
        "INSERT INTO webhook_reposts "
        "(webhook_message_id, channel_id, original_author_id, "
        "cleaned_content, posted_at, original_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (5000, 200, 5, "cleaned", 0, 42),
    )
    await fresh_db.commit()

    monkeypatch.setattr(
        "cogs.link_embedder.mod_log.post_deleted", AsyncMock()
    )

    # Hook webhook.delete() to inspect the row at delete time
    webhook_msg = MagicMock()
    observed: dict = {}

    async def check_db_then_delete():
        async with bot.db.execute(
            "SELECT * FROM webhook_reposts WHERE webhook_message_id = ?",
            (5000,),
        ) as cur:
            observed["row"] = await cur.fetchone()

    webhook_msg.delete = AsyncMock(side_effect=check_db_then_delete)

    channel = MagicMock(spec=discord.TextChannel)
    channel.fetch_message = AsyncMock(return_value=webhook_msg)
    bot.get_channel = MagicMock(return_value=channel)

    payload = MagicMock()
    payload.guild_id = 100
    payload.user_id = 5  # original author
    payload.message_id = 5000
    payload.emoji = "\N{CROSS MARK}"  # cog calls str(payload.emoji)

    await cog.on_raw_reaction_add(payload)

    webhook_msg.delete.assert_awaited_once()
    assert observed["row"] is None, (
        "_finalize_repost must DELETE the webhook_reposts row before "
        "message.delete() runs, so the resulting MESSAGE_DELETE event "
        "finds no row and on_raw_message_delete no-ops."
    )


@pytest.mark.asyncio
async def test_finalize_repost_stamps_deleted_at_on_original(
    fresh_db, monkeypatch
):
    """The deleted_at-deferral fix relies on _finalize_repost stamping
    `messages.deleted_at` on the original at exactly the moment of the
    intentional removal (❌ press or manual delete). Pin that down."""
    from cogs.link_embedder import LinkEmbedderCog

    bot = make_bot_stub(db=fresh_db)
    cog = LinkEmbedderCog(bot)

    # Original archived; deleted_at NULL (archive deferred it via
    # the suppressed_deletes handshake at rewrite time).
    await fresh_db.execute(
        "INSERT INTO messages "
        "(id, channel_id, guild_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (42, 200, 100, 5, "original", 0),
    )
    await fresh_db.execute(
        "INSERT INTO webhook_reposts "
        "(webhook_message_id, channel_id, original_author_id, "
        "cleaned_content, posted_at, original_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (5000, 200, 5, "cleaned", 0, 42),
    )
    await fresh_db.commit()

    monkeypatch.setattr(
        "cogs.link_embedder.mod_log.post_deleted", AsyncMock()
    )

    await cog._finalize_repost(
        webhook_message_id=5000,
        channel_id=200,
        original_author_id=5,
        cleaned_content="cleaned",
        original_message_id=42,
    )

    async with bot.db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (42,)
    ) as cur:
        row = await cur.fetchone()
    assert row is not None and row[0] is not None, (
        "deleted_at should be stamped on the original at finalize time"
    )
