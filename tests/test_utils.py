"""Characterization tests for `core.utils`.

Pure functions:
- `parse_id_set` — comma-separated env var → `set[int]`
- `parse_bool_env` — env var string → bool, with a configurable default
  for unset/empty values

These tests pin down current behavior so a future refactor doesn't
quietly change the contract.
"""

import logging

from core.utils import parse_bool_env, parse_id_set


def test_empty_string_returns_empty_set():
    assert parse_id_set("") == set()


def test_single_id_parses_to_singleton_set():
    assert parse_id_set("42") == {42}


def test_multiple_ids_parse_to_set():
    assert parse_id_set("1,2,3") == {1, 2, 3}


def test_whitespace_around_entries_is_stripped():
    assert parse_id_set("  1 ,  2  ,3  ") == {1, 2, 3}


def test_blank_entries_between_commas_are_ignored():
    assert parse_id_set("1,,2,") == {1, 2}


def test_only_commas_returns_empty_set():
    assert parse_id_set(",,,") == set()


def test_duplicate_ids_are_deduplicated():
    assert parse_id_set("7,7,7") == {7}


def test_non_integer_entries_are_skipped(caplog):
    with caplog.at_level(logging.WARNING, logger="utils"):
        result = parse_id_set("1,not_a_number,2")
    assert result == {1, 2}
    # The warning is part of the contract — it tells the operator their
    # env list has a bad entry.
    assert any("not_a_number" in rec.getMessage() for rec in caplog.records)


def test_mixed_valid_invalid_keeps_only_valid():
    # Negative numbers are valid integers; keep them. (Discord IDs are
    # always positive, but the function is general-purpose.)
    assert parse_id_set("1, abc, 2, , -5, xyz") == {1, 2, -5}


# --- parse_bool_env ---------------------------------------------------


def test_parse_bool_env_unset_uses_default():
    assert parse_bool_env(None, default=True) is True
    assert parse_bool_env(None, default=False) is False


def test_parse_bool_env_empty_string_uses_default():
    # An operator who writes `FOO=` in .env probably means "leave default" —
    # we don't want a stray empty value to silently flip a feature off.
    assert parse_bool_env("", default=True) is True
    assert parse_bool_env("", default=False) is False


def test_parse_bool_env_false_is_false():
    for raw in ("false", "FALSE", "False"):
        assert parse_bool_env(raw, default=True) is False, raw


def test_parse_bool_env_other_values_are_true():
    # Only the literal word `false` flips the toggle off — keeps the
    # contract obvious to a deployer skimming `.env`. Everything else,
    # including would-be-falsy strings like `0`/`no`/`off`, stays true.
    for raw in ("true", "TRUE", "yes", "1", "on", "no", "0", "off", "anything"):
        assert parse_bool_env(raw, default=False) is True, raw


def test_parse_bool_env_strips_whitespace():
    assert parse_bool_env("  false  ", default=True) is False
    assert parse_bool_env("\ttrue\n", default=False) is True
