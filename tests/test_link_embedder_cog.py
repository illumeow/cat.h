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

    from core.webhook_reposts import WebhookRepost

    await cog._finalize_repost(
        WebhookRepost(
            webhook_message_id=5000,
            channel_id=200,
            original_author_id=5,
            cleaned_content="cleaned",
            posted_at=0,
            original_message_id=42,
        )
    )

    async with bot.db.execute(
        "SELECT deleted_at FROM messages WHERE id = ?", (42,)
    ) as cur:
        row = await cur.fetchone()
    assert row is not None and row[0] is not None, (
        "deleted_at should be stamped on the original at finalize time"
    )


# --- _build_preview_embeds: filter out anti-bot challenge pages ------


@pytest.mark.asyncio
async def test_build_preview_embeds_skips_cloudflare_challenge_page(
    fresh_db, monkeypatch
):
    """When the preview sidecar lands on a Cloudflare "Just a moment..."
    challenge page (Dcard sits behind one of these), it returns metadata
    with the challenge title and empty description/image. Rendering an
    embed titled "Just a moment..." is worse than rendering no embed —
    it actively misleads. The cog should recognize the pattern and skip
    those URLs."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()  # any non-None — _fetch_preview is mocked below

    # Force PREVIEW_SERVICE_URL to a non-empty value so the early-return
    # in _build_preview_embeds doesn't short-circuit (the env var is read
    # at module load time and may be empty in the test env).
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    # Sidecar response that looks exactly like Cloudflare's basic JS
    # challenge: a title, no description, no image.
    challenge_meta = {
        "platform": "dcard",
        "url": "https://www.dcard.tw/f/ntu/p/1",
        "title": "Just a moment...",
        "description": "",
        "image": "",
        "video": None,
        "siteName": "Dcard",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=challenge_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.dcard.tw/f/ntu/p/1"]
    )
    assert embeds == [], (
        "embed should be suppressed when the only metadata we got back "
        "looks like an anti-bot challenge page"
    )


@pytest.mark.asyncio
async def test_process_message_dcard_url_skips_preview_and_wrapping(
    fresh_db, monkeypatch
):
    """Dcard sits behind a Cloudflare tier we can't reliably bypass, so
    custom embeds are off for that platform. The URL still gets cleaned
    in the body (cid stripped) and the message still gets reposted by
    the webhook — we just don't ask the sidecar about it and we don't
    wrap the URL in <…>, so Discord's native auto-embed has a chance
    to render whatever it can.
    """
    from cogs.link_embedder import LinkEmbedderCog

    bot = make_bot_stub(db=fresh_db)
    cog = LinkEmbedderCog(bot)
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    fetch_calls: list[str] = []

    async def fake_fetch(url: str):
        fetch_calls.append(url)
        return None

    monkeypatch.setattr(cog, "_fetch_preview", fake_fetch)

    msg = _build_text_message(
        msg_id=42,
        channel_id=200,
        guild_id=100,
        author_id=5,
        content=(
            "check https://www.dcard.tw/f/ntu/p/261398533"
            "?cid=eeb65574-0784-49d8-b298-15b4ca089da2"
        ),
    )

    sent = MagicMock()
    sent.id = 9999
    sent.add_reaction = AsyncMock()
    webhook = MagicMock()
    webhook.send = AsyncMock(return_value=sent)
    monkeypatch.setattr(cog, "_get_webhook", AsyncMock(return_value=webhook))

    msg.delete = AsyncMock()

    await cog._process_message(msg)

    # Sidecar must not be hit for Dcard URLs.
    assert fetch_calls == [], (
        f"Dcard URLs should bypass the preview sidecar; got calls: {fetch_calls}"
    )

    webhook.send.assert_awaited_once()
    body = webhook.send.call_args.kwargs.get("content")
    # Cleaned URL is in the body, with cid stripped.
    assert "https://www.dcard.tw/f/ntu/p/261398533" in body
    assert "cid=" not in body
    # And critically, NOT wrapped in <…> — we want Discord's native
    # auto-embed to be free to try.
    assert "<https://www.dcard.tw/" not in body
    # No custom embeds attached.
    embeds_kwarg = webhook.send.call_args.kwargs.get("embeds")
    assert not embeds_kwarg, f"expected no embeds, got {embeds_kwarg!r}"


@pytest.mark.asyncio
async def test_build_preview_embeds_dedupes_duplicate_urls(
    fresh_db, monkeypatch
):
    """If the same URL appears twice in a message (literally repeated,
    or two URLs that clean to the same canonical form), the sidecar
    must be hit at most once and at most one embed should come back —
    otherwise the webhook send renders two identical previews
    side-by-side, and we burn a redundant browser round-trip."""
    from cogs.link_embedder import LinkEmbedderCog

    bot = make_bot_stub(db=fresh_db)
    cog = LinkEmbedderCog(bot)
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    fetch_calls: list[str] = []

    async def fake_fetch(url: str):
        fetch_calls.append(url)
        return {
            "platform": "threads",
            "url": url,
            "title": "Real post",
            "description": "Some content",
            "image": "https://example/i.jpg",
            "video": None,
            "siteName": "Threads",
        }

    monkeypatch.setattr(cog, "_fetch_preview", fake_fetch)

    duplicate = "https://threads.com/@u/post/abc"
    embeds = await cog._build_preview_embeds([duplicate, duplicate, duplicate])

    assert fetch_calls == [duplicate], (
        f"sidecar should be hit once per unique URL; got {fetch_calls}"
    )
    assert len(embeds) == 1, (
        f"duplicates should collapse to one embed; got {len(embeds)}"
    )


@pytest.mark.asyncio
async def test_build_preview_embeds_keeps_real_page_with_challenge_word(
    fresh_db, monkeypatch
):
    """Defends against an over-eager filter: if a real page happens to
    contain "Cloudflare" or "Just a moment" in its title BUT also has a
    real description or image, we still render the embed."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    real_page = {
        "platform": "threads",
        "url": "https://threads.com/x",
        "title": "Just a moment of silence — a meditation guide",
        "description": "Some real content describing the post.",
        "image": "https://example/img.jpg",
        "video": None,
        "siteName": "Threads",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=real_page)
    )

    embeds = await cog._build_preview_embeds(["https://threads.com/x"])
    assert len(embeds) == 1, (
        "real page with description/image should render even if title "
        "happens to share words with a challenge page"
    )


