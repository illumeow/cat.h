import logging
import os
import re
import time as time_mod
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

import mod_log

if TYPE_CHECKING:
    from bot import Bot

log = logging.getLogger(__name__)

THREADS_URL_RE = re.compile(
    r"https?://(?:www\.)?threads\.(?:com|net)/[^\s?]+(?:\?\S*)?",
    re.IGNORECASE,
)

WEBHOOK_NAME_SUFFIX = "Link Embedder"

CONFIRM_EMOJI = "\N{WHITE HEAVY CHECK MARK}"
DELETE_EMOJI = "\N{CROSS MARK}"

MOD_LOG_CHANNEL_ID = int(os.environ.get("MOD_LOG_CHANNEL_ID", "0"))


def _parse_id_set(env_value: str) -> set[int]:
    out: set[int] = set()
    for part in env_value.split(","):
        part = part.strip()
        if part:
            try:
                out.add(int(part))
            except ValueError:
                log.warning("Ignoring non-integer ID %r in env list", part)
    return out


THREADS_EXCLUDED_CHANNELS = _parse_id_set(
    os.environ.get("THREADS_EXCLUDED_CHANNELS", "")
)


def _strip_query(url: str) -> str:
    q = url.find("?")
    return url[:q] if q != -1 else url


def _rebuild_content(content: str) -> tuple[str, bool]:
    """Returns (rebuilt, changed)."""
    changed = False

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        original = match.group(0)
        cleaned = _strip_query(original)
        if cleaned != original:
            changed = True
        return cleaned

    new_content = THREADS_URL_RE.sub(replace, content)
    # Even if every URL was already clean, if there were threads links we still
    # want to repost so Discord re-fetches the OG metadata. Treat any match as
    # a trigger.
    if THREADS_URL_RE.search(content):
        changed = True
    return new_content, changed


class ThreadsCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self._webhook_cache: dict[int, discord.Webhook] = {}

    # --- helpers -----------------------------------------------------------

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
                "Missing Manage Webhooks in channel %s; threads embedder disabled here",
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
                "Cannot create webhook in channel %s; threads embedder disabled",
                channel.id,
            )
            return None
        self._webhook_cache[channel.id] = created
        return created

    # --- listener: rewrite threads links ----------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return
        if message.author.id == (self.bot.user.id if self.bot.user else 0):
            return
        if message.webhook_id is not None:
            return
        if not message.content:
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

        # Excluded by either the channel itself or its parent (so listing a
        # parent channel ID excludes all of its threads in one entry).
        if message.channel.id in THREADS_EXCLUDED_CHANNELS:
            return
        if thread is not None and parent_channel.id in THREADS_EXCLUDED_CHANNELS:
            return

        new_content, changed = _rebuild_content(message.content)
        if not changed:
            return

        webhook = await self._get_webhook(parent_channel)
        if webhook is None:
            # No webhook permission — leave the original message alone.
            return

        # Post the rewritten copy first; if that fails we don't want to leave
        # the channel with neither version.
        send_kwargs: dict = {
            "content": new_content,
            "username": message.author.display_name,
            "avatar_url": message.author.display_avatar.url,
            "wait": True,
            "allowed_mentions": discord.AllowedMentions.none(),
        }
        if thread is not None:
            send_kwargs["thread"] = thread
        try:
            sent = await webhook.send(**send_kwargs)
        except discord.HTTPException:
            log.exception("Webhook send failed in channel %s", message.channel.id)
            return

        # Mark the original delete as bot-initiated so the archive cog skips
        # archiving + mod-log. Then attempt the delete; on Forbidden we keep
        # the duplicate (signal to the operator to fix Manage Messages perm).
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

        # Track for the confirm/delete reaction flow.
        await self.bot.db.execute(
            "INSERT INTO webhook_reposts "
            "(webhook_message_id, channel_id, original_author_id, "
            "cleaned_content, posted_at) VALUES (?, ?, ?, ?, ?)",
            (sent.id, message.channel.id, message.author.id, new_content, int(time_mod.time())),
        )
        await self.bot.db.commit()

        try:
            await sent.add_reaction(CONFIRM_EMOJI)
            await sent.add_reaction(DELETE_EMOJI)
        except discord.HTTPException:
            log.exception("Failed to seed reactions on webhook repost %s", sent.id)

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
            "SELECT channel_id, original_author_id, cleaned_content "
            "FROM webhook_reposts WHERE webhook_message_id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        channel_id, original_author_id, cleaned_content = row

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

        await mod_log.post_deleted(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            author_id=original_author_id,
            source_channel_id=channel_id,
            content=cleaned_content,
        )


async def setup(bot: "Bot") -> None:
    await bot.add_cog(ThreadsCog(bot))
