import logging

log = logging.getLogger(__name__)


def parse_id_set(s: str) -> set[int]:
    """Parse a comma-separated list of integer IDs (typically from an env
    var) into a set, ignoring blank entries and warning on non-integers."""
    out: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if part:
            try:
                out.add(int(part))
            except ValueError:
                log.warning("Ignoring non-integer ID %r in env list", part)
    return out


def parse_bool_env(raw: str | None, *, default: bool) -> bool:
    """Parse an env-var-style boolean. Unset (`None`) or empty falls back
    to `default`; `false` (case-insensitive, whitespace trimmed) → False;
    anything else → True."""
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    return stripped.lower() != "false"
