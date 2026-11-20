"""Importers for public state RERA registers.

Supported (public lists, no CAPTCHA, no login):
    ka  RERA Karnataka   -> Bengaluru (Urban + Rural districts)
    hr  HRERA Gurugram   -> Gurugram
    tn  TNRERA           -> Chennai metropolitan area
    mh  MahaRERA         -> Mumbai, Thane, Pune (newest projects; the full register is 50k+)

    tg  TG RERA          -> Hyderabad, from search-result pages you saved yourself
                            (the portal's search is behind a CAPTCHA, so it is never queried)

Not supported: UP RERA (portal was down for maintenance when this was built).

Every importer returns records in the JSON import format (docs/DATA_FORMAT.md), so the
output can be loaded with `ingest.import_records` or saved as a seed file.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .. import config
from . import haryana, karnataka, maharashtra, tamilnadu, telangana
from .fetch import PoliteFetcher

STATES = {
    "ka": ("Karnataka", "Bengaluru"),
    "hr": ("Haryana", "Gurugram"),
    "tn": ("Tamil Nadu", "Chennai"),
    "mh": ("Maharashtra", "Mumbai, Thane, Pune"),
    "tg": ("Telangana", "Hyderabad"),
}
SEED_DIR = config.DATA_DIR / "seed"


def run(state: str, fetcher: PoliteFetcher, details: bool = False, details_limit: int | None = None,
        max_pages: int = 60, files: list[str] | None = None, log=print) -> list[dict]:
    if state == "tg":
        if not files:
            raise ValueError("Telangana needs saved search-result pages: import-rera tg --from-file page1.html ...")
        return telangana.from_files(files, log=log)
    if state == "ka":
        return karnataka.fetch(fetcher, details=details, details_limit=details_limit, log=log)
    if state == "hr":
        return haryana.fetch(fetcher, log=log)
    if state == "tn":
        return tamilnadu.fetch(fetcher, log=log)
    if state == "mh":
        return maharashtra.fetch(fetcher, max_pages=max_pages, log=log)
    raise ValueError(f"Unknown state '{state}'. Choose from: {', '.join(STATES)}")


def dedupe(records: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for r in records:
        seen.setdefault(r["slug"], r)
    return list(seen.values())


def save_seed(state: str, records: list[dict], seed_dir: Path = SEED_DIR) -> Path:
    seed_dir.mkdir(parents=True, exist_ok=True)
    path = seed_dir / f"rera_{state}.json"
    payload = {
        "source": f"{STATES[state][0]} RERA public register",
        "fetched_on": date.today().isoformat(),
        "count": len(records),
        "properties": records,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path
