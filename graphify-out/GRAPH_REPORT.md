# Graph Report - .  (2026-06-01)

## Corpus Check
- Corpus is ~31,978 words - fits in a single context window. You may not need a graph.

## Summary
- 504 nodes · 835 edges · 60 communities detected
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 374 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Archive Attachment Vault|Archive Attachment Vault]]
- [[_COMMUNITY_Link Embedder Cog|Link Embedder Cog]]
- [[_COMMUNITY_Archive Cog Handlers|Archive Cog Handlers]]
- [[_COMMUNITY_Architecture Overview (CLAUDE.md)|Architecture Overview (CLAUDE.md)]]
- [[_COMMUNITY_Bot Core & Mod-log Helpers|Bot Core & Mod-log Helpers]]
- [[_COMMUNITY_Birthday Cog|Birthday Cog]]
- [[_COMMUNITY_Utils & Channel-exclusion Tests|Utils & Channel-exclusion Tests]]
- [[_COMMUNITY_ADRs & Persistence Rationale|ADRs & Persistence Rationale]]
- [[_COMMUNITY_DB Init & Domain Terms|DB Init & Domain Terms]]
- [[_COMMUNITY_URL Rule Rewriting & Tests|URL Rule Rewriting & Tests]]
- [[_COMMUNITY_Threads Embed Fix (planspec)|Threads Embed Fix (plan/spec)]]
- [[_COMMUNITY_HW6 Probability Problem Set|HW6 Probability Problem Set]]
- [[_COMMUNITY_Embed Truncation Helper|Embed Truncation Helper]]
- [[_COMMUNITY_Score Histogram Image|Score Histogram Image]]
- [[_COMMUNITY_Bot Entry & Environment|Bot Entry & Environment]]
- [[_COMMUNITY_webhook_reposts table|webhook_reposts table]]
- [[_COMMUNITY_messages table|messages table]]
- [[_COMMUNITY_attachments table|attachments table]]
- [[_COMMUNITY_message_edits table|message_edits table]]
- [[_COMMUNITY_birthdays table|birthdays table]]
- [[_COMMUNITY_core.mod_log module|core.mod_log module]]
- [[_COMMUNITY_post_deleted|post_deleted]]
- [[_COMMUNITY_post_edited|post_edited]]
- [[_COMMUNITY_post_attachment_removed|post_attachment_removed]]
- [[_COMMUNITY_no_task_loops fixture|no_task_loops fixture]]
- [[_COMMUNITY_strip_query full-query test|strip_query full-query test]]
- [[_COMMUNITY_strip_query no-query test|strip_query no-query test]]
- [[_COMMUNITY_strip_query bare- test|strip_query bare-? test]]
- [[_COMMUNITY_instagram regex test|instagram regex test]]
- [[_COMMUNITY_threads regex test|threads regex test]]
- [[_COMMUNITY_dcard cid match test|dcard cid match test]]
- [[_COMMUNITY_dcard cid no-match test|dcard cid no-match test]]
- [[_COMMUNITY_dcard www test|dcard www test]]
- [[_COMMUNITY_youtube si short-link test|youtube si short-link test]]
- [[_COMMUNITY_youtube si watch test|youtube si watch test]]
- [[_COMMUNITY_youtube si subdomain test|youtube si subdomain test]]
- [[_COMMUNITY_youtube si clean test|youtube si clean test]]
- [[_COMMUNITY_youtube si false-match test|youtube si false-match test]]
- [[_COMMUNITY_Idempotent column migrations|Idempotent column migrations]]
- [[_COMMUNITY_post_edited docstring|post_edited docstring]]
- [[_COMMUNITY_parse_id_set|parse_id_set]]
- [[_COMMUNITY_parse_bool_env|parse_bool_env]]
- [[_COMMUNITY_conftest setup|conftest setup]]
- [[_COMMUNITY_fresh_db fixture|fresh_db fixture]]
- [[_COMMUNITY_task-loop suppression|task-loop suppression]]
- [[_COMMUNITY_bot stub builder|bot stub builder]]
- [[_COMMUNITY_db.init_db tests|db.init_db tests]]
- [[_COMMUNITY_db tempdir fixture|db tempdir fixture]]
- [[_COMMUNITY_URL rewrite test suite|URL rewrite test suite]]
- [[_COMMUNITY_Dcard preview=False rationale|Dcard preview=False rationale]]
- [[_COMMUNITY_YouTube preview=False rationale|YouTube preview=False rationale]]
- [[_COMMUNITY_mod_log.truncate tests|mod_log.truncate tests]]
- [[_COMMUNITY_suppressed_deletes handshake|suppressed_deletes handshake]]
- [[_COMMUNITY_recent_edit_mod_logs handshake|recent_edit_mod_logs handshake]]
- [[_COMMUNITY_Discord threads handling|Discord threads handling]]
- [[_COMMUNITY_Troubleshooting guidance|Troubleshooting guidance]]
- [[_COMMUNITY_Oracle gotchas|Oracle gotchas]]
- [[_COMMUNITY_Project intent|Project intent]]
- [[_COMMUNITY_Environment Python 3.14|Environment Python 3.14]]
- [[_COMMUNITY_help command|/help command]]

