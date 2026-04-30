# Features

Slash commands and automatic behaviors, per cog. For setup and deployment see [USAGE.md](./USAGE.md); for internal architecture see [CLAUDE.md](./CLAUDE.md).

After the bot connects for the first time it runs `tree.sync()`. Discord can take up to an hour to refresh the slash command list in your client — if commands are missing, give it time or kick + re-invite the bot.

## Birthday

| Command | Who | Effect |
|---|---|---|
| `/birthday set month:<1-12> day:<1-31>` | anyone | Register your birthday (overwrites any existing) |
| `/birthday show [user]` | anyone | Show yours, or another user's |
| `/birthday remove` | anyone | Remove your own |
| `/birthday remove user:<member>` | **Admin** (Administrator or Manage Server) | Remove someone else's |

The bot wishes you happy birthday at **09:00 in `TIME_ZONE`** in `BIRTHDAY_CHANNEL_ID`. Feb 29 entries fire on Feb 28 in non-leap years.

## Archive (Moderator only)

The `/archive` group is **hidden from every member by default** (`default_permissions=Permissions()`); the server admin grants the moderator role access once via Server Settings → Integrations → bot → /archive → Roles. See [USAGE.md § 4](./USAGE.md#4-grant-moderator-access-to-archive-one-time). Discord enforces the role gate at invocation time, so members without the role can neither see nor run the command.

| Command | Effect |
|---|---|
| `/archive deleted [user] [channel] [limit]` | List recent deleted messages, optionally filtered. Default limit 10, max 25. Ephemeral output |
| `/archive show <message_id>` | Full detail: original content, every edit revision, deletion timestamp, attachment status. Ephemeral output |
| `/archive get <message_id>` | Re-upload saved attachments as an ephemeral reply, with a per-file note for anything skipped, missing on disk, or not yet downloaded. Falls back to pointing at `data/attachments/<id>/` on the host if Discord rejects the upload size |

Independent of the commands, the bot posts a **live notice** in `MOD_LOG_CHANNEL_ID` every time a tracked message is edited (showing prior → new), has an attachment removed (eagerly downloads it before the CDN URL expires), or is deleted (showing the final content + any attachments).

Retention: **90 days from message creation**. The archive purges nightly at 03:00 in `TIME_ZONE` and removes both DB rows (cascading to edits and attachment metadata) and the on-disk attachment files at `data/attachments/<message_id>/`.

## Link embedder

No commands. When someone **posts or edits a message to add** a tracked link from a supported platform, the bot:

1. Cleans the platform's tracking params:
   - **Threads** (`threads.com` / `threads.net`): drops the entire `?…` query. Every threads link is reposted (even ones with no tracker) — Discord's threads embed re-fetches more reliably from a fresh post.
   - **Instagram** (`instagram.com`): drops only `igsh=…` from the query, keeping anything else like `img_index=2`. Plain IG links without `igsh` are left alone.
2. Deletes the original message
3. Reposts the cleaned link via a per-channel webhook, using the original poster's username and avatar — so Discord renders an embed preview
4. Adds ✅ and ❌ reactions on the repost

The **original poster** (and only the original poster) can:
- ✅ → confirm the repost. Bot clears all reactions; message stays as-is.
- ❌ → delete. Bot deletes the repost and posts a "Deleted" notice in `MOD_LOG_CHANNEL_ID`.

After **90 days** (matching the archive retention) the tracking row expires and the reactions stop being interactive — the message itself stays in chat indefinitely.

If the bot is missing **Manage Messages** in a channel, it falls back to keeping the original alongside the webhook repost (you'll see duplicates — that's the signal to fix the permission). If it's missing **Manage Webhooks**, the embedder is silently disabled in that channel.

The embedder also works **inside Discord threads** — the webhook is created on the parent channel and the cleaned message is posted into the thread via `webhook.send(thread=...)`. This requires **Send Messages in Threads** in addition to the permissions above.
