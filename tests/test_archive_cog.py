"""Cog-level tests for the archive cog.

These tests construct a real `ArchiveCog` instance against an in-memory
DB and a SimpleNamespace stand-in for `bot`. We don't go through Discord
— slash command bodies are reached via `cog.command_name.callback` and
listeners are invoked directly with hand-built payload objects.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import make_bot_stub


@pytest.mark.asyncio
async def test_archive_get_closes_files_on_unexpected_exception(
    fresh_db, no_task_loops, monkeypatch, tmp_path
):
    """If `interaction.followup.send` raises an exception type other
    than discord.HTTPException after we've constructed discord.File
    objects, those file handles still need to be closed. The current
    code (`cogs/archive.py:639-653`) only closes on HTTPException;
    other exception types leak the open files.
    """
    from cogs.archive import ArchiveCog

    # Real on-disk file so `Path(local_path).exists()` is True without
    # patching pathlib.
    real_file = tmp_path / "test.txt"
    real_file.write_text("content")

    msg_id = 99999
    await fresh_db.execute(
        "INSERT INTO messages "
        "(id, channel_id, guild_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, 1, 2, 3, "hi", 0),
    )
    await fresh_db.execute(
        "INSERT INTO attachments "
        "(message_id, filename, url, content_type, size, local_path) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, "test.txt", "https://example/x", None, 7, str(real_file)),
    )
    await fresh_db.commit()

    bot = SimpleNamespace(db=fresh_db)
    cog = ArchiveCog(bot)

    # Track every discord.File constructed inside archive_get.
    file_instances: list = []

    def fake_file(*args, **kwargs):
        m = MagicMock()
        file_instances.append(m)
        return m

    monkeypatch.setattr("cogs.archive.discord.File", fake_file)

    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    # Non-HTTPException — the bug is that this leaks the files.
    interaction.followup.send = AsyncMock(
        side_effect=RuntimeError("simulated transport error")
    )

    with pytest.raises(RuntimeError):
        await cog.archive_get.callback(cog, interaction, str(msg_id))

    assert len(file_instances) == 1, (
        f"expected 1 file constructed, got {len(file_instances)}"
    )
    for f in file_instances:
        f.close.assert_called()


@pytest.mark.asyncio
async def test_suppressed_delete_defers_deleted_at_and_skips_mod_log(
    fresh_db, no_task_loops, monkeypatch
):
    """Recent fix: when a delete is bot-initiated (link embedder
    rewriting a tracked URL), the archive must NOT stamp
    `messages.deleted_at` here. The webhook repost is now the user's
    "live" message; the link embedder will stamp deleted_at when the
    user actually presses ❌ on the repost. Same delete should also
    skip the mod-log "Deleted" notice (the bot caused it, not the
    user).
    """
    from cogs.archive import ArchiveCog

    msg_id = 42
    await fresh_db.execute(
        "INSERT INTO messages "
        "(id, channel_id, guild_id, author_id, content, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (msg_id, 200, 100, 5, "original", 0),
    )
    await fresh_db.commit()

    bot = make_bot_stub(db=fresh_db)
    bot.suppressed_deletes.add(msg_id)  # marked as bot-initiated
    cog = ArchiveCog(bot)

    post_deleted = AsyncMock()
    monkeypatch.setattr("cogs.archive.mod_log.post_deleted", post_deleted)

    payload = MagicMock()
    payload.message_id = msg_id
    payload.channel_id = 200

    await cog.on_raw_message_delete(payload)

    async with fresh_db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (msg_id,)
    ) as cur:
        row = await cur.fetchone()
    assert row is not None and row[0] is None, (
        "deleted_at must stay NULL on suppressed deletes — the link "
        "embedder will stamp it when ❌ runs"
    )
    post_deleted.assert_not_called()
    # The suppressed_deletes set is consumed (discarded) on read so a
    # later, separate delete event for the same ID would NOT be treated
    # as suppressed.
    assert msg_id not in bot.suppressed_deletes
