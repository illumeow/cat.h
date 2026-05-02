import logging
import os
import time as time_mod
from datetime import time
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from core import archive, mod_log
from core.utils import is_channel_or_parent_in, parse_id_set

if TYPE_CHECKING:
    from bot import Bot

log = logging.getLogger(__name__)

TZ = ZoneInfo(os.environ.get("TIME_ZONE", "UTC"))
PURGE_TIME = time(hour=3, tzinfo=TZ)

MOD_LOG_CHANNEL_ID = int(os.environ.get("MOD_LOG_CHANNEL_ID", "0"))


USER_EXCLUDED_CHANNELS = parse_id_set(os.environ.get("ARCHIVE_EXCLUDED_CHANNELS", ""))
# Mod-log channel is auto-excluded from logging to avoid recursion.
EXCLUDED_CHANNELS = USER_EXCLUDED_CHANNELS | (
    {MOD_LOG_CHANNEL_ID} if MOD_LOG_CHANNEL_ID else set()
)


def _now() -> int:
    return int(time_mod.time())


class ArchiveCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self._http: aiohttp.ClientSession | None = None
        self.daily_purge.start()

    async def cog_load(self) -> None:
        self._http = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        self.daily_purge.cancel()
        if self._http is not None:
            await self._http.close()

    # --- helpers -----------------------------------------------------------

    def _should_log(self, message: discord.Message) -> bool:
        # Caller is expected to have filtered DMs (message.guild is None).
        if message.is_system():
            return False
        if message.webhook_id is not None:
            return False  # don't archive our own webhook reposts (or any webhook)
        if message.channel.id in EXCLUDED_CHANNELS:
            return False
        # A thread inherits its parent's exclusion: listing a parent channel
        # ID in ARCHIVE_EXCLUDED_CHANNELS implicitly excludes all threads in it.
        if (
            isinstance(message.channel, discord.Thread)
            and message.channel.parent_id in EXCLUDED_CHANNELS
        ):
            return False
        return True

    @staticmethod
    def _attachment_summary(rows: list[archive.Attachment]) -> str | None:
        """Format the bullet list used in deletion / removal mod-log
        embeds from a list of Attachment rows already fetched by the
        caller."""
        if not rows:
            return None
        lines = []
        for att in rows:
            if att.local_path:
                lines.append(f"• `{att.filename}` (saved)")
            elif att.skipped_reason:
                lines.append(f"• `{att.filename}` ({att.skipped_reason})")
            else:
                lines.append(f"• `{att.filename}`")
        return "\n".join(lines)

    # --- listeners ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return  # DM — also narrows message.guild for the type checker
        if not self._should_log(message):
            return
        await archive.record(
            self.bot.db,
            message_id=message.id,
            channel_id=message.channel.id,
            guild_id=message.guild.id,
            author_id=message.author.id,
            content=message.content,
            created_at=int(message.created_at.timestamp()),
            attachments=[
                archive.AttachmentSpec(
                    filename=att.filename,
                    url=att.url,
                    content_type=att.content_type,
                    size=att.size,
                )
                for att in message.attachments
            ],
        )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        guild_id = payload.guild_id
        if guild_id is None:
            return  # DM edit — narrows guild_id to int for the post_edited call
        # Channel-level exclusion before any DB work. Mod-log is in
        # EXCLUDED_CHANNELS automatically, so this short-circuits all edits
        # in mod-log too. The helper also matches a Discord thread whose
        # parent channel was added to the exclusion list after archive time.
        if is_channel_or_parent_in(self.bot, payload.channel_id, EXCLUDED_CHANNELS):
            return
        # Discord's MESSAGE_UPDATE is partial: only changed fields are
        # delivered. Skip events that touch neither content nor attachments
        # (e.g. embed regeneration after a URL fetch, pin status changes).
        has_content = "content" in payload.data
        has_attachments = "attachments" in payload.data
        if not has_content and not has_attachments:
            return

        archived = await archive.get(self.bot.db, payload.message_id)
        if archived is None:
            return

        # 1) Attachment removal — eagerly download anything the user dropped
        # before its CDN URL stops resolving. We compare URL paths (ignoring
        # the rotating signed query params) against still-pending DB rows;
        # already-saved or already-skipped rows are excluded so we don't
        # re-fire on a later edit.
        if has_attachments:
            payload_att_paths = {
                a["url"].split("?", 1)[0] for a in payload.data["attachments"]
            }
            pending = await archive.pending_attachments(
                self.bot.db, payload.message_id
            )
            removed_db_ids = {
                att.id
                for att in pending
                if att.url.split("?", 1)[0] not in payload_att_paths
            }
            if removed_db_ids and self._http is not None:
                await archive.download_pending(
                    self.bot.db,
                    self._http,
                    payload.message_id,
                    restrict_to_db_ids=removed_db_ids,
                )
                summary = self._attachment_summary(
                    await archive.get_attachments(
                        self.bot.db,
                        payload.message_id,
                        restrict_to_db_ids=removed_db_ids,
                    )
                )
                if summary is not None:
                    await mod_log.post_attachment_removed(
                        self.bot,
                        MOD_LOG_CHANNEL_ID,
                        guild_id=guild_id,
                        message_id=payload.message_id,
                        author_id=archived.author_id,
                        source_channel_id=payload.channel_id,
                        attachments_summary=summary,
                    )

        # 2) Text edit — record the prior version and post the live notice.
        if not has_content:
            return
        new_content = payload.data["content"]
        if archived.content == new_content:
            return

        now = _now()
        await archive.record_edit(
            self.bot.db,
            message_id=payload.message_id,
            prior_content=archived.content,
            new_content=new_content,
            edited_at=now,
        )

        sent = await mod_log.post_edited(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            guild_id=guild_id,
            message_id=payload.message_id,
            author_id=archived.author_id,
            source_channel_id=payload.channel_id,
            before=archived.content,
            after=new_content,
        )
        # Hand the link embedder a way to re-target this notice's jump URL
        # if it's about to rewrite the message. Insertion-ordered dict, so
        # the oldest entries get evicted first when the cap is hit.
        if sent is not None:
            self.bot.recent_edit_mod_logs[payload.message_id] = sent.id
            while len(self.bot.recent_edit_mod_logs) > 200:
                oldest = next(iter(self.bot.recent_edit_mod_logs))
                del self.bot.recent_edit_mod_logs[oldest]

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        # Cross-cog handshake: bot-initiated deletes (e.g. the link embedder
        # rewriting a tracked URL) are pre-registered. From the user's POV
        # the message is now alive via the webhook repost — the *intentional*
        # deletion is when they press ❌ on it later. So we leave deleted_at
        # NULL here; the link embedder's ❌ handler will set it then. We
        # also skip the attachment download (URL rewrites are text-only) and
        # the mod-log notice (the bot caused this delete, not the user).
        suppress_mod_log = payload.message_id in self.bot.suppressed_deletes
        self.bot.suppressed_deletes.discard(payload.message_id)

        if is_channel_or_parent_in(self.bot, payload.channel_id, EXCLUDED_CHANNELS):
            return

        if suppress_mod_log:
            log.info(
                "Suppressed delete for message %s in channel %s "
                "(bot-initiated; deleted_at deferred until ❌, attachments not saved)",
                payload.message_id,
                payload.channel_id,
            )
            return

        archived = await archive.get(self.bot.db, payload.message_id)
        if archived is None:
            return
        if not await archive.mark_deleted(
            self.bot.db, message_id=payload.message_id, deleted_at=_now()
        ):
            return  # already deleted (double-delete event)

        if self._http is not None:
            await archive.download_pending(
                self.bot.db, self._http, payload.message_id
            )
        attachments_summary = self._attachment_summary(
            await archive.get_attachments(self.bot.db, payload.message_id)
        )

        await mod_log.post_deleted(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            message_id=payload.message_id,
            author_id=archived.author_id,
            source_channel_id=payload.channel_id,
            content=archived.content,
            attachments_summary=attachments_summary,
        )

    # --- TTL purge ---------------------------------------------------------

    @tasks.loop(time=PURGE_TIME)
    async def daily_purge(self) -> None:
        purged = await archive.purge_expired(self.bot.db)
        # Shared TTL window: webhook_reposts uses the same 90-day cap as
        # the archive but it's the link embedder's table. We run the
        # DELETE here because daily_purge already exists; revisit when
        # the link embedder grows its own scheduled work.
        await self.bot.db.execute(
            "DELETE FROM webhook_reposts WHERE posted_at < ?",
            (archive.cutoff_ts(),),
        )
        await self.bot.db.commit()

        log.info(
            "Purged %d archived messages older than %d days",
            purged,
            archive.TTL_DAYS,
        )

    @daily_purge.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()

    # --- slash commands ----------------------------------------------------

    archive = app_commands.Group(
        name="archive",
        description="Archive query commands (moderator only)",
        guild_only=True,
        # Hidden from every member by default. The server admin grants access
        # once per role via Server Settings → Integrations → bot → /archive →
        # Roles. Discord enforces this at invocation time, so no further
        # in-handler authorization check is needed.
        default_permissions=discord.Permissions(),
    )

    @archive.command(
        name="deleted", description="List recent deleted messages from the archive"
    )
    @app_commands.describe(
        user="Filter to messages by this user",
        channel="Filter to messages in this channel",
        limit="How many results (default 10, max 25)",
    )
    async def archive_deleted(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        channel: discord.TextChannel | None = None,
        limit: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        rows = await archive.list_deleted(
            self.bot.db,
            user_id=user.id if user else None,
            channel_id=channel.id if channel else None,
            limit=limit,
        )
        if not rows:
            await interaction.response.send_message(
                "No deleted messages match.", ephemeral=True
            )
            return

        lines = []
        for r in rows:
            edit_marker = " *(edited)*" if r.edited_at else ""
            preview = (r.content or "*(empty)*").replace("\n", " ")[:120]
            lines.append(
                f"`{r.id}` <t:{r.deleted_at}:R> by <@{r.author_id}> "
                f"in <#{r.channel_id}>{edit_marker}\n> {preview}"
            )

        embed = discord.Embed(
            title=f"Deleted messages ({len(lines)})",
            description=mod_log.truncate("\n\n".join(lines), mod_log.EMBED_DESC_MAX),
            color=discord.Color.dark_grey(),
        )
        embed.set_footer(text="Use /archive show <id> for full detail")
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @archive.command(
        name="show", description="Show full archive detail for a message ID"
    )
    @app_commands.describe(message_id="Discord message ID (right-click → Copy ID)")
    async def archive_show(
        self, interaction: discord.Interaction, message_id: str
    ) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "That's not a valid message ID.", ephemeral=True
            )
            return

        archived = await archive.get(self.bot.db, mid)
        if archived is None:
            await interaction.response.send_message(
                "Not found in the archive.", ephemeral=True
            )
            return

        edits = await archive.get_edits(self.bot.db, mid)
        attachments = await archive.get_attachments(self.bot.db, mid)

        embed = discord.Embed(title=f"Message `{mid}`", color=discord.Color.blue())
        embed.add_field(name="Author", value=f"<@{archived.author_id}>", inline=True)
        embed.add_field(name="Channel", value=f"<#{archived.channel_id}>", inline=True)
        embed.add_field(
            name="Created", value=f"<t:{archived.created_at}:F>", inline=False
        )
        if archived.deleted_at:
            embed.add_field(
                name="Deleted", value=f"<t:{archived.deleted_at}:F>", inline=False
            )
        embed.add_field(
            name="Latest content",
            value=mod_log.truncate(archived.content, mod_log.FIELD_VALUE_MAX),
            inline=False,
        )
        for i, edit in enumerate(edits, start=1):
            embed.add_field(
                name=f"Prior version {i} (saved <t:{edit.edited_at}:R>)",
                value=mod_log.truncate(edit.content, mod_log.FIELD_VALUE_MAX),
                inline=False,
            )
        if attachments:
            lines = []
            for att in attachments:
                if att.local_path:
                    lines.append(f"• `{att.filename}` → `{att.local_path}`")
                elif att.skipped_reason:
                    lines.append(f"• `{att.filename}` (skipped: {att.skipped_reason})")
                else:
                    lines.append(f"• `{att.filename}` (not downloaded)")
            embed.add_field(
                name="Attachments",
                value=mod_log.truncate("\n".join(lines), mod_log.FIELD_VALUE_MAX),
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @archive.command(
        name="get", description="Re-upload archived attachments for a message"
    )
    @app_commands.describe(message_id="Discord message ID (right-click → Copy ID)")
    async def archive_get(
        self, interaction: discord.Interaction, message_id: str
    ) -> None:
        try:
            mid = int(message_id)
        except ValueError:
            await interaction.response.send_message(
                "That's not a valid message ID.", ephemeral=True
            )
            return

        attachments = await archive.get_attachments(self.bot.db, mid)
        if not attachments:
            await interaction.response.send_message(
                "No attachments archived for that message.", ephemeral=True
            )
            return

        # Defer before opening files (sync I/O can block briefly) and before
        # the upload itself (which may exceed the 3-second response window).
        await interaction.response.defer(ephemeral=True)

        files: list[discord.File] = []
        notes: list[str] = []
        for att in attachments:
            if att.local_path:
                path = Path(att.local_path)
                if path.exists():
                    files.append(discord.File(path, filename=att.filename))
                else:
                    notes.append(
                        f"• `{att.filename}` — DB says saved but file is missing on disk"
                    )
            elif att.skipped_reason:
                notes.append(
                    f"• `{att.filename}` — skipped at download time ({att.skipped_reason})"
                )
            else:
                notes.append(
                    f"• `{att.filename}` — not downloaded yet (message still live)"
                )

        # Empty content is fine here: when there are no notes, `files` is
        # always non-empty (we early-returned on `not attachments`), so Discord still
        # has something to render. Avoids passing None where Pylance expects str.
        content = "\n".join(notes)
        # `discord.File(path, …)` opens the file at construction. Whether
        # the upload succeeds, fails with HTTPException, or escapes with
        # any other exception, every File instance has to be closed —
        # otherwise we leak file descriptors on the unexpected-error path.
        # close() is idempotent, so calling it after discord.py has
        # already consumed the file is fine.
        try:
            try:
                await interaction.followup.send(
                    content=content,
                    files=files,
                    ephemeral=True,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except discord.HTTPException as exc:
                await interaction.followup.send(
                    f"Discord rejected the upload ({exc}). Files are still on "
                    f"the bot host at `data/attachments/{mid}/`.",
                    ephemeral=True,
                )
        finally:
            for f in files:
                f.close()


async def setup(bot: "Bot") -> None:
    await bot.add_cog(ArchiveCog(bot))
