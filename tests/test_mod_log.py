"""Characterization tests for `mod_log.truncate`.

Pure function used to keep embed fields under Discord's per-field /
description caps. Pins down: None and empty become a fixed sentinel;
short text passes through untouched; over-limit text is truncated with
a suffix and the *total* length stays at exactly the limit.
"""

from mod_log import truncate

# Mirror what callers use; if these change in production code, the
# tests still describe the contract relative to whatever limit is passed.
SUFFIX = "\n…(truncated)"


def test_none_returns_empty_sentinel():
    assert truncate(None, 100) == "*(empty)*"


def test_empty_string_returns_empty_sentinel():
    assert truncate("", 100) == "*(empty)*"


def test_short_text_passes_through_unchanged():
    assert truncate("hello", 100) == "hello"


def test_text_at_exact_limit_passes_through():
    text = "a" * 100
    assert truncate(text, 100) == text


def test_text_over_limit_is_truncated_with_suffix():
    text = "a" * 200
    out = truncate(text, 100)
    assert out.endswith(SUFFIX)


def test_truncated_output_length_equals_limit():
    # Subtle but load-bearing: the truncation budget is `limit - len(SUFFIX)`,
    # so the final string is exactly `limit` chars (suffix included). Test
    # at a few limit sizes so an off-by-one in the slice would be caught.
    for limit in (50, 100, 1024, 4000):
        out = truncate("z" * (limit * 2), limit)
        assert len(out) == limit, f"limit={limit}: got len={len(out)}"