## God Nodes (most connected - your core abstractions)
1. `LinkEmbedderCog` - 43 edges
2. `Bot` - 42 edges
3. `record()` - 31 edges
4. `make_bot_stub` - 20 edges
5. `WebhookRepost` - 19 edges
6. `_rebuild_content()` - 18 edges
7. `AttachmentSpec` - 15 edges
8. `Link embedder cog (LinkEmbedderCog)` - 14 edges
9. `download_pending()` - 13 edges
10. `parse_id_set()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `birthdays table` --shares_data_with--> `Birthday cog (CLAUDE.md)`  [INFERRED]
  core/db.py → CLAUDE.md
- `messages table` --shares_data_with--> `Archive cog (CLAUDE.md)`  [INFERRED]
  core/db.py → CLAUDE.md
- `messages table` --shares_data_with--> `ADR-0002: Archive uses full message logging`  [INFERRED]
  core/db.py → docs/adr/0002-full-logging-archive.md
- `message_edits table` --shares_data_with--> `Archive cog (CLAUDE.md)`  [INFERRED]
  core/db.py → CLAUDE.md
- `message_edits table` --shares_data_with--> `ADR-0002: Archive uses full message logging`  [INFERRED]
  core/db.py → docs/adr/0002-full-logging-archive.md

## Hyperedges (group relationships)
- **Link embedder webhook repost flow** — claude_cog_link_embedder, claude_url_rules, claude_preview_sidecar, context_webhook_repost, context_original_poster [EXTRACTED 0.85]
- **Cross-cog handshakes between archive and link embedder** — claude_suppressed_deletes, claude_recent_edit_mod_logs, claude_cog_archive, claude_cog_link_embedder, claude_mod_log_builders [EXTRACTED 0.90]
- **Threads avatar/video embed fix: signals, helpers, sidecar fields** — design_avatar_signal, design_video_signal, design_is_threads_avatar_fallback, design_is_threads_video_frame, plan_task1_sidecar_fields [EXTRACTED 0.85]
- **Conditional distribution decomposition: joint = marginal * conditional** — 2026_hw6_0521_joint_density, 2026_hw6_0521_marginal_density, 2026_hw6_0521_conditional_density [INFERRED 0.85]
- **Bivariate normal conditional inference (regression line, conditional sd, standardized probability)** — 2026_hw6_0521_bivariate_normal, 2026_hw6_0521_regression_line, 2026_hw6_0521_conditional_variance, 2026_hw6_0521_normal_cdf [INFERRED 0.80]

## Communities

### Community 0 - "Archive Attachment Vault"
Cohesion: 0.06
Nodes (59): AttachmentSpec, download_pending(), mark_deleted(), pending_attachments(), Attachments not yet downloaded and not yet skipped — the rows     `download_pend, Input shape for `record` — one row's worth of attachment metadata     at archiva, Download any pending attachments for `message_id` to     `data/attachments/<mess, Atomically stamp `deleted_at` iff the row exists and the     column is NULL. Ret (+51 more)

### Community 1 - "Link Embedder Cog"
Cohesion: 0.07
Nodes (56): make_bot_stub, _is_instagram_reel(), _is_threads_avatar_fallback(), _is_threads_video_frame(), LinkEmbedderCog, on_message(), on_raw_message_delete(), on_raw_message_edit() (+48 more)

### Community 2 - "Archive Cog Handlers"
Cohesion: 0.07
Nodes (38): archive_deleted(), archive_get(), archive_show(), ArchiveCog, ArchivedMessage, Attachment, _attachment_summary(), cutoff_ts() (+30 more)

