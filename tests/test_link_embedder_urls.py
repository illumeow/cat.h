"""Characterization tests for the link embedder's URL rewriting pipeline.

Covers the pure functions only — no Discord, no aiohttp, no cog
state. The pieces under test:

- `_strip_query` — drops the whole `?…` (used for threads.com)
- `_strip_param("igsh")` — drops a single query param, keeps others
  (used for instagram.com)
- `_apply_rule` — runs one regex+cleaner over a string and reports
  back the cleaned URLs it matched
- `_rebuild_content` — folds over `URL_RULES`; this is the function
  the cog uses to decide "did anything trigger?" and what to repost
- `_truncate_for_embed` — embed-safe text capping helper

These tests pin down current behavior so future refactors of the
rewrite pipeline don't quietly regress threads/instagram handling.
"""

import re

from cogs.link_embedder import (
    DCARD_CID_URL_RE,
    INSTAGRAM_IGSH_URL_RE,
    THREADS_URL_RE,
    _apply_rule,
    _preview_eligible_urls,
    _rebuild_content,
    _strip_param,
    _strip_query,
    _truncate_for_embed,
)


# --- _strip_query -----------------------------------------------------


def test_strip_query_drops_full_query_string():
    assert (
        _strip_query("https://threads.com/post/abc?xmt=foo&utm=bar")
        == "https://threads.com/post/abc"
    )


def test_strip_query_keeps_url_without_query_unchanged():
    assert _strip_query("https://threads.com/post/abc") == "https://threads.com/post/abc"


def test_strip_query_handles_bare_question_mark():
    assert _strip_query("https://threads.com/post/abc?") == "https://threads.com/post/abc"


# --- _strip_param ------------------------------------------------------


def test_strip_param_removes_only_named_param():
    clean = _strip_param("igsh")
    assert (
        clean("https://www.instagram.com/p/ABC/?img_index=2&igsh=hash")
        == "https://www.instagram.com/p/ABC/?img_index=2"
    )


def test_strip_param_drops_query_when_only_target_param_present():
    clean = _strip_param("igsh")
    assert (
        clean("https://www.instagram.com/p/ABC/?igsh=hash")
        == "https://www.instagram.com/p/ABC/"
    )


def test_strip_param_preserves_url_without_query():
    clean = _strip_param("igsh")
    assert (
        clean("https://www.instagram.com/p/ABC/")
        == "https://www.instagram.com/p/ABC/"
    )


def test_strip_param_no_op_when_target_param_absent():
    clean = _strip_param("igsh")
    assert (
        clean("https://www.instagram.com/p/ABC/?img_index=2")
        == "https://www.instagram.com/p/ABC/?img_index=2"
    )


def test_strip_param_handles_param_at_either_position():
    clean = _strip_param("igsh")
    # igsh first, then a real param after
    out_first = clean("https://www.instagram.com/p/ABC/?igsh=h&img_index=2")
    # real param first, igsh after
    out_last = clean("https://www.instagram.com/p/ABC/?img_index=2&igsh=h")
    assert out_first == "https://www.instagram.com/p/ABC/?img_index=2"
    assert out_last == "https://www.instagram.com/p/ABC/?img_index=2"


# --- _apply_rule -------------------------------------------------------


def test_apply_rule_returns_unchanged_text_and_empty_list_on_no_match():
    rebuilt, urls = _apply_rule("plain text no link", THREADS_URL_RE, _strip_query)
    assert rebuilt == "plain text no link"
    assert urls == []


def test_apply_rule_substitutes_match_and_records_cleaned_url():
    rebuilt, urls = _apply_rule(
        "look: https://threads.com/post/abc?xmt=foo end",
        THREADS_URL_RE,
        _strip_query,
    )
    assert rebuilt == "look: https://threads.com/post/abc end"
    assert urls == ["https://threads.com/post/abc"]


def test_apply_rule_collects_one_entry_per_match_in_source_order():
    rebuilt, urls = _apply_rule(
        "a https://threads.com/x?q=1 then b https://threads.com/y?q=2",
        THREADS_URL_RE,
        _strip_query,
    )
    assert rebuilt == "a https://threads.com/x then b https://threads.com/y"
    assert urls == ["https://threads.com/x", "https://threads.com/y"]


# --- _rebuild_content --------------------------------------------------


