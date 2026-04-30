import logging
import os
import shutil
import time as time_mod
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import mod_log
from utils import parse_id_set

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

ATTACHMENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"
# Retention window for everything the archive cog purges nightly: message
# rows + edits + attachments, plus webhook_reposts (✅/❌ both delete the
# row when processed, so this only governs the rare case where the user
# never reacts).
TTL_DAYS = 90
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB


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

    def _channel_or_parent_excluded(self, channel_id: int) -> bool:
        """Exclusion check that respects the parent-of-Discord-thread rule.
        Used by the raw edit/delete listeners which only receive the channel
        ID; the in-memory channel cache resolves the parent for us."""
        if channel_id in EXCLUDED_CHANNELS:
            return True
        chan = self.bot.get_channel(channel_id)
        if isinstance(chan, discord.Thread) and chan.parent_id in EXCLUDED_CHANNELS:
            return True
        return False

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

    # --- listeners ---------------------------------------------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None:
            return  # DM — also narrows message.guild for the type checker
        if not self._should_log(message):
            return
        await self.bot.db.execute(
            "INSERT OR IGNORE INTO messages "
            "(id, channel_id, guild_id, author_id, content, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                message.id,
                message.channel.id,
                message.guild.id,
                message.author.id,
                message.content,
                int(message.created_at.timestamp()),
            ),
        )
        for att in message.attachments:
            await self.bot.db.execute(
                "INSERT INTO attachments "
                "(message_id, filename, url, content_type, size) "
                "VALUES (?, ?, ?, ?, ?)",
                (message.id, att.filename, att.url, att.content_type, att.size),
            )
        await self.bot.db.commit()

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        guild_id = payload.guild_id
        if guild_id is None:
            return  # DM edit — narrows guild_id to int for the post_edited call
        # Channel-level exclusion before any DB work. Mod-log is in
        # EXCLUDED_CHANNELS automatically, so this short-circuits all edits
        # in mod-log too. The helper also matches a Discord thread whose
        # parent channel was added to the exclusion list after archive time.
        if self._channel_or_parent_excluded(payload.channel_id):
            return
        # Discord's MESSAGE_UPDATE is partial: only changed fields are
        # delivered. Skip events that touch neither content nor attachments
        # (e.g. embed regeneration after a URL fetch, pin status changes).
        has_content = "content" in payload.data
        has_attachments = "attachments" in payload.data
        if not has_content and not has_attachments:
            return

        async with self.bot.db.execute(
            "SELECT content, author_id FROM messages WHERE id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        prior_content, author_id = row

        # 1) Attachment removal — eagerly download anything the user dropped
        # before its CDN URL stops resolving. We compare URL paths (ignoring
        # the rotating signed query params) against still-pending DB rows;
        # already-saved or already-skipped rows are excluded so we don't
        # re-fire on a later edit.
        if has_attachments:
            payload_att_paths = {
                a["url"].split("?", 1)[0] for a in payload.data["attachments"]
            }
            async with self.bot.db.execute(
                "SELECT id, url FROM attachments "
                "WHERE message_id = ? "
                "AND local_path IS NULL AND skipped_reason IS NULL",
                (payload.message_id,),
            ) as cur:
                pending = await cur.fetchall()
            removed_db_ids = {
                att_id
                for att_id, url in pending
                if url.split("?", 1)[0] not in payload_att_paths
            }
            if removed_db_ids:
                await self._download_attachments(
                    payload.message_id, restrict_to_db_ids=removed_db_ids
                )
                summary = await self._attachment_summary(
                    payload.message_id, restrict_to_db_ids=removed_db_ids
                )
                if summary is not None:
                    await mod_log.post_attachment_removed(
                        self.bot,
                        MOD_LOG_CHANNEL_ID,
                        guild_id=guild_id,
                        message_id=payload.message_id,
                        author_id=author_id,
                        source_channel_id=payload.channel_id,
                        attachments_summary=summary,
                    )

        # 2) Text edit — record the prior version and post the live notice.
        if not has_content:
            return
        new_content = payload.data["content"]
        if prior_content == new_content:
            return

        now = _now()
        await self.bot.db.execute(
            "INSERT INTO message_edits (message_id, content, edited_at) "
            "VALUES (?, ?, ?)",
            (payload.message_id, prior_content, now),
        )
        await self.bot.db.execute(
            "UPDATE messages SET content = ?, edited_at = ? WHERE id = ?",
            (new_content, now, payload.message_id),
        )
        await self.bot.db.commit()

        sent = await mod_log.post_edited(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            guild_id=guild_id,
            message_id=payload.message_id,
            author_id=author_id,
            source_channel_id=payload.channel_id,
            before=prior_content,
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

        # Channel-level exclusion before any DB or disk work. Helper also
        # catches Discord-thread parents added to the exclusion list after
        # the message was archived.
        if self._channel_or_parent_excluded(payload.channel_id):
            return

        if suppress_mod_log:
            log.info(
                "Suppressed delete for message %s in channel %s "
                "(bot-initiated; deleted_at deferred until ❌, attachments not saved)",
                payload.message_id,
                payload.channel_id,
            )
            return

        async with self.bot.db.execute(
            "SELECT author_id, content, deleted_at FROM messages WHERE id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        author_id, content, already_deleted = row
        if already_deleted is not None:
            return  # double-delete event (shouldn't happen, but be safe)

        now = _now()
        await self.bot.db.execute(
            "UPDATE messages SET deleted_at = ? WHERE id = ?",
            (now, payload.message_id),
        )
        await self.bot.db.commit()

        await self._download_attachments(payload.message_id)
        attachments_summary = await self._attachment_summary(payload.message_id)

        await mod_log.post_deleted(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            message_id=payload.message_id,
            author_id=author_id,
            source_channel_id=payload.channel_id,
            content=content,
            attachments_summary=attachments_summary,
        )

    # --- attachment download ----------------------------------------------

    async def _download_attachments(
        self,
        message_id: int,
        restrict_to_db_ids: set[int] | None = None,
    ) -> None:
        """Download any attachments for this message that haven't yet been
        processed (local_path and skipped_reason are both NULL). Idempotent —
        rows already saved or skipped are left alone, so calling this from
        both the edit handler (for removed attachments) and the delete
        handler is safe and won't re-fetch the same file twice.

        If restrict_to_db_ids is given, only those `attachments.id` rows are
        considered; this lets the edit handler grab just the removed-from-
        message attachments without prematurely downloading the still-live
        ones (those stay lazy until the message is deleted).
        """
        if self._http is None:
            return

        sql = (
            "SELECT id, filename, url, size FROM attachments "
            "WHERE message_id = ? "
            "AND local_path IS NULL AND skipped_reason IS NULL"
        )
        params: list[object] = [message_id]
        if restrict_to_db_ids is not None:
            if not restrict_to_db_ids:
                return
            placeholders = ",".join(["?"] * len(restrict_to_db_ids))
            sql += f" AND id IN ({placeholders})"
            params.extend(restrict_to_db_ids)

        async with self.bot.db.execute(sql, params) as cur:
            rows = await cur.fetchall()

        for att_id, filename, url, size in rows:
            if size is not None and size > MAX_ATTACHMENT_BYTES:
                await self.bot.db.execute(
                    "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                    ("too_large", att_id),
                )
                continue

            target_dir = ATTACHMENTS_DIR / str(message_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename

            try:
                async with self._http.get(url) as resp:
                    if resp.status != 200:
                        await self.bot.db.execute(
                            "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                            (f"http_{resp.status}", att_id),
                        )
                        continue
                    with open(target_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            f.write(chunk)
                await self.bot.db.execute(
                    "UPDATE attachments SET local_path = ? WHERE id = ?",
                    (str(target_path), att_id),
                )
            except (aiohttp.ClientError, OSError):
                log.exception("Attachment download failed for %s", url)
                await self.bot.db.execute(
                    "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                    ("download_failed", att_id),
                )

        await self.bot.db.commit()

    async def _attachment_summary(
        self,
        message_id: int,
        restrict_to_db_ids: set[int] | None = None,
    ) -> str | None:
        """Format the bullet list used in deletion / removal mod-log embeds
        from the current state of the attachments table."""
        sql = (
            "SELECT filename, local_path, skipped_reason FROM attachments "
            "WHERE message_id = ?"
        )
        params: list[object] = [message_id]
        if restrict_to_db_ids is not None:
            if not restrict_to_db_ids:
                return None
            placeholders = ",".join(["?"] * len(restrict_to_db_ids))
            sql += f" AND id IN ({placeholders})"
            params.extend(restrict_to_db_ids)

        async with self.bot.db.execute(sql, params) as cur:
            rows = await cur.fetchall()
        if not rows:
            return None

        lines = []
        for filename, local_path, skipped_reason in rows:
            if local_path:
                lines.append(f"• `{filename}` (saved)")
            elif skipped_reason:
                lines.append(f"• `{filename}` ({skipped_reason})")
            else:
                lines.append(f"• `{filename}`")
        return "\n".join(lines)

    # --- TTL purge ---------------------------------------------------------

    @tasks.loop(time=PURGE_TIME)
    async def daily_purge(self) -> None:
        cutoff = int(
            (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)).timestamp()
        )
        async with self.bot.db.execute(
            "SELECT id FROM messages WHERE created_at < ?", (cutoff,)
        ) as cur:
            ids = [row[0] for row in await cur.fetchall()]
        await self.bot.db.execute(
            "DELETE FROM messages WHERE created_at < ?", (cutoff,)
        )
        await self.bot.db.execute(
            "DELETE FROM webhook_reposts WHERE posted_at < ?", (cutoff,)
        )
        await self.bot.db.commit()

        for mid in ids:
            d = ATTACHMENTS_DIR / str(mid)
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)

        log.info(
            "Purged %d archived messages older than %d days", len(ids), TTL_DAYS
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
        sql = (
            "SELECT id, channel_id, author_id, content, edited_at, deleted_at "
            "FROM messages WHERE deleted_at IS NOT NULL"
        )
        params: list[object] = []
        if user is not None:
            sql += " AND author_id = ?"
            params.append(user.id)
        if channel is not None:
            sql += " AND channel_id = ?"
            params.append(channel.id)
        sql += " ORDER BY deleted_at DESC LIMIT ?"
        params.append(limit)

        async with self.bot.db.execute(sql, params) as cur:
            rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message(
                "No deleted messages match.", ephemeral=True
            )
            return

        lines = []
        for mid, ch_id, auth_id, content, edited_at, deleted_at in rows:
            edit_marker = " *(edited)*" if edited_at else ""
            preview = (content or "*(empty)*").replace("\n", " ")[:120]
            lines.append(
                f"`{mid}` <t:{deleted_at}:R> by <@{auth_id}> in <#{ch_id}>{edit_marker}\n"
                f"> {preview}"
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

        async with self.bot.db.execute(
            "SELECT channel_id, author_id, content, created_at, edited_at, deleted_at "
            "FROM messages WHERE id = ?",
            (mid,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            await interaction.response.send_message(
                "Not found in the archive.", ephemeral=True
            )
            return
        ch_id, auth_id, content, created_at, edited_at, deleted_at = row

        async with self.bot.db.execute(
            "SELECT content, edited_at FROM message_edits "
            "WHERE message_id = ? ORDER BY edited_at DESC",
            (mid,),
        ) as cur:
            edits = await cur.fetchall()

        async with self.bot.db.execute(
            "SELECT filename, local_path, skipped_reason "
            "FROM attachments WHERE message_id = ?",
            (mid,),
        ) as cur:
            attachments = await cur.fetchall()

        embed = discord.Embed(title=f"Message `{mid}`", color=discord.Color.blue())
        embed.add_field(name="Author", value=f"<@{auth_id}>", inline=True)
        embed.add_field(name="Channel", value=f"<#{ch_id}>", inline=True)
        embed.add_field(name="Created", value=f"<t:{created_at}:F>", inline=False)
        if deleted_at:
            embed.add_field(name="Deleted", value=f"<t:{deleted_at}:F>", inline=False)
        embed.add_field(
            name="Latest content",
            value=mod_log.truncate(content, mod_log.FIELD_VALUE_MAX),
            inline=False,
        )
        for i, (edit_content, edit_at) in enumerate(edits, start=1):
            embed.add_field(
                name=f"Prior version {i} (saved <t:{edit_at}:R>)",
                value=mod_log.truncate(edit_content, mod_log.FIELD_VALUE_MAX),
                inline=False,
            )
        if attachments:
            lines = []
            for filename, local_path, skipped_reason in attachments:
                if local_path:
                    lines.append(f"• `{filename}` → `{local_path}`")
                elif skipped_reason:
                    lines.append(f"• `{filename}` (skipped: {skipped_reason})")
                else:
                    lines.append(f"• `{filename}` (not downloaded)")
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

        async with self.bot.db.execute(
            "SELECT filename, local_path, skipped_reason "
            "FROM attachments WHERE message_id = ?",
            (mid,),
        ) as cur:
            rows = await cur.fetchall()

        if not rows:
            await interaction.response.send_message(
                "No attachments archived for that message.", ephemeral=True
            )
            return

        # Defer before opening files (sync I/O can block briefly) and before
        # the upload itself (which may exceed the 3-second response window).
        await interaction.response.defer(ephemeral=True)

        files: list[discord.File] = []
        notes: list[str] = []
        for filename, local_path, skipped_reason in rows:
            if local_path:
                path = Path(local_path)
                if path.exists():
                    files.append(discord.File(path, filename=filename))
                else:
                    notes.append(
                        f"• `{filename}` — DB says saved but file is missing on disk"
                    )
            elif skipped_reason:
                notes.append(
                    f"• `{filename}` — skipped at download time ({skipped_reason})"
                )
            else:
                notes.append(
                    f"• `{filename}` — not downloaded yet (message still live)"
                )

        # Empty content is fine here: when there are no notes, `files` is
        # always non-empty (we early-returned on `not rows`), so Discord still
        # has something to render. Avoids passing None where Pylance expects str.
        content = "\n".join(notes)
        try:
            await interaction.followup.send(
                content=content,
                files=files,
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.HTTPException as exc:
            for f in files:
                f.close()
            await interaction.followup.send(
                f"Discord rejected the upload ({exc}). Files are still on the "
                f"bot host at `data/attachments/{mid}/`.",
                ephemeral=True,
            )


async def setup(bot: "Bot") -> None:
    await bot.add_cog(ArchiveCog(bot))