# --- _build_preview_embeds: Threads avatar fallback → thumbnail -------


@pytest.mark.asyncio
async def test_build_preview_embeds_threads_avatar_fallback_uses_thumbnail(
    fresh_db, monkeypatch
):
    """A Threads post with no media: the page's og:image is the poster's
    avatar, and Threads signals this by setting twitter:card='summary'
    (vs 'summary_large_image' when real media is present). The avatar
    must render as a thumbnail inset, not as the full-width hero —
    otherwise a tiny portrait dominates an otherwise text-only embed."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    avatar_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX0y9JlFc95",
        "title": "Janet Kuo (@janetkuo) on Threads",
        "description": "想大聲宣佈，今天正式升 L7 Senior Staff SWE",
        "image": "https://example/avatar.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary",
        "imageStp": "dst-jpg_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=avatar_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX0y9JlFc95"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.thumbnail.url == "https://example/avatar.jpg", (
        "avatar fallback should be routed to set_thumbnail"
    )
    assert embed.image.url is None, (
        "avatar fallback should NOT be routed to set_image"
    )
    assert embed.footer.text is None, (
        "no video footer expected on a no-media post"
    )


@pytest.mark.asyncio
async def test_build_preview_embeds_threads_image_post_keeps_main_image(
    fresh_db, monkeypatch
):
    """Regression guard for Task 2: a normal Threads post with media must
    still use set_image (full-width hero), not set_thumbnail. Threads
    signals real media via twitter:card='summary_large_image'."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    image_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX1vJ40E0Eg",
        "title": "Illustrator on Threads",
        "description": "Cute illustration",
        "image": "https://example/post-media.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary_large_image",
        "imageStp": "cp6_dst-jpg_e35_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=image_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX1vJ40E0Eg"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/post-media.jpg"
    assert embed.thumbnail.url is None
    assert embed.footer.text is None


# --- _build_preview_embeds: Threads video frame footer ---------------


@pytest.mark.asyncio
async def test_build_preview_embeds_threads_video_post_gets_video_footer(
    fresh_db, monkeypatch
):
    """Threads video posts have a play-button glyph baked into the
    og:image, but the embed renders as a static image. We mark the
    video case with a footer so users don't expect inline playback.
    Detection: og:image's stp= query param starts with 'cmp1_' (Meta's
    composite-from-video-frame pipeline tag). Mirrors the existing IG
    reel handling, which keys on URL path instead since Threads has no
    /reel/ marker."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    video_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX1150kE6jR",
        "title": "シン (@hsinting._) on Threads",
        "description": "練習日文",
        "image": "https://example/video-frame.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=video_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX1150kE6jR"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/video-frame.jpg", (
        "video frame should still be the full-width hero"
    )
    assert embed.thumbnail.url is None
    assert embed.footer.text == "Video · cannot be played here"


@pytest.mark.asyncio
async def test_build_preview_embeds_instagram_reel_keeps_reel_footer(
    fresh_db, monkeypatch
):
    """Regression guard for Task 3: IG reels keep the existing
    'Reel · cannot be played here' wording. The two video-footer rules
    (IG via /reel/ URL path, Threads via cmp1_ stp= prefix) coexist
    independently and use platform-correct labels."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    reel_meta = {
        "platform": "instagram",
        "url": "https://www.instagram.com/reel/abc123/",
        "title": "Reel by @user",
        "description": "Reel caption",
        "image": "https://example/reel-frame.jpg",
        "video": None,
        "siteName": "Instagram",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=reel_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.instagram.com/reel/abc123/"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/reel-frame.jpg"
    assert embed.footer.text == "Reel · cannot be played here", (
        "IG reels must keep the Reel-specific wording even though the "
        "Threads cmp1_ rule could theoretically also fire — IG is gated "
        "out by platform check"
    )


@pytest.mark.asyncio
async def test_build_preview_embeds_instagram_normal_post_no_footer(
    fresh_db, monkeypatch
):
    """Regression guard: a normal IG /p/ post (no /reel/) gets no footer
    even when the Threads-style cmp1_ signal is present. Both video-
    detection rules are platform-gated."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    post_meta = {
        "platform": "instagram",
        "url": "https://www.instagram.com/p/abc123/",
        "title": "Post by @user",
        "description": "Caption",
        "image": "https://example/post.jpg",
        "video": None,
        "siteName": "Instagram",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=post_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.instagram.com/p/abc123/"]
    )
    assert len(embeds) == 1
    assert embeds[0].footer.text is None
