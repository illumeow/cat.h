# All bot state in a single SQLite file

The bot started with `data/birthdays.json`. When the second feature (a deleted-message Archive) needed real persistent storage, we considered keeping per-feature files (more JSON or a new SQLite per cog) and adding Postgres as a service. We picked **one SQLite file (`data/bot.db`) for every cog's state**, accessed via `aiosqlite` and a shared `db.py` helper.

Why: SQLite handles the projected workload (one server, low concurrency, tens of millions of rows tops) without needing a second container, single-file backups, and avoids the "split-brain" of having some state in JSON and some in a database. Postgres would have added a second service to the Docker compose for no benefit at this scale. Per-feature files would multiply the surface area for backup, migration, and Docker volume mounts as more cogs land.

Trade-off accepted: schema changes require explicit `ALTER TABLE` (no migration framework), and concurrent writers are not supported — fine because the bot is the only writer.
