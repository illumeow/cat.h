import logging

import discord

log = logging.getLogger(__name__)

EMBED_DESC_MAX = 4000  # leave headroom under Discord's 4096 limit
FIELD_VALUE_MAX = 1000  # leave headroom under Discord's 1024 limit


def truncate(text: str | None, limit: int) -> str:
    if not text:
        return "*(empty)*"
    if len(text) <= limit:
        return text
    return text[: limit - len("\n…(truncated)")] + "\n…(truncated)"


async def _send(bot, channel_id: int, embed: discord.Embed) -> None:
    if channel_id == 0:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        log.warning("Mod-log channel %s not in cache; skipping post.", channel_id)
        return
    try:
        await channel.send(
            embed=embed, allowed_mentions=discord.AllowedMentions.none()
        )
    except discord.HTTPException:
        log.exception("Failed to post to mod-log channel %s", channel_id)


async def post_deleted(
    bot,
    channel_id: int,
    *,
    message_id: int,
    author_id: int,
    source_channel_id: int,
    content: str | None,
    attachments_summary: str | None = None,
) -> None:
    embed = discord.Embed(
        title="Deleted",
        color=discord.Color.red(),
        description=truncate(content, EMBED_DESC_MAX),
    )
    embed.add_field(name="User", value=f"<@{author_id}>", inline=True)
    embed.add_field(name="Channel", value=f"<#{source_channel_id}>", inline=True)
    embed.add_field(name="Message ID", value=f"`{message_id}`", inline=True)
    if attachments_summary:
        embed.add_field(
            name="Attachments",
            value=truncate(attachments_summary, FIELD_VALUE_MAX),
            inline=False,
        )
    await _send(bot, channel_id, embed)


async def post_edited(
    bot,
    channel_id: int,
    *,
    guild_id: int,
    message_id: int,
    author_id: int,
    source_channel_id: int,
    before: str | None,
    after: str | None,
) -> None:
    jump_url = (
        f"https://discord.com/channels/{guild_id}/{source_channel_id}/{message_id}"
    )
    embed = discord.Embed(title="Edited", url=jump_url, color=discord.Color.gold())
    embed.add_field(name="User", value=f"<@{author_id}>", inline=True)
    embed.add_field(name="Channel", value=f"<#{source_channel_id}>", inline=True)
    embed.add_field(
        name="Before", value=truncate(before, FIELD_VALUE_MAX), inline=False
    )
    embed.add_field(
        name="After", value=truncate(after, FIELD_VALUE_MAX), inline=False
    )
    await _send(bot, channel_id, embed)


async def post_attachment_removed(
    bot,
    channel_id: int,
    *,
    guild_id: int,
    message_id: int,
    author_id: int,
    source_channel_id: int,
    attachments_summary: str,
) -> None:
    jump_url = (
        f"https://discord.com/channels/{guild_id}/{source_channel_id}/{message_id}"
    )
    embed = discord.Embed(
        title="Attachment removed",
        url=jump_url,
        color=discord.Color.orange(),
        description="User edited a message to remove an attachment; the bot pulled the bytes before the CDN URL expired.",
    )
    embed.add_field(name="User", value=f"<@{author_id}>", inline=True)
    embed.add_field(name="Channel", value=f"<#{source_channel_id}>", inline=True)
    embed.add_field(
        name="Attachments",
        value=truncate(attachments_summary, FIELD_VALUE_MAX),
        inline=False,
    )
    await _send(bot, channel_id, embed)