def test_rebuild_content_plain_text_returns_empty_url_list():
    rebuilt, urls = _rebuild_content("hello world, no links here")
    assert rebuilt == "hello world, no links here"
    assert urls == []


def test_rebuild_content_threads_url_with_tracker_is_cleaned():
    rebuilt, urls = _rebuild_content(
        "check https://www.threads.com/@u/post/123?xmt=tracker"
    )
    assert rebuilt == "check https://www.threads.com/@u/post/123"
    assert urls == ["https://www.threads.com/@u/post/123"]


def test_rebuild_content_threads_clean_url_still_triggers():
    # The threads regex is intentionally broad: every threads URL counts
    # as a match (rationale: discord re-fetches OG more reliably from a
    # fresh post). So even a clean URL should trigger.
    rebuilt, urls = _rebuild_content("https://www.threads.com/@u/post/123")
    assert rebuilt == "https://www.threads.com/@u/post/123"
    assert urls == ["https://www.threads.com/@u/post/123"]


def test_rebuild_content_instagram_with_igsh_strips_only_igsh():
    rebuilt, urls = _rebuild_content(
        "ig: https://www.instagram.com/reel/ABC/?img_index=2&igsh=hash"
    )
    assert rebuilt == "ig: https://www.instagram.com/reel/ABC/?img_index=2"
    assert urls == ["https://www.instagram.com/reel/ABC/?img_index=2"]


def test_rebuild_content_instagram_without_igsh_is_left_alone():
    # IG rule is narrow on purpose: untracked IG URLs aren't reposted.
    text = "https://www.instagram.com/p/ABC/?img_index=2"
    rebuilt, urls = _rebuild_content(text)
    assert rebuilt == text
    assert urls == []


def test_rebuild_content_plain_instagram_link_is_left_alone():
    text = "https://www.instagram.com/p/ABC/"
    rebuilt, urls = _rebuild_content(text)
    assert rebuilt == text
    assert urls == []


def test_rebuild_content_handles_mixed_threads_and_instagram_in_one_message():
    rebuilt, urls = _rebuild_content(
        "look: https://www.instagram.com/p/IG/?igsh=foo and "
        "https://threads.com/post/T?xmt=bar"
    )
    assert rebuilt == (
        "look: https://www.instagram.com/p/IG/ and "
        "https://threads.com/post/T"
    )
    # URLs are collected in URL_RULES iteration order (threads rule
    # first, instagram rule second), NOT source order. The cog uses
    # this list only as "things to ask the preview sidecar about," so
    # the order doesn't matter for behavior — but it IS the contract,
    # so we pin it down here.
    assert urls == [
        "https://threads.com/post/T",
        "https://www.instagram.com/p/IG/",
    ]


def test_instagram_igsh_regex_does_not_match_clean_ig_url():
    # Defends the gate: the regex is what decides "do anything," not
    # the cleaner. A future tweak that loosens the regex needs to break
    # this test, not slip in silently.
    assert INSTAGRAM_IGSH_URL_RE.search("https://www.instagram.com/p/ABC/") is None
    assert (
        INSTAGRAM_IGSH_URL_RE.search(
            "https://www.instagram.com/p/ABC/?img_index=2"
        )
        is None
    )


def test_instagram_igsh_regex_matches_url_with_igsh_param():
    m = INSTAGRAM_IGSH_URL_RE.search(
        "https://www.instagram.com/p/ABC/?igsh=hash"
    )
    assert m is not None


def test_threads_regex_matches_both_dotcom_and_dotnet_hosts():
    assert THREADS_URL_RE.search("https://threads.com/post/abc") is not None
    assert THREADS_URL_RE.search("https://threads.net/post/abc") is not None
    assert THREADS_URL_RE.search("https://www.threads.com/post/abc") is not None


# --- Dcard rule -------------------------------------------------------
#
# Mirror of the Instagram igsh pattern: dcard.tw URLs carry a campaign
# tracker `cid=…` (UUID) when shared from inside the app or via certain
# deeplinks. Only those URLs trigger a rewrite; clean URLs (and ones
# carrying only meaningful params) are left alone, on the same logic
# that drives the Instagram rule.


def test_dcard_cid_regex_matches_url_with_cid_param():
    m = DCARD_CID_URL_RE.search(
        "https://www.dcard.tw/f/ntu/p/261398533?cid=eeb65574-0784-49d8-b298-15b4ca089da2"
    )
    assert m is not None


