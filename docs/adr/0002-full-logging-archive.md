# Archive uses full message logging, not in-memory cache

Most "snipe-style" bots only persist a message at the moment it is deleted, by reading from discord.py's in-memory cache (default ~1000 most recent messages). That works while the bot is up, but loses everything sent before the most recent restart — gateway `MESSAGE_DELETE` payloads carry only the message ID, not its content.

We instead **write every visible message to `messages` on `on_message`** (and every edit to `message_edits`), then mark a row deleted on `on_message_delete`. The Archive is the source of truth; the in-memory cache is irrelevant.

Why: the bot will restart (deploys, hosting reboots, crashes) and we want the Archive to survive those events without holes. With cache-only, a message sent at 09:00 and deleted at 09:30 across a 09:15 restart is unrecoverable; with full logging, the row is already on disk. Storage is bounded by the 90-day creation-time TTL (ADR-0001's SQLite handles this volume comfortably).

Trade-off accepted: we persist *every* message, not just deleted ones, which is a stronger privacy footprint than cache-only. Mitigations: `ARCHIVE_EXCLUDED_CHANNELS` carves out sensitive channels, the Mod-log channel is auto-excluded, the bot ignores DMs entirely, and 90 days is a hard ceiling on retention.
