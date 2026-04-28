import logging
import os
import shutil
import time as time_mod
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

import mod_log

log = logging.getLogger(__name__)

TZ = ZoneInfo(os.environ.get("TIME_ZONE", "UTC"))
PURGE_TIME = time(hour=3, tzinfo=TZ)

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


MODERATOR_IDS = _parse_id_set(os.environ.get("MODERATOR_IDS", ""))
USER_EXCLUDED_CHANNELS = _parse_id_set(os.environ.get("ARCHIVE_EXCLUDED_CHANNELS", ""))
# Mod-log channel is auto-excluded from logging to avoid recursion.
EXCLUDED_CHANNELS = USER_EXCLUDED_CHANNELS | (
    {MOD_LOG_CHANNEL_ID} if MOD_LOG_CHANNEL_ID else set()
)

ATTACHMENTS_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"
TTL_DAYS = 90
WEBHOOK_REPOST_TTL_DAYS = 7
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB


def _now() -> int:
    return int(time_mod.time())


class ArchiveCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
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

    def _is_moderator(self, user_id: int) -> bool:
        return user_id in MODERATOR_IDS

    def _should_log(self, message: discord.Message) -> bool:
        if message.guild is None:
            return False  # DM
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
        if payload.data.get("guild_id") is None:
            return
        if "content" not in payload.data:
            return  # not a content edit (could be embed-only update)
        new_content = payload.data["content"]

        async with self.bot.db.execute(
            "SELECT content, channel_id, author_id FROM messages WHERE id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        prior_content, channel_id, author_id = row
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

        if channel_id in EXCLUDED_CHANNELS:
            return
        await mod_log.post_edited(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            author_id=author_id,
            source_channel_id=channel_id,
            before=prior_content,
            after=new_content,
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(
        self, payload: discord.RawMessageDeleteEvent
    ) -> None:
        # Cross-cog handshake: bot-initiated deletes (e.g. the threads cog
        # rewriting a link) are pre-registered. We still mark them deleted in
        # the DB (the message *was* deleted; that's the truth) and still
        # download attachments, but we skip the mod-log notice — the user
        # didn't initiate the delete, the bot did.
        suppress_mod_log = payload.message_id in self.bot.suppressed_deletes
        if suppress_mod_log:
            self.bot.suppressed_deletes.discard(payload.message_id)

        async with self.bot.db.execute(
            "SELECT channel_id, author_id, content, deleted_at "
            "FROM messages WHERE id = ?",
            (payload.message_id,),
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return
        channel_id, author_id, content, already_deleted = row
        if already_deleted is not None:
            return  # double-delete event (shouldn't happen, but be safe)

        now = _now()
        await self.bot.db.execute(
            "UPDATE messages SET deleted_at = ? WHERE id = ?",
            (now, payload.message_id),
        )
        await self.bot.db.commit()

        downloaded = await self._download_attachments(payload.message_id)

        if suppress_mod_log:
            return
        if channel_id in EXCLUDED_CHANNELS:
            return

        attachments_summary = None
        if downloaded:
            lines = []
            for filename, local_path, skipped_reason in downloaded:
                if local_path:
                    lines.append(f"• `{filename}` (saved)")
                elif skipped_reason:
                    lines.append(f"• `{filename}` ({skipped_reason})")
                else:
                    lines.append(f"• `{filename}`")
            attachments_summary = "\n".join(lines)

        await mod_log.post_deleted(
            self.bot,
            MOD_LOG_CHANNEL_ID,
            author_id=author_id,
            source_channel_id=channel_id,
            content=content,
            attachments_summary=attachments_summary,
        )

    # --- attachment download ----------------------------------------------

    async def _download_attachments(
        self, message_id: int
    ) -> list[tuple[str, str | None, str | None]]:
        """Returns list of (filename, local_path, skipped_reason) tuples."""
        if self._http is None:
            return []

        async with self.bot.db.execute(
            "SELECT id, filename, url, size FROM attachments WHERE message_id = ?",
            (message_id,),
        ) as cur:
            rows = await cur.fetchall()

        results: list[tuple[str, str | None, str | None]] = []
        for att_id, filename, url, size in rows:
            if size is not None and size > MAX_ATTACHMENT_BYTES:
                await self.bot.db.execute(
                    "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                    ("too_large", att_id),
                )
                results.append((filename, None, "too_large"))
                continue

            target_dir = ATTACHMENTS_DIR / str(message_id)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / filename

            try:
                async with self._http.get(url) as resp:
                    if resp.status != 200:
                        reason = f"http_{resp.status}"
                        await self.bot.db.execute(
                            "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                            (reason, att_id),
                        )
                        results.append((filename, None, reason))
                        continue
                    with open(target_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(64 * 1024):
                            f.write(chunk)
                await self.bot.db.execute(
                    "UPDATE attachments SET local_path = ? WHERE id = ?",
                    (str(target_path), att_id),
                )
                results.append((filename, str(target_path), None))
            except (aiohttp.ClientError, OSError):
                log.exception("Attachment download failed for %s", url)
                await self.bot.db.execute(
                    "UPDATE attachments SET skipped_reason = ? WHERE id = ?",
                    ("download_failed", att_id),
                )
                results.append((filename, None, "download_failed"))

        await self.bot.db.commit()
        return results

    # --- TTL purge ---------------------------------------------------------

    @tasks.loop(time=PURGE_TIME)
    async def daily_purge(self) -> None:
        msg_cutoff = int(
            (datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)).timestamp()
        )
        async with self.bot.db.execute(
            "SELECT id FROM messages WHERE created_at < ?", (msg_cutoff,)
        ) as cur:
            ids = [row[0] for row in await cur.fetchall()]
        await self.bot.db.execute(
            "DELETE FROM messages WHERE created_at < ?", (msg_cutoff,)
        )

        repost_cutoff = int(
            (
                datetime.now(timezone.utc) - timedelta(days=WEBHOOK_REPOST_TTL_DAYS)
            ).timestamp()
        )
        await self.bot.db.execute(
            "DELETE FROM webhook_reposts WHERE posted_at < ?", (repost_cutoff,)
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
        if not self._is_moderator(interaction.user.id):
            await interaction.response.send_message(
                "You're not authorized to use this command.", ephemeral=True
            )
            return

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
            title=f"Deleted messages ({len(rows)})",
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
        if not self._is_moderator(interaction.user.id):
            await interaction.response.send_message(
                "You're not authorized to use this command.", ephemeral=True
            )
            return

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
            "WHERE message_id = ? ORDER BY edited_at",
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArchiveCog(bot))