def test_dcard_cid_regex_does_not_match_clean_dcard_url():
    assert DCARD_CID_URL_RE.search("https://www.dcard.tw/f/ntu/p/261398533") is None
    assert (
        DCARD_CID_URL_RE.search("https://www.dcard.tw/f/ntu/p/261398533?utm=x")
        is None
    )


def test_dcard_cid_regex_matches_with_or_without_www():
    assert (
        DCARD_CID_URL_RE.search(
            "https://dcard.tw/f/ntu/p/261398533?cid=abc"
        )
        is not None
    )
    assert (
        DCARD_CID_URL_RE.search(
            "https://www.dcard.tw/f/ntu/p/261398533?cid=abc"
        )
        is not None
    )


def test_rebuild_content_dcard_url_with_cid_strips_only_cid():
    rebuilt, urls = _rebuild_content(
        "look: https://www.dcard.tw/f/ntu/p/261398533?cid=eeb65574"
    )
    assert rebuilt == "look: https://www.dcard.tw/f/ntu/p/261398533"
    assert urls == ["https://www.dcard.tw/f/ntu/p/261398533"]


def test_rebuild_content_dcard_url_keeps_other_params():
    rebuilt, urls = _rebuild_content(
        "https://www.dcard.tw/f/ntu/p/123?utm_source=share&cid=abc"
    )
    assert rebuilt == "https://www.dcard.tw/f/ntu/p/123?utm_source=share"
    assert urls == ["https://www.dcard.tw/f/ntu/p/123?utm_source=share"]


def test_rebuild_content_clean_dcard_link_is_left_alone():
    text = "https://www.dcard.tw/f/ntu/p/261398533"
    rebuilt, urls = _rebuild_content(text)
    assert rebuilt == text
    assert urls == []


# --- _preview_eligible_urls -------------------------------------------


def test_preview_eligible_urls_includes_threads_and_instagram():
    urls = _preview_eligible_urls(
        "look at https://threads.com/post/abc?xmt=foo and "
        "https://www.instagram.com/p/IG/?igsh=hash"
    )
    # Both rules have preview=True, so both cleaned URLs come back.
    assert urls == [
        "https://threads.com/post/abc",
        "https://www.instagram.com/p/IG/",
    ]


def test_preview_eligible_urls_excludes_dcard():
    """Dcard's rule has preview=False because Cloudflare blocks the
    sidecar reliably. The URL is still cleaned by _rebuild_content for
    the rewrite, but we don't ask the sidecar about it."""
    urls = _preview_eligible_urls(
        "ouch: https://www.dcard.tw/f/ntu/p/123?cid=eeb65574"
    )
    assert urls == []


def test_preview_eligible_urls_only_returns_preview_enabled_in_mixed_message():
    urls = _preview_eligible_urls(
        "https://www.dcard.tw/f/ntu/p/1?cid=x and "
        "https://threads.com/@u/post/2?xmt=y"
    )
    # Threads only — Dcard is filtered out.
    assert urls == ["https://threads.com/@u/post/2"]


# --- _truncate_for_embed ----------------------------------------------


def test_truncate_for_embed_none_returns_none():
    assert _truncate_for_embed(None, 100) is None


def test_truncate_for_embed_empty_string_returns_none():
    # Different from mod_log.truncate (which returns "*(empty)*"); this
    # helper returns None so the caller can omit the field cleanly.
    assert _truncate_for_embed("", 100) is None


def test_truncate_for_embed_whitespace_only_returns_none():
    assert _truncate_for_embed("   \n\t  ", 100) is None


def test_truncate_for_embed_short_text_passes_through():
    assert _truncate_for_embed("hello", 100) == "hello"


def test_truncate_for_embed_strips_outer_whitespace_when_returning():
    assert _truncate_for_embed("  hi  ", 100) == "hi"


def test_truncate_for_embed_long_text_ellipsizes_within_limit():
    # The helper uses a single-char ellipsis "…", so the budget is
    # `limit - 1` content chars. Result must fit in `limit`.
    out = _truncate_for_embed("x" * 500, 100)
    assert out is not None
    assert len(out) <= 100
    assert out.endswith("…")


def test_truncate_for_embed_text_at_exact_limit_passes_through():
    text = "y" * 100
    assert _truncate_for_embed(text, 100) == text
