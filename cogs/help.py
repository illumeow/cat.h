import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from cogs.link_embedder import URL_RULES

if TYPE_CHECKING:
    from bot import Bot

log = logging.getLogger(__name__)

# Display overrides for rule names that don't title-case cleanly. Anything
# missing falls back to .capitalize(), so a new URL_RULES entry shows up in
# /help automatically without needing a touch here.
_PLATFORM_DISPLAY_NAMES: dict[str, str] = {
    "youtube": "YouTube",
}


def _supported_platforms() -> str:
    names = [
        _PLATFORM_DISPLAY_NAMES.get(name, name.capitalize())
        for name, *_ in URL_RULES
    ]
    return ", ".join(f"**{n}**" for n in names)


class HelpCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot

    @app_commands.command(
        name="help",
        description="Show available commands and what the bot does",
    )
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(
            title="Bot help",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Birthday",
            value=(
                "• `/birthday set month:<1-12> day:<1-31>` — register your birthday\n"
                "• `/birthday show [user]` — show yours, or another user's\n"
                "• `/birthday remove` — remove your own\n"
                "\n"
                "On your birthday I'll send a happy-birthday message in the "
                "configured channel at 09:00 (server timezone)."
            ),
            inline=False,
        )
        embed.add_field(
            name="Link cleaner",
            value=(
                "No commands — it runs automatically. When you post (or edit "
                "in) a link from a supported platform, I repost it under your "
                "name with the tracking parameters stripped, and add a cleaner "
                "embed where the platform's default one is broken.\n"
                f"Supported: {_supported_platforms()}.\n"
                "\n"
                "On the repost, only **you** (the original poster) can react:\n"
                "• ✅ keep the repost as-is (clears the reactions)\n"
                "• ❌ delete the repost"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: "Bot") -> None:
    await bot.add_cog(HelpCog(bot))
