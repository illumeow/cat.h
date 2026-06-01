import logging
import os
from datetime import date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

from core import birthday_calendar

if TYPE_CHECKING:
    from bot import Bot

BIRTHDAY_CHANNEL_ID = int(os.environ.get("BIRTHDAY_CHANNEL_ID", "0"))
TZ = ZoneInfo(os.environ.get("TIME_ZONE", "UTC"))
ANNOUNCE_TIME = time(hour=0, tzinfo=TZ)

log = logging.getLogger(__name__)


class BirthdayCog(commands.Cog):
    def __init__(self, bot: "Bot") -> None:
        self.bot = bot
        self.daily_announce.start()

    async def cog_unload(self) -> None:
        self.daily_announce.cancel()

    birthday = app_commands.Group(
        name="birthday",
        description="Birthday commands",
        guild_only=True,
    )

    @birthday.command(name="set", description="Register your birthday")
    @app_commands.describe(month="Month (1-12)", day="Day (1-31)")
    async def birthday_set(
        self,
        interaction: discord.Interaction,
        month: app_commands.Range[int, 1, 12],
        day: app_commands.Range[int, 1, 31],
    ) -> None:
        try:
            # Year 2000 is a leap year, so Feb 29 validates as a real date.
            date(2000, month, day)
        except ValueError:
            await interaction.response.send_message(
                "That doesn't look like a real date — check the month/day combo.",
                ephemeral=True,
            )
            return

        await birthday_calendar.register(
            self.bot.db, interaction.user.id, month, day
        )
        await interaction.response.send_message(
            f"Registered. I'll wish you happy birthday on {month:02d}/{day:02d}.",
            ephemeral=True,
        )

    @birthday.command(
        name="remove",
        description="Remove a birthday (admin required when targeting someone else)",
    )
    @app_commands.describe(user="Whose birthday to remove; defaults to yourself")
    async def birthday_remove(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        # guild_only=True on the group means Discord rejects DM invocations,
        # so interaction.user is always a Member here. Pylance can't see that.
        target = user or interaction.user
        if target.id != interaction.user.id:
            perms = interaction.user.guild_permissions  # type: ignore
            if not (perms.administrator or perms.manage_guild):
                await interaction.response.send_message(
                    "Only admins can remove someone else's birthday.",
                    ephemeral=True,
                )
                return

        removed = await birthday_calendar.remove(self.bot.db, target.id)
        if not removed:
            await interaction.response.send_message(
                f"{target.display_name} has no birthday registered.",
                ephemeral=True,
            )
            return

        msg = (
            "Removed your birthday."
            if target.id == interaction.user.id
            else f"Removed {target.display_name}'s birthday."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @birthday.command(name="list", description="List everyone's registered birthdays")
    async def birthday_list(self, interaction: discord.Interaction) -> None:
        # guild_only=True on the group — guild is always present.
        guild = interaction.guild
        assert guild is not None
        entries = await birthday_calendar.list_all(self.bot.db)
        lines = [
            f"{bday.month:02d}/{bday.day:02d} — <@{user_id}>"
            for user_id, bday in entries
            if guild.get_member(user_id) is not None
        ]
        if not lines:
            await interaction.response.send_message(
                "No birthdays registered yet.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            "\n".join(lines),
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @birthday.command(name="show", description="Show a registered birthday")
    @app_commands.describe(user="Whose birthday to show; defaults to yourself")
    async def birthday_show(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        target = user or interaction.user
        bday = await birthday_calendar.get(self.bot.db, target.id)
        if bday is None:
            await interaction.response.send_message(
                f"{target.display_name} hasn't registered a birthday.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"{target.display_name}'s birthday: {bday.month:02d}/{bday.day:02d}.",
            ephemeral=True,
        )

    @tasks.loop(time=ANNOUNCE_TIME)
    async def daily_announce(self) -> None:
        today = datetime.now(TZ).date()
        channel = self.bot.get_channel(BIRTHDAY_CHANNEL_ID)
        if channel is None:
            log.warning(
                "Birthday channel %s not found or not cached yet", BIRTHDAY_CHANNEL_ID
            )
            return
        if not isinstance(channel, discord.abc.Messageable):
            log.warning(
                "Birthday channel %s is not a text channel; check BIRTHDAY_CHANNEL_ID",
                BIRTHDAY_CHANNEL_ID,
            )
            return
        user_ids = await birthday_calendar.users_with_birthday_on(self.bot.db, today)
        for user_id in user_ids:
            await channel.send(f"Happy birthday, <@{user_id}>!")

    @daily_announce.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: "Bot") -> None:
    await bot.add_cog(BirthdayCog(bot))