### Community 3 - "Architecture Overview (CLAUDE.md)"
Cohesion: 0.07
Nodes (45): bot.py entry point and EXTENSIONS toggles, Cloudflare challenge handling (CHALLENGE_WAIT_MS), Archive cog, Birthday cog, Link embedder cog (LinkEmbedderCog), Containerized deployment (Dockerfile + compose), Discord threads handled transparently, Per-cog feature toggles via EXTENSIONS env vars (+37 more)

### Community 4 - "Bot Core & Mod-log Helpers"
Cohesion: 0.05
Nodes (38): Download any attachments for this message that haven't yet been         processe, Format the bullet list used in deletion / removal mod-log embeds         from th, Exclusion check that respects the parent-of-Discord-thread rule.         Used by, Format the bullet list used in deletion / removal mod-log         embeds from a, Bot, main(), help_command(), HelpCog (+30 more)

### Community 5 - "Birthday Cog"
Cohesion: 0.09
Nodes (33): daily_purge(), birthday_list(), birthday_remove(), birthday_set(), birthday_show(), BirthdayCog, Birthday, get() (+25 more)

### Community 6 - "Utils & Channel-exclusion Tests"
Cohesion: 0.11
Nodes (26): Characterization tests for `core.utils`.  Pure functions: - `parse_id_set` — com, A regular TextChannel object isn't a Thread; the parent walk     must not fire e, test_blank_entries_between_commas_are_ignored(), test_duplicate_ids_are_deduplicated(), test_empty_string_returns_empty_set(), test_is_channel_or_parent_in_direct_match(), test_is_channel_or_parent_in_no_match(), test_is_channel_or_parent_in_non_thread_channel() (+18 more)

### Community 7 - "ADRs & Persistence Rationale"
Cohesion: 0.12
Nodes (26): Rationale: SQLite chosen over Postgres / per-feature JSON, ADR-0001: All bot state in a single SQLite file, ADR-0002: Archive uses full message logging, Rationale: full logging survives restarts vs cache-only snipe, Archive cog (CLAUDE.md), Birthday cog (CLAUDE.md), Persistence (single SQLite file), mod_log.truncate (+18 more)

### Community 8 - "DB Init & Domain Terms"
Cohesion: 0.15
Nodes (21): Link embedder cog (CLAUDE.md), Preview sidecar (Node + Playwright), fresh_db fixture, Excluded channel (domain term), Original poster (domain term), Webhook repost (domain term), db.init_db, db._migrate (+13 more)

### Community 9 - "URL Rule Rewriting & Tests"
Cohesion: 0.1
Nodes (21): _apply_rule(), Substitute every match of `pattern` in `text` with `cleaner(match)`.     Returns, Apply each URL rule to the message text. Returns (rebuilt, urls) —     `urls` is, _rebuild_content(), test_apply_rule_collects_one_entry_per_match_in_source_order, test_apply_rule_returns_unchanged_text_and_empty_list_on_no_match, test_apply_rule_substitutes_match_and_records_cleaned_url, test_rebuild_content_clean_dcard_link_is_left_alone (+13 more)

### Community 10 - "Threads Embed Fix (plan/spec)"
Cohesion: 0.14
Nodes (20): One feature/task per commit, Subagent prompts must pin working directory, Threads avatar-thumbnail + video-footer quirks, Superpowers workflow for substantial work, Avatar fallback signal: twitter:card == summary, Bug 1: avatar-as-hero on text-only Threads posts, Bug 2: play-button overlay on Threads video posts, _is_instagram_reel existing helper (+12 more)

### Community 11 - "HW6 Probability Problem Set"
Cohesion: 0.2
Nodes (12): Bivariate Normal Distribution, Conditional Density h(y|x), f_{Y|X}, Conditional Expectation E[Y|X=x], Conditional Standard Deviation sigma_{Y|X}=sigma_Y*sqrt(1-rho^2), Correlation Coefficient rho, 2026 HW6 (Probability/Statistics Problem Set, 2026/5/21), Joint Probability Density Function f(x,y), Marginal Density f_X(x), f_Y(y) (+4 more)

### Community 12 - "Embed Truncation Helper"
Cohesion: 0.22
Nodes (9): Cap a Discord embed field at `limit` characters with an ellipsis;     return Non, _truncate_for_embed(), test_truncate_for_embed_empty_string_returns_none, test_truncate_for_embed_long_text_ellipsizes_within_limit, test_truncate_for_embed_none_returns_none, test_truncate_for_embed_short_text_passes_through, test_truncate_for_embed_strips_outer_whitespace_when_returning, test_truncate_for_embed_text_at_exact_limit_passes_through (+1 more)

