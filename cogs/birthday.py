import calendar
import json
import logging
import os
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands, tasks

BIRTHDAY_CHANNEL_ID = int(os.environ.get("BIRTHDAY_CHANNEL_ID", "0"))
TZ = ZoneInfo(os.environ.get("TIME_ZONE", "UTC"))
ANNOUNCE_TIME = time(hour=9, tzinfo=TZ)

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "birthdays.json"

log = logging.getLogger(__name__)


def load_birthdays() -> dict[str, dict]:
    if not DATA_FILE.exists():
        return {}
    return json.loads(DATA_FILE.read_text())


def save_birthdays(data: dict[str, dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2))


class BirthdayCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.daily_announce.start()

    def cog_unload(self) -> None:
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

        data = load_birthdays()
        data[str(interaction.user.id)] = {"month": month, "day": day}
        save_birthdays(data)

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
        target = user or interaction.user
        if target.id != interaction.user.id:
            perms = interaction.user.guild_permissions
            if not (perms.administrator or perms.manage_guild):
                await interaction.response.send_message(
                    "Only admins can remove someone else's birthday.",
                    ephemeral=True,
                )
                return

        data = load_birthdays()
        if data.pop(str(target.id), None) is None:
            await interaction.response.send_message(
                f"{target.display_name} has no birthday registered.",
                ephemeral=True,
            )
            return
        save_birthdays(data)

        msg = (
            "Removed your birthday."
            if target.id == interaction.user.id
            else f"Removed {target.display_name}'s birthday."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @birthday.command(name="show", description="Show a registered birthday")
    @app_commands.describe(user="Whose birthday to show; defaults to yourself")
    async def birthday_show(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ) -> None:
        target = user or interaction.user
        entry = load_birthdays().get(str(target.id))
        if entry is None:
            await interaction.response.send_message(
                f"{target.display_name} hasn't registered a birthday.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            f"{target.display_name}'s birthday: {entry['month']:02d}/{entry['day']:02d}.",
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
        # Feb-29 birthdays fall back to Feb 28 in non-leap years.
        feb29_falls_back = (
            today.month == 2 and today.day == 28 and not calendar.isleap(today.year)
        )
        for user_id, entry in load_birthdays().items():
            m, d = entry["month"], entry["day"]
            matches = (m == today.month and d == today.day) or (
                feb29_falls_back and m == 2 and d == 29
            )
            if matches:
                await channel.send(f"Happy birthday, <@{user_id}>!")

    @daily_announce.before_loop
    async def _wait_until_ready(self) -> None:
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(BirthdayCog(bot))
