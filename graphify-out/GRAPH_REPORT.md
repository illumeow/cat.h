# Graph Report - /Users/illumeow/Developer/discord-bot  (2026-05-02)

## Corpus Check
- Corpus is ~19,193 words - fits in a single context window. You may not need a graph.

## Summary
- 299 nodes · 560 edges · 17 communities detected
- Extraction: 77% EXTRACTED · 23% INFERRED · 0% AMBIGUOUS · INFERRED: 127 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_URL Rule Engine|URL Rule Engine]]
- [[_COMMUNITY_Link Embedder Cog|Link Embedder Cog]]
- [[_COMMUNITY_Archive Cog Internals|Archive Cog Internals]]
- [[_COMMUNITY_Test Fixtures & DB Schema|Test Fixtures & DB Schema]]
- [[_COMMUNITY_Env Parsing Utilities|Env Parsing Utilities]]
- [[_COMMUNITY_Architecture Decisions & Domain|Architecture Decisions & Domain]]
- [[_COMMUNITY_Bot Bootstrap & Deployment|Bot Bootstrap & Deployment]]
- [[_COMMUNITY_Mod-log Embeds|Mod-log Embeds]]
- [[_COMMUNITY_Birthday Cog|Birthday Cog]]
- [[_COMMUNITY_Bot Entrypoint & Preview Sidecar|Bot Entrypoint & Preview Sidecar]]
- [[_COMMUNITY_Link Embedder Concepts|Link Embedder Concepts]]
- [[_COMMUNITY_Discord Threads|Discord Threads]]
- [[_COMMUNITY_Discord App Setup|Discord App Setup]]
- [[_COMMUNITY_Troubleshooting|Troubleshooting]]
- [[_COMMUNITY_Oracle Idle Reclamation Note|Oracle Idle Reclamation Note]]
- [[_COMMUNITY_core.mod_log module|core.mod_log module]]
- [[_COMMUNITY_no_task_loops fixture|no_task_loops fixture]]

