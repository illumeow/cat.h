import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN", "")

EXTENSIONS = ("cogs.birthday",)

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        # command_prefix is unused (we only register slash commands) but is required.
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await self.tree.sync()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN env var (see .env.example).")
    logging.basicConfig(level=logging.INFO)
    Bot().run(TOKEN)


if __name__ == "__main__":
    main()
