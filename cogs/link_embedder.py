import asyncio
import logging
import os
import re
import time as time_mod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import aiohttp
import discord
from discord.ext import commands

import mod_log
from utils import parse_id_set

if TYPE_CHECKING:
    from bot import Bot

log = logging.getLogger(__name__)

THREADS_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:com|net)/[^\s?]+(?:\?\S*)?",
    re.IGNORECASE,
)
# Instagram URLs that carry an `igsh` share-tracker. Clean IG URLs (e.g.
# plain /p/<code>/ links or ones that only carry meaningful params like
# img_index) are left alone — only igsh-tagged ones trigger a rewrite.
INSTAGRAM_IGSH_URL_RE = re.compile(
    r"https?://(?:www\.)?instagram\.com/[^\s?]+\?\S*?\bigsh=[^\s&]*\S*",
    re.IGNORECASE,
)

WEBHOOK_NAME_SUFFIX = "Link Embedder"

CONFIRM_EMOJI = "\N{WHITE HEAVY CHECK MARK}"
DELETE_EMOJI = "\N{CROSS MARK}"

MOD_LOG_CHANNEL_ID = int(os.environ.get("MOD_LOG_CHANNEL_ID", "0"))

# Sidecar that runs Playwright + Chromium and returns OG metadata for a
# given URL. Optional: an empty value disables custom embeds and the bot
# falls back to letting Discord render whatever it can.
PREVIEW_SERVICE_URL = os.environ.get("PREVIEW_SERVICE_URL", "").rstrip("/")
PREVIEW_TIMEOUT_S = 15
# Platform brand-ish colors for the custom embed's left bar.
PLATFORM_COLORS: dict[str, discord.Color] = {
    "threads": discord.Color.from_str("#000000"),
    "instagram": discord.Color.from_str("#E1306C"),
}
# Discord embed limits (we keep a small headroom under the hard caps).
EMBED_TITLE_MAX = 250
EMBED_DESC_MAX = 4000


USER_EXCLUDED_CHANNELS = parse_id_set(
    os.environ.get("LINK_EMBEDDER_EXCLUDED_CHANNELS", "")
)
# Mod-log channel is auto-excluded so the bot doesn't rewrite links posted
# there — keep mod-log as a plain channel the bot only writes notices to.
EXCLUDED_CHANNELS = USER_EXCLUDED_CHANNELS | (
    {MOD_LOG_CHANNEL_ID} if MOD_LOG_CHANNEL_ID else set()
)


def _strip_query(url: str) -> str:
    """Drop the entire `?…` query string."""
    q = url.find("?")
    return url[:q] if q != -1 else url


def _strip_param(param: str) -> Callable[[str], str]:
    """Build a cleaner that drops a single query param while preserving
    the rest. Used when most params are meaningful and only one is a
    tracker — e.g. Instagram's `igsh` alongside a real `img_index`."""

    def clean(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        kept = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k != param
        ]
        return urlunparse(parsed._replace(query=urlencode(kept)))

    return clean


# Per-platform rewrite rules. Each entry: (name, pattern, cleaner). The
# pattern decides what to act on — matching it triggers a webhook repost
# of the cleaned text, even if the cleaner output is identical (some
# embeds, e.g. threads.com, render more reliably from a fresh post).
# Add a platform = append a row.
URL_RULES: list[tuple[str, re.Pattern[str], Callable[[str], str]]] = [
    ("threads", THREADS_URL_RE, _strip_query),
    ("instagram", INSTAGRAM_IGSH_URL_RE, _strip_param("igsh")),
]


def _apply_rule(
    text: str, pattern: re.Pattern[str], cleaner: Callable[[str], str]
) -> tuple[str, list[str]]:
    """Substitute every match of `pattern` in `text` with `cleaner(match)`.
    Returns (rebuilt, cleaned_urls) — `cleaned_urls` is each match after
    the cleaner ran, in source order, useful for the preview sidecar."""
    cleaned_urls: list[str] = []

    def replace(m: re.Match[str]) -> str:
        cleaned = cleaner(m.group(0))
        cleaned_urls.append(cleaned)
        return cleaned

    return pattern.sub(replace, text), cleaned_urls


def _rebuild_content(content: str) -> tuple[str, list[str]]:
    """Apply each URL rule to the message text. Returns (rebuilt, urls) —
    `urls` is the cleaned form of every URL we matched. Empty list means
    no rule fired (the cue to leave the message alone)."""
    rebuilt = content
    matched_urls: list[str] = []
    for _name, pattern, cleaner in URL_RULES:
        rebuilt, urls = _apply_rule(rebuilt, pattern, cleaner)
        matched_urls.extend(urls)
    return rebuilt, matched_urls


