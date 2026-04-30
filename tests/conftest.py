"""Shared pytest setup for the discord-bot tests.

The project's modules import from project root (e.g. `import mod_log`,
`from utils import parse_id_set`), and `cogs/*.py` does `from bot import
Bot` under TYPE_CHECKING. Add the project root to sys.path so tests can
import the same way the running bot does, without needing a package
install.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# --- Cog test helpers -------------------------------------------------
#
# Cogs read `self.bot.db` and a couple of cross-cog sets/dicts. They
# also start `@tasks.loop` jobs in `__init__`, which we don't want
# running during tests. The fixtures below give us:
#
#   - `fresh_db`: an in-memory aiosqlite connection with the bot's
#     schema applied (init_db's full pipeline minus the tempfile dance).
#   - `no_task_loops`: monkeypatches `tasks.Loop.start` to a no-op so
#     constructing a cog doesn't kick off background work.

import pytest_asyncio
import pytest


@pytest_asyncio.fixture
async def fresh_db():
    """An in-memory aiosqlite Connection with the production schema and
    migrations applied. Tests own the lifetime; fixture closes on exit."""
    import aiosqlite

    import db as db_module

    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys = ON;")
    await conn.executescript(db_module._SCHEMA)
    await db_module._migrate(conn)
    await conn.commit()
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture
def no_task_loops(monkeypatch):
    """Stop `@tasks.loop`-decorated methods from actually scheduling
    background tasks during cog construction. The cogs call
    `self.daily_purge.start()` (etc.) inside `__init__`; under tests we
    don't have a running event loop tied to a Discord gateway, so we
    just turn `start()` into a no-op."""
    from discord.ext import tasks

    monkeypatch.setattr(tasks.Loop, "start", lambda self, *a, **kw: None)
