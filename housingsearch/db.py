"""SQLite storage. One file, zero setup; swap for Postgres by porting this module."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import config

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS builders (
    id                    INTEGER PRIMARY KEY,
    name                  TEXT NOT NULL UNIQUE,
    established_year      INTEGER,
    projects_delivered    INTEGER DEFAULT 0,
    projects_ongoing      INTEGER DEFAULT 0,
    on_time_delivery_pct  REAL,
    avg_delay_months      REAL,
    rera_complaints       INTEGER DEFAULT 0,
    website               TEXT,
    description           TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id                      INTEGER PRIMARY KEY,
    slug                    TEXT NOT NULL UNIQUE,
    name                    TEXT NOT NULL,
    builder_id              INTEGER REFERENCES builders(id),
    city                    TEXT NOT NULL,
    state                   TEXT NOT NULL,
    locality                TEXT NOT NULL,
    address                 TEXT,
    pincode                 TEXT,
    lat                     REAL,
    lng                     REAL,
    property_type           TEXT,          -- Apartment | Villa | Plot | Row House | Penthouse
    status                  TEXT,          -- Pre-launch | Under Construction | Ready to Move
    launch_date             TEXT,
    rera_number             TEXT,
    rera_status             TEXT,          -- Registered | Applied | Lapsed | Revoked | Not Registered
    rera_authority          TEXT,
    rera_url                TEXT,
    rera_possession_date    TEXT,          -- date declared to RERA (legally binding)
    builder_possession_date TEXT,          -- date advertised by builder / brokers
    construction_progress   INTEGER,       -- percent, as reported in RERA quarterly update
    total_units             INTEGER,
    available_units         INTEGER,
    towers                  INTEGER,
    floors                  INTEGER,
    land_area_acres         REAL,
    open_space_pct          REAL,
    amenities               TEXT,          -- JSON list
    bank_approvals          TEXT,          -- JSON list of lenders that approved the project
    description             TEXT,
    is_demo                 INTEGER DEFAULT 0,
    updated_at              TEXT
);

CREATE TABLE IF NOT EXISTS configurations (
    id                 INTEGER PRIMARY KEY,
    property_id        INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    label              TEXT NOT NULL,     -- "2 BHK", "3 BHK + Study"
    bhk                REAL,
    carpet_sqft        REAL,
    super_builtup_sqft REAL,
    price_min          REAL,
    price_max          REAL,
    units_total        INTEGER,
    units_available    INTEGER,
    facing             TEXT
);

CREATE TABLE IF NOT EXISTS price_quotes (
    id              INTEGER PRIMARY KEY,
    property_id     INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    config_label    TEXT,
    source          TEXT NOT NULL,      -- housing.com, 99acres, builder site, broker ...
    source_url      TEXT,
    price           REAL,               -- INR, all-inclusive quote where available
    price_per_sqft  REAL,               -- INR / sq ft on super built-up area
    quoted_on       TEXT NOT NULL,      -- ISO date the quote was observed
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS approvals (
    id            INTEGER PRIMARY KEY,
    property_id   INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    code          TEXT NOT NULL,       -- key into approvals_catalog
    status        TEXT NOT NULL,       -- Obtained | Pending | Missing | Not Applicable | Not Yet Due | Unknown
    reference     TEXT,
    issued_on     TEXT,
    document_url  TEXT,
    notes         TEXT
);

CREATE TABLE IF NOT EXISTS reviews (
    id           INTEGER PRIMARY KEY,
    property_id  INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    source       TEXT NOT NULL,
    url          TEXT,
    author       TEXT,
    rating       REAL,               -- 1..5, null when the forum has no ratings
    posted_on    TEXT,
    title        TEXT,
    body         TEXT,
    sentiment    TEXT                -- positive | neutral | negative (computed if absent)
);

CREATE TABLE IF NOT EXISTS litigation (
    id           INTEGER PRIMARY KEY,
    property_id  INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    forum        TEXT NOT NULL,      -- RERA | Consumer Commission | High Court | NCLT
    case_ref     TEXT,
    filed_on     TEXT,
    status       TEXT,               -- Open | Disposed | Settled
    summary      TEXT,
    url          TEXT
);

CREATE TABLE IF NOT EXISTS nearby (
    id           INTEGER PRIMARY KEY,
    property_id  INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    category     TEXT NOT NULL,      -- Metro | School | Hospital | IT Park | Mall | Airport | Railway
    name         TEXT NOT NULL,
    distance_km  REAL
);

CREATE INDEX IF NOT EXISTS ix_prop_city     ON properties(city);
CREATE INDEX IF NOT EXISTS ix_prop_locality ON properties(city, locality);
CREATE INDEX IF NOT EXISTS ix_conf_prop     ON configurations(property_id);
CREATE INDEX IF NOT EXISTS ix_quote_prop    ON price_quotes(property_id, quoted_on);
CREATE INDEX IF NOT EXISTS ix_appr_prop     ON approvals(property_id);
CREATE INDEX IF NOT EXISTS ix_rev_prop      ON reviews(property_id);
"""


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def is_empty(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT COUNT(*) FROM properties").fetchone()[0] == 0


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    d = dict(row)
    for key in ("amenities", "bank_approvals"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = json.loads(d[key])
            except json.JSONDecodeError:
                d[key] = [s.strip() for s in d[key].split(",") if s.strip()]
    return d
