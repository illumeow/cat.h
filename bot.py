import logging
import os

import aiosqlite
import discord
from discord.ext import commands
from dotenv import load_dotenv

from core import db
from core.utils import parse_bool_env

load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN", "")

# (dotted-path, env-var that gates loading). All default-enabled; an
# operator opts out per cog by setting the var to `false`/`no`/`0`/`off`
# in `.env`. Disabled cogs are skipped at startup — none of their event
# listeners, slash commands, or task loops register, so they're truly
# inert (a restart is needed to flip them back).
EXTENSIONS: tuple[tuple[str, str], ...] = (
    ("cogs.birthday", "BIRTHDAY_ENABLED"),
    ("cogs.archive", "ARCHIVE_ENABLED"),
    ("cogs.link_embedder", "LINK_EMBEDDER_ENABLED"),
)

log = logging.getLogger(__name__)


class Bot(commands.Bot):
    # Set in setup_hook before any cog touches them. Class-level annotations
    # (no value) so Pylance treats them as known attributes; we use hasattr
    # in close() in case startup aborts before setup_hook runs.
    db: aiosqlite.Connection
    suppressed_deletes: set[int]
    recent_edit_mod_logs: dict[int, int]

    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        # command_prefix is unused (we only register slash commands) but is required.
        super().__init__(command_prefix="!", intents=intents)
        # Cross-cog handshake: when one cog deletes a message it owns (e.g.
        # the link embedder rewriting a tracked URL), it adds the ID here
        # so the archive cog skips the mod-log notice for that delete.
        self.suppressed_deletes = set()
        # Cross-cog handshake: archive maps original_message_id →
        # mod_log_message_id after posting an "Edited" notice; the link
        # embedder pops it post-rewrite to re-target the embed's jump URL
        # at the webhook repost (the original is gone by then). Bounded by
        # archive's own eviction.
        self.recent_edit_mod_logs = {}

    async def setup_hook(self) -> None:
        self.db = await db.init_db()
        for ext, flag in EXTENSIONS:
            if not parse_bool_env(os.environ.get(flag), default=True):
                log.info("Skipping %s (disabled via %s)", ext, flag)
                continue
            await self.load_extension(ext)
        await self.tree.sync()

    async def close(self) -> None:
        if hasattr(self, "db"):
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
