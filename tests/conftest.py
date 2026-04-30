"""Shared pytest setup for the discord-bot tests.

The project's modules import from project root (e.g. `import mod_log`,
`from utils import parse_id_set`), and `cogs/*.py` does `from bot import
Bot` under TYPE_CHECKING. Add the project root to sys.path so tests can
import the same way the running bot does, without needing a package
install.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
