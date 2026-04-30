"""Characterization tests for `utils.parse_id_set`.

Pure function: takes a comma-separated string (typically from an env var)
and returns a `set[int]`. Blank entries are ignored, non-integer entries
are skipped with a warning. These tests pin down current behavior so a
future refactor doesn't quietly change the contract.
"""

import logging

from utils import parse_id_set


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
