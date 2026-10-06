# Graph Report - discord-bot  (2026-10-06)

## Corpus Check
- 23 files · ~119,916 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 521 nodes · 927 edges · 47 communities detected
- Extraction: 51% EXTRACTED · 49% INFERRED · 0% AMBIGUOUS · INFERRED: 456 edges (avg confidence: 0.72)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]

## God Nodes (most connected - your core abstractions)
1. `Bot` - 56 edges
2. `LinkEmbedderCog` - 53 edges
3. `record()` - 31 edges
4. `make_bot_stub` - 31 edges
5. `WebhookRepost` - 28 edges
6. `_rebuild_content()` - 16 edges
7. `AttachmentSpec` - 15 edges
8. `on_raw_message_edit()` - 14 edges
9. `Link embedder cog (LinkEmbedderCog)` - 14 edges
10. `download_pending()` - 13 edges

## Surprising Connections (you probably didn't know these)
- `post_deleted()` --calls--> `Archive cog (CLAUDE.md)`  [INFERRED]
  core/mod_log.py → CLAUDE.md
- `post_edited()` --calls--> `Archive cog (CLAUDE.md)`  [INFERRED]
  core/mod_log.py → CLAUDE.md
- `Bot` --uses--> `Build a cleaner that drops the named query params while preserving     the rest.`  [INFERRED]
  bot.py → cogs/link_embedder.py
- `Bot` --uses--> `Substitute every match of `pattern` in `text` with `cleaner(match)`.     Returns`  [INFERRED]
  bot.py → cogs/link_embedder.py
- `Bot` --uses--> `Apply each URL rule to the message text. Returns (rebuilt, urls) —     `urls` is`  [INFERRED]
  bot.py → cogs/link_embedder.py

## Hyperedges (group relationships)
- **Link embedder webhook repost flow** — claude_cog_link_embedder, claude_url_rules, claude_preview_sidecar, context_webhook_repost, context_original_poster [EXTRACTED 0.85]
- **Cross-cog handshakes between archive and link embedder** — claude_suppressed_deletes, claude_recent_edit_mod_logs, claude_cog_archive, claude_cog_link_embedder, claude_mod_log_builders [EXTRACTED 0.90]
- **Threads avatar/video embed fix: signals, helpers, sidecar fields** — design_avatar_signal, design_video_signal, design_is_threads_avatar_fallback, design_is_threads_video_frame, plan_task1_sidecar_fields [EXTRACTED 0.85]
- **Conditional distribution decomposition: joint = marginal * conditional** — 2026_hw6_0521_joint_density, 2026_hw6_0521_marginal_density, 2026_hw6_0521_conditional_density [INFERRED 0.85]
- **Bivariate normal conditional inference (regression line, conditional sd, standardized probability)** — 2026_hw6_0521_bivariate_normal, 2026_hw6_0521_regression_line, 2026_hw6_0521_conditional_variance, 2026_hw6_0521_normal_cdf [INFERRED 0.80]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.06
Nodes (57): AttachmentSpec, download_pending(), mark_deleted(), Input shape for `record` — one row's worth of attachment metadata     at archiva, Download any pending attachments for `message_id` to     `data/attachments/<mess, Atomically stamp `deleted_at` iff the row exists and the     column is NULL. Ret, _FakeGetCM, _FakeHttp (+49 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (48): make_bot_stub, LinkEmbedderCog, Ask the preview sidecar for OG metadata about `url`. Returns the         decoded, Hit the preview sidecar for each cleaned URL (in parallel) and         turn the, _build_text_message(), Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired, The ❌ reaction path must run `_finalize_repost` (which DELETEs     the webhook_r, The deleted_at-deferral fix relies on _finalize_repost stamping     `messages.de (+40 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (52): _apply_rule(), on_message(), on_raw_message_edit(), _plan_rewrite(), _preview_eligible_urls(), Build a cleaner that drops the named query params while preserving     the rest., Substitute every match of `pattern` in `text` with `cleaner(match)`.     Returns, Apply each URL rule to the message text. Returns (rebuilt, urls) —     `urls` is (+44 more)

