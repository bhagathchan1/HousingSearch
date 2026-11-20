"""Runtime configuration, overridable with environment variables."""

from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT_DIR / "web"
DATA_DIR = Path(os.environ.get("HS_DATA_DIR", ROOT_DIR / "data"))
DB_PATH = Path(os.environ.get("HS_DB_PATH", DATA_DIR / "housingsearch.db"))
SEED_DIR = DATA_DIR / "seed"
SEED_FILE = SEED_DIR / "demo_properties.json"
# Demo data is loaded only when no real seed files exist, unless HS_DEMO=1 (always) or 0 (never).
DEMO = os.environ.get("HS_DEMO", "auto").lower()

HOST = os.environ.get("HS_HOST", "127.0.0.1")
PORT = int(os.environ.get("HS_PORT") or os.environ.get("PORT") or "8000")

# Token required for write endpoints (POST /api/admin/*). Empty disables them.
ADMIN_TOKEN = os.environ.get("HS_ADMIN_TOKEN", "")

# Identifies this tool to sites when the optional URL importer fetches a page.
USER_AGENT = os.environ.get(
    "HS_USER_AGENT", "HousingSearchBot/1.0 (+https://github.com/bhagathchan1/HousingSearch)"
)