## God Nodes (most connected - your core abstractions)
1. `LinkEmbedderCog` - 32 edges
2. `Bot` - 26 edges
3. `_rebuild_content()` - 20 edges
4. `ArchiveCog` - 16 edges
5. `on_raw_message_edit()` - 15 edges
6. `on_raw_message_delete()` - 14 edges
7. `init_db()` - 13 edges
8. `URL_RULES` - 13 edges
9. `truncate()` - 12 edges
10. `parse_id_set()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `Persistence (single SQLite file)` --references--> `init_db()`  [EXTRACTED]
  CLAUDE.md → /Users/illumeow/Developer/discord-bot/core/db.py
- `Archive cog (CLAUDE.md)` --calls--> `post_deleted()`  [INFERRED]
  CLAUDE.md → /Users/illumeow/Developer/discord-bot/core/mod_log.py
- `Archive cog (CLAUDE.md)` --calls--> `post_edited()`  [INFERRED]
  CLAUDE.md → /Users/illumeow/Developer/discord-bot/core/mod_log.py
- `Bot entry point and cog loading` --implements--> `Bot (commands.Bot subclass)`  [INFERRED]
  CLAUDE.md → bot.py
- `EXTENSIONS feature toggles` --references--> `parse_bool_env()`  [EXTRACTED]
  CLAUDE.md → /Users/illumeow/Developer/discord-bot/core/utils.py

## Hyperedges (group relationships)
- **Cross-cog in-memory handshake pattern (suppressed_deletes + recent_edit_mod_logs)** — bot_suppressed_deletes_attr, bot_recent_edit_mod_logs_attr, claude_md_archive_cog, claude_md_link_embedder_cog [EXTRACTED 0.90]
- **Shared mod-log embed builders used by archive and link embedder** — mod_log_post_deleted, mod_log_post_edited, mod_log_post_attachment_removed, claude_md_archive_cog, claude_md_link_embedder_cog [INFERRED 0.85]
- **All cog state lives in one SQLite file (single-DB pattern)** — db_init_db, db_table_birthdays, db_table_messages, db_table_webhook_reposts, adr_0001_sqlite_for_all_state [EXTRACTED 0.95]
- **Cross-cog delete handshake (link embedder + archive + mod_log)** — link_embedder_process_message, link_embedder_finalize_repost, archive_on_raw_message_delete, bot_suppressed_deletes_set, core_mod_log_post_deleted [EXTRACTED 0.95]
- **Edit-rewrite mod-log retargeting handshake** — archive_on_raw_message_edit, core_mod_log_post_edited, bot_recent_edit_mod_logs_dict, link_embedder_process_message, link_embedder_retarget_edit_mod_log [EXTRACTED 0.90]
- **Webhook repost lifecycle (insert before delete; finalize before delete-of-webhook)** — link_embedder_process_message, link_embedder_on_raw_reaction_add, link_embedder_on_raw_message_delete, link_embedder_finalize_repost, link_embedder_webhook_reposts_table [EXTRACTED 0.95]

## Communities

### Community 0 - "URL Rule Engine"
Cohesion: 0.05
Nodes (62): _apply_rule(), _preview_eligible_urls(), Build a cleaner that drops a single query param while preserving     the rest. U, Substitute every match of `pattern` in `text` with `cleaner(match)`.     Returns, Apply each URL rule to the message text. Returns (rebuilt, urls) —     `urls` is, Cleaned URLs in `content` that belong to rules with preview=True.      This re-r, Cap a Discord embed field at `limit` characters with an ellipsis;     return Non, Drop the entire `?…` query string. (+54 more)

### Community 1 - "Link Embedder Cog"
Cohesion: 0.09
Nodes (34): bot.recent_edit_mod_logs, make_bot_stub(), Build a minimal stand-in for `bot` that satisfies what the cogs     actually rea, LinkEmbedderCog._build_preview_embeds, LinkEmbedderCog._fetch_preview, LinkEmbedderCog._get_webhook, _is_instagram_reel(), LinkEmbedderCog (+26 more)

### Community 2 - "Archive Cog Internals"
Cohesion: 0.1
Nodes (26): archive_get(), ArchiveCog, ArchiveCog._attachment_summary, attachments table, ArchiveCog._download_attachments, message_edits table, messages table, _now() (+18 more)

### Community 3 - "Test Fixtures & DB Schema"
Cohesion: 0.14
Nodes (24): fresh_db(), fresh_db fixture, no_task_loops(), Shared pytest setup for the discord-bot tests.  The project's modules import fro, An in-memory aiosqlite Connection with the production schema and     migrations, Stop `@tasks.loop`-decorated methods from actually scheduling     background tas, db.init_db, db._migrate (+16 more)

### Community 4 - "Env Parsing Utilities"
Cohesion: 0.19
Nodes (21): parse_bool_env, parse_id_set, Characterization tests for `core.utils`.  Pure functions: - `parse_id_set` — com, test_blank_entries_between_commas_are_ignored(), test_duplicate_ids_are_deduplicated(), test_empty_string_returns_empty_set(), test_mixed_valid_invalid_keeps_only_valid(), test_multiple_ids_parse_to_set() (+13 more)

### Community 5 - "Architecture Decisions & Domain"
Cohesion: 0.12
Nodes (23): Rationale: SQLite chosen over Postgres / per-feature JSON, ADR-0001: All bot state in a single SQLite file, ADR-0002: Archive uses full message logging, Rationale: full logging survives restarts vs cache-only snipe, Archive cog (CLAUDE.md), Birthday cog (CLAUDE.md), Persistence (single SQLite file), Project intent (incremental, no master spec) (+15 more)

### Community 6 - "Bot Bootstrap & Deployment"
Cohesion: 0.1
Nodes (21): Bot (commands.Bot subclass), Bot.close, EXTENSIONS tuple, Bot.recent_edit_mod_logs attribute, Bot.setup_hook, Bot.suppressed_deletes attribute, Bot entry point and cog loading, Deployment (Dockerfile + compose) (+13 more)

### Community 7 - "Mod-log Embeds"
Cohesion: 0.23
Nodes (16): archive_deleted(), archive_show(), mod_log.truncate, post_attachment_removed(), post_deleted(), post_edited(), Post an "Edited" mod-log notice. Returns the sent message so callers     that ne, _send() (+8 more)

### Community 8 - "Birthday Cog"
Cohesion: 0.21
Nodes (9): daily_purge(), birthday_remove(), birthday_set(), birthday_show(), BirthdayCog, birthdays table, daily_announce(), setup() (+1 more)

### Community 9 - "Bot Entrypoint & Preview Sidecar"
Cohesion: 0.18
Nodes (8): Bot, main(), Exclusion check that respects the parent-of-Discord-thread rule.         Listing, Ask the preview sidecar for OG metadata about `url`. Returns the         decoded, Hit the preview sidecar for each cleaned URL (in parallel) and         turn the, Apply URL rules to `message.content`; if any rule matched,         replace the m, Edit the previously-posted "Edited" mod-log notice so its embed         URL poin, Catch deletions of a tracked webhook repost from any source —         the ❌ reac

### Community 10 - "Link Embedder Concepts"
Cohesion: 0.38
Nodes (7): Link embedder cog (CLAUDE.md), Preview sidecar (Node + Playwright), Original poster concept, Webhook repost concept, webhook_reposts table, Link embedder automatic behavior, Link embedder feature (README)

### Community 13 - "Discord Threads"
Cohesion: 1.0
Nodes (1): Discord threads handling

### Community 14 - "Discord App Setup"
Cohesion: 1.0
Nodes (1): Create the Discord application

### Community 15 - "Troubleshooting"
Cohesion: 1.0
Nodes (1): Troubleshooting guidance

### Community 16 - "Oracle Idle Reclamation Note"
Cohesion: 1.0
Nodes (1): Oracle-specific gotchas (idle reclamation etc.)

### Community 17 - "core.mod_log module"
Cohesion: 1.0
Nodes (1): core.mod_log

### Community 18 - "no_task_loops fixture"
Cohesion: 1.0
Nodes (1): no_task_loops fixture

## Knowledge Gaps
- **46 isolated node(s):** `Idempotent column additions for already-deployed databases. SQLite     has no AD`, `Post an "Edited" mod-log notice. Returns the sent message so callers     that ne`, `Parse a comma-separated list of integer IDs (typically from an env     var) into`, `Parse an env-var-style boolean. Unset (`None`) or empty falls back     to `defau`, `Characterization tests for `core.utils`.  Pure functions: - `parse_id_set` — com` (+41 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Discord Threads`** (1 nodes): `Discord threads handling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Discord App Setup`** (1 nodes): `Create the Discord application`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Troubleshooting`** (1 nodes): `Troubleshooting guidance`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Oracle Idle Reclamation Note`** (1 nodes): `Oracle-specific gotchas (idle reclamation etc.)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `core.mod_log module`** (1 nodes): `core.mod_log`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `no_task_loops fixture`** (1 nodes): `no_task_loops fixture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bot` connect `Bot Entrypoint & Preview Sidecar` to `URL Rule Engine`, `Link Embedder Cog`, `Archive Cog Internals`, `Test Fixtures & DB Schema`, `Birthday Cog`?**
  _High betweenness centrality (0.354) - this node is a cross-community bridge._
- **Why does `LinkEmbedderCog` connect `Link Embedder Cog` to `URL Rule Engine`, `Bot Entrypoint & Preview Sidecar`, `Test Fixtures & DB Schema`, `Env Parsing Utilities`?**
  _High betweenness centrality (0.247) - this node is a cross-community bridge._
- **Why does `parse_bool_env()` connect `Env Parsing Utilities` to `Bot Entrypoint & Preview Sidecar`, `Bot Bootstrap & Deployment`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Are the 17 inferred relationships involving `LinkEmbedderCog` (e.g. with `Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired` and `A MagicMock shaped like the `discord.Message` attributes the     link embedder r`) actually correct?**
  _`LinkEmbedderCog` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Bot` (e.g. with `LinkEmbedderCog` and `Drop the entire `?…` query string.`) actually correct?**
  _`Bot` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `ArchiveCog` (e.g. with `Cog-level tests for the archive cog.  These tests construct a real `ArchiveCog`` and `If `interaction.followup.send` raises an exception type other     than discord.H`) actually correct?**
  _`ArchiveCog` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `on_raw_message_edit()` (e.g. with `post_attachment_removed()` and `post_edited()`) actually correct?**
  _`on_raw_message_edit()` has 3 INFERRED edges - model-reasoned connections that need verification._