### Community 13 - "Score Histogram Image"
Cohesion: 0.4
Nodes (6): Bimodal / U-shaped Distribution, Empty Mid-range (10-30, zero counts), High-value Peak (80-100, ~42-43 count), Histogram Chart, Score Distribution (0-100), Low-value Spike (0-10, ~26 count)

### Community 14 - "Bot Entry & Environment"
Cohesion: 1.0
Nodes (2): Bot entry point and cog loading, Environment (Python 3.14 + uv)

### Community 15 - "webhook_reposts table"
Cohesion: 1.0
Nodes (1): webhook_reposts table

### Community 16 - "messages table"
Cohesion: 1.0
Nodes (1): messages table

### Community 17 - "attachments table"
Cohesion: 1.0
Nodes (1): attachments table

### Community 18 - "message_edits table"
Cohesion: 1.0
Nodes (1): message_edits table

### Community 19 - "birthdays table"
Cohesion: 1.0
Nodes (1): birthdays table

### Community 20 - "core.mod_log module"
Cohesion: 1.0
Nodes (1): core.mod_log

### Community 21 - "post_deleted"
Cohesion: 1.0
Nodes (1): mod_log.post_deleted

### Community 22 - "post_edited"
Cohesion: 1.0
Nodes (1): mod_log.post_edited

### Community 23 - "post_attachment_removed"
Cohesion: 1.0
Nodes (1): mod_log.post_attachment_removed

### Community 25 - "no_task_loops fixture"
Cohesion: 1.0
Nodes (1): no_task_loops fixture

### Community 26 - "strip_query full-query test"
Cohesion: 1.0
Nodes (1): test_strip_query_drops_full_query_string

### Community 27 - "strip_query no-query test"
Cohesion: 1.0
Nodes (1): test_strip_query_keeps_url_without_query_unchanged

### Community 28 - "strip_query bare-? test"
Cohesion: 1.0
Nodes (1): test_strip_query_handles_bare_question_mark

### Community 29 - "instagram regex test"
Cohesion: 1.0
Nodes (1): test_instagram_regex_matches_clean_and_tracked_urls

### Community 30 - "threads regex test"
Cohesion: 1.0
Nodes (1): test_threads_regex_matches_both_dotcom_and_dotnet_hosts

### Community 31 - "dcard cid match test"
Cohesion: 1.0
Nodes (1): test_dcard_cid_regex_matches_url_with_cid_param

### Community 32 - "dcard cid no-match test"
Cohesion: 1.0
Nodes (1): test_dcard_cid_regex_does_not_match_clean_dcard_url

### Community 33 - "dcard www test"
Cohesion: 1.0
Nodes (1): test_dcard_cid_regex_matches_with_or_without_www

### Community 34 - "youtube si short-link test"
Cohesion: 1.0
Nodes (1): test_youtube_si_regex_matches_youtu_be_short_link

### Community 35 - "youtube si watch test"
Cohesion: 1.0
Nodes (1): test_youtube_si_regex_matches_watch_url_with_si

### Community 36 - "youtube si subdomain test"
Cohesion: 1.0
Nodes (1): test_youtube_si_regex_matches_subdomains_and_shorts

### Community 37 - "youtube si clean test"
Cohesion: 1.0
Nodes (1): test_youtube_si_regex_does_not_match_clean_youtube_url

### Community 38 - "youtube si false-match test"
Cohesion: 1.0
Nodes (1): test_youtube_si_regex_does_not_falsematch_si_in_other_param

### Community 40 - "Idempotent column migrations"
Cohesion: 1.0
Nodes (1): Idempotent column additions for already-deployed databases. SQLite     has no AD

### Community 41 - "post_edited docstring"
Cohesion: 1.0
Nodes (1): Post an "Edited" mod-log notice. Returns the sent message so callers     that ne

### Community 42 - "parse_id_set"
Cohesion: 1.0
Nodes (1): Parse a comma-separated list of integer IDs (typically from an env     var) into

