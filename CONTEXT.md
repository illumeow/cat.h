# Discord bot

A personal Discord bot for one server. Features are added one cog at a time. This document defines the language used across the project so that domain terms mean the same thing in code, docs, and conversation.

## Language

**Birthday**:
A month/day pair registered by a Discord user; the bot announces it once per year in the configured birthday channel.
_Avoid_: "DOB", "birth date" (no year is stored).

**Archive**:
The bot's persistent record of every message it sees in non-excluded channels. Includes the original content, every edit, and a deletion timestamp once the message is deleted. Storage is bounded — entries are evicted 90 days after the message's creation timestamp.
_Avoid_: "log", "history" (overloaded).

**Mod-log**:
The single channel (`MOD_LOG_CHANNEL_ID`) where the bot posts a real-time notice every time a tracked message is edited or deleted. Distinct from the Archive — the mod-log is a live audit feed; the Archive is queryable storage.
_Avoid_: "audit log" (Discord uses that for its own concept), "log channel".

**Moderator**:
A user with a Discord role that has been granted access to the `/archive` group via Server Settings → Integrations → bot → /archive → Roles. The `/archive` group is hidden from every member by default; the role override is the sole authorization gate, enforced server-side by Discord. Distinct from "admin".
_Avoid_: "mod", "trusted user".

**Admin**:
A user with the Discord-permission bits `Administrator` or `Manage Server` in the current guild. Used for touching another user's personal data (e.g. `/birthday remove <user>`). Higher bar than Moderator.
_Avoid_: conflating with Moderator.

**Excluded channel**:
A channel ID listed in `ARCHIVE_EXCLUDED_CHANNELS` (or in the cog-specific `LINK_EMBEDDER_EXCLUDED_CHANNELS`). The Archive (resp. Link embedder) feature does nothing in that channel. The Mod-log channel is auto-excluded from both without needing to be listed.

**Webhook repost**:
The bot's replacement for a user message that contained a tracked link from a supported platform (currently `threads.com` / `threads.net`, where the whole query is stripped; `instagram.com` URLs carrying an `?igsh=…` share tracker, where only `igsh` is removed; and `dcard.tw` URLs carrying a `?cid=…` campaign tracker, where only `cid` is removed). The original is deleted; a webhook posts the cleaned version under the original poster's username and avatar. Tracked in the `webhook_reposts` table for 90 days (same window as the archive) so reactions can drive confirm/delete even on older posts; the row remembers the user's original message ID so a later ❌ surfaces an `/archive show`-able ID in the mod-log "Deleted" notice (the webhook repost itself isn't archived).
_Avoid_: "rewrite", "fix" (vague).

**Original poster**:
The human author of the message that the Threads cog deleted to produce a Webhook repost. Identified by Discord user ID. The only user whose ✅ / ❌ reaction on the Webhook repost the bot acts on.

## Relationships

- A **User** has zero or one **Birthday**.
- An **Archive** entry belongs to one **User** (author) and one **Channel**, and has zero-or-more edit revisions and zero-or-more downloaded attachments.
- A **Webhook repost** has exactly one **Original poster** and lives as an interactive object (reactions) for the same 90-day window as the archive; the message itself stays in chat indefinitely.
- The **Mod-log** receives notices from the Archive cog (edits / deletions) and the Threads cog (✗ deletions of webhook reposts).
- The **Mod-log channel** is implicitly an Excluded channel for the Archive (no recursion).

## Example dialogue

> **You:** "Did Alice delete that message right after sending it?"
> **Bot author:** "Check the **Mod-log** — every delete shows up there live. If it's older, run `/archive deleted user:@Alice` from the **Moderator** allowlist."
> **You:** "Can a regular **Admin** see the archive?"
> **Bot author:** "No. **Admin** is the gate for personal-data actions like removing someone else's **Birthday**. The Archive is **Moderator**-only — different list, different bar."

## Flagged ambiguities

- "moderator" vs "admin" — **resolved**: Moderator is the Discord role granted access to `/archive` via the Integrations UI; Admin is the Discord-permission concept (`Administrator` / `Manage Server`). The two gates protect different things on purpose: Moderator gates audit-log access; Admin gates editing other users' personal data.
- "log" alone is ambiguous (could mean the Archive table, the Mod-log channel, or stdout). **Resolved**: always say "Archive" or "Mod-log"; reserve "log" / "logging" for stdout / `logging` module output.