### Community 3 - "Community 3"
Cohesion: 0.06
Nodes (46): bot.py entry point and EXTENSIONS toggles, Cloudflare challenge handling (CHALLENGE_WAIT_MS), Archive cog, Birthday cog, Link embedder cog (LinkEmbedderCog), One feature/task per commit, Discord threads handled transparently, Per-cog feature toggles via EXTENSIONS env vars (+38 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (40): Download any attachments for this message that haven't yet been         processe, Format the bullet list used in deletion / removal mod-log embeds         from th, Exclusion check that respects the parent-of-Discord-thread rule.         Used by, Format the bullet list used in deletion / removal mod-log         embeds from a, Bot, main(), _is_instagram_reel(), _is_threads_avatar_fallback() (+32 more)

### Community 5 - "Community 5"
Cohesion: 0.09
Nodes (33): daily_purge(), birthday_list(), birthday_remove(), birthday_set(), birthday_show(), BirthdayCog, Birthday, get() (+25 more)

### Community 6 - "Community 6"
Cohesion: 0.1
Nodes (27): archive_get(), archive_show(), ArchiveCog, _attachment_summary(), get_attachments(), _now(), on_message(), on_raw_message_delete() (+19 more)

### Community 7 - "Community 7"
Cohesion: 0.08
Nodes (33): Rationale: SQLite chosen over Postgres / per-feature JSON, ADR-0001: All bot state in a single SQLite file, ADR-0002: Archive uses full message logging, Rationale: full logging survives restarts vs cache-only snipe, Containerized deployment (Dockerfile + compose), Archive cog (CLAUDE.md), Birthday cog (CLAUDE.md), Deployment (Dockerfile + compose) (+25 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (26): Characterization tests for `core.utils`.  Pure functions: - `parse_id_set` — com, A regular TextChannel object isn't a Thread; the parent walk     must not fire e, test_blank_entries_between_commas_are_ignored(), test_duplicate_ids_are_deduplicated(), test_empty_string_returns_empty_set(), test_is_channel_or_parent_in_direct_match(), test_is_channel_or_parent_in_no_match(), test_is_channel_or_parent_in_non_thread_channel() (+18 more)

### Community 9 - "Community 9"
Cohesion: 0.1
Nodes (26): archive_deleted(), ArchivedMessage, Attachment, cutoff_ts(), DeletedListing, Edit, get(), get_edits() (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (21): Link embedder cog (CLAUDE.md), Preview sidecar (Node + Playwright), fresh_db fixture, Excluded channel (domain term), Original poster (domain term), Webhook repost (domain term), db.init_db, db._migrate (+13 more)

### Community 11 - "Community 11"
Cohesion: 0.2
Nodes (12): Bivariate Normal Distribution, Conditional Density h(y|x), f_{Y|X}, Conditional Expectation E[Y|X=x], Conditional Standard Deviation sigma_{Y|X}=sigma_Y*sqrt(1-rho^2), Correlation Coefficient rho, 2026 HW6 (Probability/Statistics Problem Set, 2026/5/21), Joint Probability Density Function f(x,y), Marginal Density f_X(x), f_Y(y) (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.29
Nodes (7): on_raw_message_delete(), on_raw_reaction_add(), Run when a tracked webhook repost is going away (❌ press, manual         delete, delete() of a non-existent webhook_message_id should not raise., test_delete_unknown_id_is_noop(), delete(), Drop the tracking row. Idempotent — DELETE on a missing row is a     no-op in SQ

### Community 13 - "Community 13"
Cohesion: 0.47
Nodes (4): help_command(), HelpCog, setup(), _supported_platforms()

### Community 14 - "Community 14"
Cohesion: 0.4
Nodes (6): Bimodal / U-shaped Distribution, Empty Mid-range (10-30, zero counts), High-value Peak (80-100, ~42-43 count), Histogram Chart, Score Distribution (0-100), Low-value Spike (0-10, ~26 count)

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (2): Bot entry point and cog loading, Environment (Python 3.14 + uv)

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): webhook_reposts table

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): messages table

### Community 18 - "Community 18"
Cohesion: 1.0
Nodes (1): attachments table

### Community 19 - "Community 19"
Cohesion: 1.0
Nodes (1): message_edits table

### Community 20 - "Community 20"
Cohesion: 1.0
Nodes (1): birthdays table

### Community 21 - "Community 21"
Cohesion: 1.0
Nodes (1): core.mod_log

### Community 22 - "Community 22"
Cohesion: 1.0
Nodes (1): mod_log.post_deleted

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): mod_log.post_edited

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): mod_log.post_attachment_removed

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): no_task_loops fixture

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Idempotent column additions for already-deployed databases. SQLite     has no AD

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Post an "Edited" mod-log notice. Returns the sent message so callers     that ne

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Parse a comma-separated list of integer IDs (typically from an env     var) into

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): Parse an env-var-style boolean. Unset (`None`) or empty falls back     to `defau

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): Shared pytest setup for the discord-bot tests.  The project's modules import fro

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): An in-memory aiosqlite Connection with the production schema and     migrations

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Stop `@tasks.loop`-decorated methods from actually scheduling     background tas

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): Build a minimal stand-in for `bot` that satisfies what the cogs     actually rea

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): Characterization tests for `db.init_db` and `db._migrate`.  Async because aiosql

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Point db.DATA_DIR / db.DB_PATH at a tempdir for this test only.     init_db() us

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (1): Dcard's rule has preview=False because Cloudflare blocks the     sidecar reliabl

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): YouTube's rule has preview=False because Discord's native player     embeds YouT

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Characterization tests for `mod_log.truncate`.  Pure function used to keep embed

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): suppressed_deletes cross-cog handshake

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): recent_edit_mod_logs cross-cog handshake

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Discord threads handling

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Troubleshooting guidance

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Oracle-specific gotchas (idle reclamation etc.)

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Project intent: incremental cogs, no upfront abstractions

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Environment: Python 3.14 + uv venv

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): /help command

## Knowledge Gaps
- **143 isolated node(s):** `Persistent record of Birthdays — the `birthdays` table interface.`, `True if a row was deleted; False if nothing matched.`, `All registered birthdays as (user_id, Birthday) sorted by (month, day).`, `User IDs whose Birthday falls on `today`; on non-leap Feb-28, also matches Feb-2`, `DATA_DIR / DB_PATH` (+138 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 15`** (2 nodes): `Bot entry point and cog loading`, `Environment (Python 3.14 + uv)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `webhook_reposts table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `messages table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 18`** (1 nodes): `attachments table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `message_edits table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (1 nodes): `birthdays table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 21`** (1 nodes): `core.mod_log`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 22`** (1 nodes): `mod_log.post_deleted`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `mod_log.post_edited`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `mod_log.post_attachment_removed`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `no_task_loops fixture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Idempotent column additions for already-deployed databases. SQLite     has no AD`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Post an "Edited" mod-log notice. Returns the sent message so callers     that ne`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Parse a comma-separated list of integer IDs (typically from an env     var) into`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `Parse an env-var-style boolean. Unset (`None`) or empty falls back     to `defau`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `Shared pytest setup for the discord-bot tests.  The project's modules import fro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `An in-memory aiosqlite Connection with the production schema and     migrations`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Stop `@tasks.loop`-decorated methods from actually scheduling     background tas`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `Build a minimal stand-in for `bot` that satisfies what the cogs     actually rea`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `Characterization tests for `db.init_db` and `db._migrate`.  Async because aiosql`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `Point db.DATA_DIR / db.DB_PATH at a tempdir for this test only.     init_db() us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (1 nodes): `Dcard's rule has preview=False because Cloudflare blocks the     sidecar reliabl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `YouTube's rule has preview=False because Discord's native player     embeds YouT`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Characterization tests for `mod_log.truncate`.  Pure function used to keep embed`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `suppressed_deletes cross-cog handshake`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `recent_edit_mod_logs cross-cog handshake`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Discord threads handling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Troubleshooting guidance`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Oracle-specific gotchas (idle reclamation etc.)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Project intent: incremental cogs, no upfront abstractions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Environment: Python 3.14 + uv venv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `/help command`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bot` connect `Community 4` to `Community 1`, `Community 2`, `Community 5`, `Community 6`, `Community 8`, `Community 9`, `Community 10`, `Community 12`, `Community 13`?**
  _High betweenness centrality (0.226) - this node is a cross-community bridge._
- **Why does `LinkEmbedderCog` connect `Community 1` to `Community 9`, `Community 2`, `Community 12`, `Community 4`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `webhook_reposts table` connect `Community 10` to `Community 7`?**
  _High betweenness centrality (0.114) - this node is a cross-community bridge._
- **Are the 50 inferred relationships involving `Bot` (e.g. with `LinkEmbedderCog` and `Build a cleaner that drops the named query params while preserving     the rest.`) actually correct?**
  _`Bot` has 50 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `LinkEmbedderCog` (e.g. with `Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired` and `A MagicMock shaped like the `discord.Message` attributes the     link embedder r`) actually correct?**
  _`LinkEmbedderCog` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `record()` (e.g. with `test_record_inserts_row()` and `test_record_accepts_null_original_message_id()`) actually correct?**
  _`record()` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `make_bot_stub` (e.g. with `Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired` and `A MagicMock shaped like the `discord.Message` attributes the     link embedder r`) actually correct?**
  _`make_bot_stub` has 31 INFERRED edges - model-reasoned connections that need verification._