### Community 43 - "parse_bool_env"
Cohesion: 1.0
Nodes (1): Parse an env-var-style boolean. Unset (`None`) or empty falls back     to `defau

### Community 44 - "conftest setup"
Cohesion: 1.0
Nodes (1): Shared pytest setup for the discord-bot tests.  The project's modules import fro

### Community 45 - "fresh_db fixture"
Cohesion: 1.0
Nodes (1): An in-memory aiosqlite Connection with the production schema and     migrations

### Community 46 - "task-loop suppression"
Cohesion: 1.0
Nodes (1): Stop `@tasks.loop`-decorated methods from actually scheduling     background tas

### Community 47 - "bot stub builder"
Cohesion: 1.0
Nodes (1): Build a minimal stand-in for `bot` that satisfies what the cogs     actually rea

### Community 48 - "db.init_db tests"
Cohesion: 1.0
Nodes (1): Characterization tests for `db.init_db` and `db._migrate`.  Async because aiosql

### Community 49 - "db tempdir fixture"
Cohesion: 1.0
Nodes (1): Point db.DATA_DIR / db.DB_PATH at a tempdir for this test only.     init_db() us

### Community 50 - "URL rewrite test suite"
Cohesion: 1.0
Nodes (1): Characterization tests for the link embedder's URL rewriting pipeline.  Covers t

### Community 51 - "Dcard preview=False rationale"
Cohesion: 1.0
Nodes (1): Dcard's rule has preview=False because Cloudflare blocks the     sidecar reliabl

### Community 52 - "YouTube preview=False rationale"
Cohesion: 1.0
Nodes (1): YouTube's rule has preview=False because Discord's native player     embeds YouT

### Community 53 - "mod_log.truncate tests"
Cohesion: 1.0
Nodes (1): Characterization tests for `mod_log.truncate`.  Pure function used to keep embed

### Community 54 - "suppressed_deletes handshake"
Cohesion: 1.0
Nodes (1): suppressed_deletes cross-cog handshake

### Community 55 - "recent_edit_mod_logs handshake"
Cohesion: 1.0
Nodes (1): recent_edit_mod_logs cross-cog handshake

### Community 56 - "Discord threads handling"
Cohesion: 1.0
Nodes (1): Discord threads handling

### Community 57 - "Troubleshooting guidance"
Cohesion: 1.0
Nodes (1): Troubleshooting guidance

### Community 58 - "Oracle gotchas"
Cohesion: 1.0
Nodes (1): Oracle-specific gotchas (idle reclamation etc.)

### Community 59 - "Project intent"
Cohesion: 1.0
Nodes (1): Project intent: incremental cogs, no upfront abstractions

### Community 60 - "Environment Python 3.14"
Cohesion: 1.0
Nodes (1): Environment: Python 3.14 + uv venv

### Community 61 - "/help command"
Cohesion: 1.0
Nodes (1): /help command

## Knowledge Gaps
- **174 isolated node(s):** `Persistent record of Birthdays — the `birthdays` table interface.`, `True if a row was deleted; False if nothing matched.`, `All registered birthdays as (user_id, Birthday) sorted by (month, day).`, `User IDs whose Birthday falls on `today`; on non-leap Feb-28, also matches Feb-2`, `DATA_DIR / DB_PATH` (+169 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Bot Entry & Environment`** (2 nodes): `Bot entry point and cog loading`, `Environment (Python 3.14 + uv)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `webhook_reposts table`** (1 nodes): `webhook_reposts table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `messages table`** (1 nodes): `messages table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `attachments table`** (1 nodes): `attachments table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `message_edits table`** (1 nodes): `message_edits table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `birthdays table`** (1 nodes): `birthdays table`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `core.mod_log module`** (1 nodes): `core.mod_log`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `post_deleted`** (1 nodes): `mod_log.post_deleted`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `post_edited`** (1 nodes): `mod_log.post_edited`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `post_attachment_removed`** (1 nodes): `mod_log.post_attachment_removed`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `no_task_loops fixture`** (1 nodes): `no_task_loops fixture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `strip_query full-query test`** (1 nodes): `test_strip_query_drops_full_query_string`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `strip_query no-query test`** (1 nodes): `test_strip_query_keeps_url_without_query_unchanged`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `strip_query bare-? test`** (1 nodes): `test_strip_query_handles_bare_question_mark`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `instagram regex test`** (1 nodes): `test_instagram_regex_matches_clean_and_tracked_urls`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `threads regex test`** (1 nodes): `test_threads_regex_matches_both_dotcom_and_dotnet_hosts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `dcard cid match test`** (1 nodes): `test_dcard_cid_regex_matches_url_with_cid_param`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `dcard cid no-match test`** (1 nodes): `test_dcard_cid_regex_does_not_match_clean_dcard_url`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `dcard www test`** (1 nodes): `test_dcard_cid_regex_matches_with_or_without_www`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `youtube si short-link test`** (1 nodes): `test_youtube_si_regex_matches_youtu_be_short_link`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `youtube si watch test`** (1 nodes): `test_youtube_si_regex_matches_watch_url_with_si`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `youtube si subdomain test`** (1 nodes): `test_youtube_si_regex_matches_subdomains_and_shorts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `youtube si clean test`** (1 nodes): `test_youtube_si_regex_does_not_match_clean_youtube_url`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `youtube si false-match test`** (1 nodes): `test_youtube_si_regex_does_not_falsematch_si_in_other_param`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Idempotent column migrations`** (1 nodes): `Idempotent column additions for already-deployed databases. SQLite     has no AD`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `post_edited docstring`** (1 nodes): `Post an "Edited" mod-log notice. Returns the sent message so callers     that ne`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `parse_id_set`** (1 nodes): `Parse a comma-separated list of integer IDs (typically from an env     var) into`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `parse_bool_env`** (1 nodes): `Parse an env-var-style boolean. Unset (`None`) or empty falls back     to `defau`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `conftest setup`** (1 nodes): `Shared pytest setup for the discord-bot tests.  The project's modules import fro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `fresh_db fixture`** (1 nodes): `An in-memory aiosqlite Connection with the production schema and     migrations`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `task-loop suppression`** (1 nodes): `Stop `@tasks.loop`-decorated methods from actually scheduling     background tas`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `bot stub builder`** (1 nodes): `Build a minimal stand-in for `bot` that satisfies what the cogs     actually rea`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `db.init_db tests`** (1 nodes): `Characterization tests for `db.init_db` and `db._migrate`.  Async because aiosql`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `db tempdir fixture`** (1 nodes): `Point db.DATA_DIR / db.DB_PATH at a tempdir for this test only.     init_db() us`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `URL rewrite test suite`** (1 nodes): `Characterization tests for the link embedder's URL rewriting pipeline.  Covers t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Dcard preview=False rationale`** (1 nodes): `Dcard's rule has preview=False because Cloudflare blocks the     sidecar reliabl`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `YouTube preview=False rationale`** (1 nodes): `YouTube's rule has preview=False because Discord's native player     embeds YouT`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `mod_log.truncate tests`** (1 nodes): `Characterization tests for `mod_log.truncate`.  Pure function used to keep embed`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `suppressed_deletes handshake`** (1 nodes): `suppressed_deletes cross-cog handshake`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `recent_edit_mod_logs handshake`** (1 nodes): `recent_edit_mod_logs cross-cog handshake`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Discord threads handling`** (1 nodes): `Discord threads handling`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Troubleshooting guidance`** (1 nodes): `Troubleshooting guidance`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Oracle gotchas`** (1 nodes): `Oracle-specific gotchas (idle reclamation etc.)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Project intent`** (1 nodes): `Project intent: incremental cogs, no upfront abstractions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Environment Python 3.14`** (1 nodes): `Environment: Python 3.14 + uv venv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `/help command`** (1 nodes): `/help command`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Bot` connect `Bot Core & Mod-log Helpers` to `Link Embedder Cog`, `Archive Cog Handlers`, `Birthday Cog`, `Utils & Channel-exclusion Tests`, `DB Init & Domain Terms`, `URL Rule Rewriting & Tests`, `Embed Truncation Helper`?**
  _High betweenness centrality (0.177) - this node is a cross-community bridge._
- **Why does `webhook_reposts table` connect `DB Init & Domain Terms` to `ADRs & Persistence Rationale`?**
  _High betweenness centrality (0.111) - this node is a cross-community bridge._
- **Are the 31 inferred relationships involving `LinkEmbedderCog` (e.g. with `Bot` and `test_process_message_inserts_repost_row_before_deleting_original()`) actually correct?**
  _`LinkEmbedderCog` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 36 inferred relationships involving `Bot` (e.g. with `LinkEmbedderCog` and `Build a cleaner that drops the named query params while preserving     the rest.`) actually correct?**
  _`Bot` has 36 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `record()` (e.g. with `test_record_inserts_row()` and `test_record_accepts_null_original_message_id()`) actually correct?**
  _`record()` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `make_bot_stub` (e.g. with `Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired` and `A MagicMock shaped like the `discord.Message` attributes the     link embedder r`) actually correct?**
  _`make_bot_stub` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 16 inferred relationships involving `WebhookRepost` (e.g. with `Cog-level tests for the link embedder.  Constructs a real LinkEmbedderCog wired` and `A MagicMock shaped like the `discord.Message` attributes the     link embedder r`) actually correct?**
  _`WebhookRepost` has 16 INFERRED edges - model-reasoned connections that need verification._