def _truncate_for_embed(s: str | None, limit: int) -> str | None:
    """Cap a Discord embed field at `limit` characters with an ellipsis;
    return None for empty/None so set_* / kwargs skip the field cleanly."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "…"


class LinkEmbedderCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self._webhook_cache: dict[int, discord.Webhook] = {}
        self._http: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._http = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._http is not None:
            await self._http.close()

    # --- helpers -----------------------------------------------------------

    def _channel_or_parent_excluded(self, channel_id: int) -> bool:
        """Exclusion check that respects the parent-of-Discord-thread rule.
        Listing a parent channel ID in LINK_EMBEDDER_EXCLUDED_CHANNELS
        implicitly excludes all of its threads via the in-memory channel
        cache."""
        if channel_id in EXCLUDED_CHANNELS:
            return True
        chan = self.bot.get_channel(channel_id)
        if (
            isinstance(chan, discord.Thread)
            and chan.parent_id in EXCLUDED_CHANNELS
        ):
            return True
        return False

    async def _fetch_preview(self, url: str) -> dict[str, Any] | None:
        """Ask the preview sidecar for OG metadata about `url`. Returns the
        decoded JSON dict on success, None on any failure (timeout, HTTP
        error, service down) — the caller treats None as "no embed for
        this URL," so the bot stays usable with the sidecar absent."""
        if not PREVIEW_SERVICE_URL or self._http is None:
            return None
        try:
            async with self._http.get(
                f"{PREVIEW_SERVICE_URL}/preview",
                params={"url": url},
                timeout=aiohttp.ClientTimeout(total=PREVIEW_TIMEOUT_S),
            ) as resp:
                if resp.status != 200:
                    log.warning(
                        "Preview service returned %s for %s", resp.status, url
                    )
                    return None
                return await resp.json()
        except Exception:
            log.exception("Preview service request failed for %s", url)
            return None

    async def _build_preview_embeds(self, urls: list[str]) -> list[discord.Embed]:
        """Hit the preview sidecar for each cleaned URL (in parallel) and
        turn the OG metadata into a Discord embed. Skip URLs where the
        sidecar has nothing useful or the call failed; cap at Discord's
        10-embeds-per-message limit."""
        if not urls or not PREVIEW_SERVICE_URL or self._http is None:
            return []
        # Cap to 10 to match Discord's per-message embed limit.
        results = await asyncio.gather(
            *(self._fetch_preview(u) for u in urls[:10])
        )
        embeds: list[discord.Embed] = []
        for url, meta in zip(urls, results):
            if not meta:
                continue
            title = _truncate_for_embed(meta.get("title"), EMBED_TITLE_MAX)
            description = _truncate_for_embed(
                meta.get("description"), EMBED_DESC_MAX
            )
            if not title and not description and not meta.get("image"):
                continue  # nothing worth rendering
            embed = discord.Embed(
                title=title,
                description=description,
                url=url,
                color=PLATFORM_COLORS.get(
                    meta.get("platform"), discord.Color.default()
                ),
            )
            if meta.get("siteName"):
                embed.set_author(name=meta["siteName"])
            if meta.get("image"):
                embed.set_image(url=meta["image"])
            embeds.append(embed)
        return embeds

    def _webhook_name(self) -> str:
        bot_user = self.bot.user
        prefix = bot_user.name if bot_user else "Bot"
        return f"{prefix} {WEBHOOK_NAME_SUFFIX}"

    async def _get_webhook(
        self, channel: discord.TextChannel | discord.ForumChannel
    ) -> discord.Webhook | None:
        cached = self._webhook_cache.get(channel.id)
        if cached is not None:
            return cached
        try:
            existing = await channel.webhooks()
        except discord.Forbidden:
            log.warning(
                "Missing Manage Webhooks in channel %s; link embedder disabled here",
                channel.id,
            )
            return None
        target_name = self._webhook_name()
        for w in existing:
            if w.name == target_name and w.user == self.bot.user:
                self._webhook_cache[channel.id] = w
                return w
        try:
            avatar_bytes = None
            if self.bot.user and self.bot.user.display_avatar:
                avatar_bytes = await self.bot.user.display_avatar.read()
            created = await channel.create_webhook(
                name=target_name, avatar=avatar_bytes
            )
        except discord.Forbidden:
            log.warning(
                "Cannot create webhook in channel %s; link embedder disabled",
                channel.id,
            )
            return None
        self._webhook_cache[channel.id] = created
        return created

    # --- listener: rewrite tracked links ----------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self._process_message(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(
        self, payload: discord.RawMessageUpdateEvent
    ) -> None:
        # We also rewrite tracked links that the user adds via *edit* (e.g.
        # they post "check this:" then paste an instagram link a moment
        # later). MESSAGE_UPDATE is partial: skip events without a content
        # field or without one of our patterns in it, so we don't pay an
        # HTTP fetch on every embed-only / pin / etc. edit.
        if payload.guild_id is None:
            return
        if "content" not in payload.data:
            return
        if self._channel_or_parent_excluded(payload.channel_id):
            return
        new_content = payload.data["content"]
        if not new_content:
            return
        if not any(p.search(new_content) for _n, p, _c in URL_RULES):
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return
        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            return  # message gone, or no read perms — nothing we can do
        await self._process_message(message, is_edit=True)

    async def _process_message(
        self, message: discord.Message, *, is_edit: bool = False
    ) -> None:
        """Apply URL rules to `message.content`; if any rule matched,
        replace the message with a cleaned webhook repost. Shared between
        on_message (initial posts) and on_raw_message_edit (edits that add
        a tracked link). When `is_edit=True`, also re-target the archive
        cog's just-posted "Edited" mod-log notice so the jump URL points
        at the webhook repost rather than the now-deleted original."""
        if message.guild is None:
            return
        if message.author.id == (self.bot.user.id if self.bot.user else 0):
            return
        if message.webhook_id is not None:
            return
        if not message.content:
            return

        # Channel-level exclusion before any structural resolution. The
        # helper resolves Discord threads back to their parent so listing a
        # parent channel ID in LINK_EMBEDDER_EXCLUDED_CHANNELS implicitly
        # excludes all of its threads.
        if self._channel_or_parent_excluded(message.channel.id):
            return

        # Resolve the webhook-bearing parent channel and (optionally) the
        # Discord thread we need to post into. A webhook lives on a
        # TextChannel/ForumChannel; sending into a thread uses the thread=
        # kwarg on webhook.send.
        if isinstance(message.channel, discord.TextChannel):
            parent_channel = message.channel
            thread = None
        elif isinstance(message.channel, discord.Thread) and isinstance(
            message.channel.parent, (discord.TextChannel, discord.ForumChannel)
        ):
            parent_channel = message.channel.parent
            thread = message.channel
        else:
            return  # voice/stage/uncategorized — nothing we can post into

        new_content, matched_urls = _rebuild_content(message.content)
        if not matched_urls:
            return

        webhook = await self._get_webhook(parent_channel)
        if webhook is None:
            # No webhook permission — leave the original message alone.
            return

        # Build custom embeds from the preview sidecar before sending so we
        # can attach them in one go. When we have custom embeds we wrap
        # each rewritten URL in <…> in the message body — Discord renders
        # bare URLs with an auto-preview by default, and our explicit
        # embeds would compete with (and double-render alongside) those.
        # We can't use suppress_embeds=True for this: it sets the message's
        # SUPPRESS_EMBEDS flag, which hides every embed including our own.
        embeds = await self._build_preview_embeds(matched_urls)
        body = new_content
        if embeds:
            for url in set(matched_urls):
                body = body.replace(url, f"<{url}>")

        # Post the rewritten copy first; if that fails we don't want to leave
        # the channel with neither version.
        send_kwargs: dict = {
            "content": body,
            "username": message.author.display_name,
            "avatar_url": message.author.display_avatar.url,
            "wait": True,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if thread is not None:
            send_kwargs["thread"] = thread
        if embeds:
            send_kwargs["embeds"] = embeds
        try:
            sent = await webhook.send(**send_kwargs)
        except discord.HTTPException:
            log.exception("Webhook send failed in channel %s", message.channel.id)
            return

        # Mark the original delete as bot-initiated so the archive cog
        # skips the mod-log notice. Then attempt the delete; on Forbidden
        # we keep the duplicate (signal to the operator to fix the
        # Manage Messages perm).
        self.bot.suppressed_deletes.add(message.id)
        try:
            await message.delete()
        except discord.Forbidden:
            self.bot.suppressed_deletes.discard(message.id)
            log.warning(
                "Missing Manage Messages in channel %s; original kept alongside repost",
                message.channel.id,
            )
        except discord.HTTPException:
            self.bot.suppressed_deletes.discard(message.id)
            log.exception("Failed to delete original message %s", message.id)

        # Track for the confirm/delete reaction flow. We persist the user's
        # original message ID alongside the webhook's so a later ❌ can show
        # an /archive-show-able ID in the mod-log "Deleted" notice (the
        # webhook repost itself isn't archived; the original is).
        await self.bot.db.execute(
            "INSERT INTO webhook_reposts "
            "(webhook_message_id, channel_id, original_author_id, "
            "cleaned_content, posted_at, original_message_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                sent.id,
                message.channel.id,
                message.author.id,
                new_content,
                int(time_mod.time()),
                message.id,
            ),
        )
        await self.bot.db.commit()

        try:
            await sent.add_reaction(CONFIRM_EMOJI)
            await sent.add_reaction(DELETE_EMOJI)
        except discord.HTTPException:
            log.exception("Failed to seed reactions on webhook repost %s", sent.id)

        # If this rewrite was triggered by an edit, the archive cog has just
        # posted (or is about to post) an "Edited" mod-log notice whose jump
        # URL points at the now-deleted original. Re-target it at the
        # webhook repost so a moderator clicking through lands at the live
        # message. Best-effort — if the archive entry isn't there yet (rare
        # scheduling order) we just leave the URL stale.
        if is_edit and message.guild is not None:
            mod_log_msg_id = self.bot.recent_edit_mod_logs.pop(message.id, None)
            if mod_log_msg_id is not None:
                await self._retarget_edit_mod_log(
                    mod_log_msg_id,
                    repost_url=(
                        f"https://discord.com/channels/{message.guild.id}/"
                        f"{message.channel.id}/{sent.id}"
                    ),
                )

    async def _retarget_edit_mod_log(
        self, mod_log_message_id: int, *, repost_url: str
    ) -> None:
        """Edit the previously-posted "Edited" mod-log notice so its embed
        URL points at the webhook repost. Called after we've replaced an
        edited message; safe to no-op on any failure."""
        if MOD_LOG_CHANNEL_ID == 0:
            return
        channel = self.bot.get_channel(MOD_LOG_CHANNEL_ID)
        if not isinstance(channel, discord.abc.Messageable):
            return
        try:
            mod_log_msg = await channel.fetch_message(mod_log_message_id)
        except discord.HTTPException:
            return
        if not mod_log_msg.embeds:
            return
        embed = mod_log_msg.embeds[0]
        if embed.title != "Edited":
            return  # something else replaced the embed in the meantime
        new_embed = embed.copy()
        new_embed.url = repost_url
        try:
            await mod_log_msg.edit(embed=new_embed)
        except discord.HTTPException:
            log.exception(
                "Failed to re-target Edited mod-log %s at webhook repost",
                mod_log_message_id,
            )

    # --- listener: ✅ / ❌ reactions ---------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(
        self, payload: discord.RawReactionActionEvent
    ) -> None:
        if payload.guild_id is None:
            return
        if self.bot.user and payload.user_id == self.bot.user.id:
            return
        emoji = str(payload.emoji)
        if emoji not in (CONFIRM_EMOJI, DELETE_EMOJI):
            return

        async with self.bot.db.execute(
            "SELECT channel_id, original_author_id, cleaned_content, "
            "original_message_id "
            "FROM webhook_reposts WHERE webhook_message_id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        channel_id, original_author_id, cleaned_content, original_message_id = row

        if payload.user_id != original_author_id:
            return  # only the original poster's reactions count

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.abc.Messageable):
            return  # channel gone, uncached, or not a messageable type anymore

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.HTTPException:
            # Message gone already; just clean up the row.
            await self.bot.db.execute(
                "DELETE FROM webhook_reposts WHERE webhook_message_id = ?",
                (payload.message_id,),
            )
            await self.bot.db.commit()
            return

        if emoji == CONFIRM_EMOJI:
            try:
                await message.clear_reactions()
            except discord.HTTPException:
                log.exception("Failed to clear reactions on %s", payload.message_id)
            await self.bot.db.execute(
                "DELETE FROM webhook_reposts WHERE webhook_message_id = ?",
                (payload.message_id,),
            )
            await self.bot.db.commit()
            return

        # DELETE_EMOJI
        try:
            await message.delete()
        except discord.HTTPException:
            log.exception("Failed to delete webhook repost %s", payload.message_id)
        await self.bot.db.execute(
            "DELETE FROM webhook_reposts WHERE webhook_message_id = ?",
            (payload.message_id,),
        )
        await self.bot.db.commit()

        # Surface the user's *original* message ID in the mod-log Deleted
        # embed (the webhook repost itself isn't archived, but the original
        # is — so /archive show <id> works on this value). Legacy rows
        # written before original_message_id existed fall back to the
        # webhook ID; nothing's gained from /archive show on those, but it
        # at least identifies the message that was deleted.
        await mod_log.post_deleted(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            message_id=original_message_id or payload.message_id,
            author_id=original_author_id,
            source_channel_id=channel_id,
            content=cleaned_content,
        )


async def setup(bot: "Bot") -> None:
    await bot.add_cog(LinkEmbedderCog(bot))
