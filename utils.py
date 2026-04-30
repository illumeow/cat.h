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
