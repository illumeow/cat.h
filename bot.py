import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

import db

load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN", "")

EXTENSIONS = (
    "cogs.birthday",
    "cogs.archive",
    "cogs.threads",
)

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        # command_prefix is unused (we only register slash commands) but is required.
        super().__init__(command_prefix="!", intents=intents)
        # Cross-cog handshake: when one cog deletes a message it owns (e.g.
        # threads cog rewriting a link), it adds the ID here so the archive
        # cog skips the corresponding on_raw_message_delete event.
        self.suppressed_deletes: set[int] = set()
        self.db = None  # type: ignore[assignment]  # set in setup_hook

    async def setup_hook(self) -> None:
        self.db = await db.init_db()
        for ext in EXTENSIONS:
            await self.load_extension(ext)
        await self.tree.sync()

    async def close(self) -> None:
        if self.db is not None:
            await self.db.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("Logged in as %s", self.user)


def main() -> None:
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN env var (see .env.example).")
    logging.basicConfig(level=logging.INFO)
    Bot().run(TOKEN)


if __name__ == "__main__":
    main()
