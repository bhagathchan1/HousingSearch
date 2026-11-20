# Architecture

```
┌──────────────────────────┐     ┌───────────────────────────────────────────┐
│  Browser (web/)          │     │  FastAPI (housingsearch/api.py)           │
│  Vanilla JS ES modules   │────▶│  /api/*  JSON                             │
│  hash router, no build   │     │  /       index.html + /static             │
│  Leaflet map (CDN)       │     └───────────────┬───────────────────────────┘
│  localStorage: shortlist,│                     │
│  compare, notes, theme   │     ┌───────────────▼───────────────────────────┐
└──────────────────────────┘     │  Repository (repository.py)               │
                                 │  • in-memory index of project summaries   │
                                 │  • filters, fuzzy search, facets, sort    │
                                 │  • detail assembly + per-id cache         │
                                 └───────┬──────────────────────┬────────────┘
                                         │                      │
                         ┌───────────────▼─────┐   ┌────────────▼─────────────┐
                         │ insights.py (pure)  │   │ SQLite (db.py)           │
                         │ price summary/trend │   │ builders, properties,    │
                         │ fair price          │   │ configurations,          │
                         │ delivery & delays   │   │ price_quotes, approvals, │
                         │ approvals checklist │   │ reviews, litigation,     │
                         │ review sentiment    │   │ nearby                   │
                         │ red flags, trust    │   └────────────▲─────────────┘
                         └─────────────────────┘                │
                                                   ┌────────────┴─────────────┐
                                                   │ ingest.py / cli.py       │
                                                   │ JSON · CSV · URL(JSON-LD)│
                                                   └──────────────────────────┘
```

## Modules

| File | Responsibility |
|---|---|
| `housingsearch/config.py` | Paths and environment variables |
| `housingsearch/db.py` | Schema, connection |
| `housingsearch/catalog.py` | Reference data: 15 approvals with state-specific authorities, RERA portals, stamp duty/registration, GST, portal & forum list |
| `housingsearch/insights.py` | Pure analytics: price summary & trend, fair price vs locality, delivery/overdue, approvals completeness, review sentiment & themes, red flags, trust score, verify links |
| `housingsearch/repository.py` | Queries, in-memory search index, upsert/merge logic |
| `housingsearch/ingest.py` | JSON, CSV and single-URL (schema.org JSON-LD) importers |
| `housingsearch/api.py` | HTTP API + static web UI |
| `housingsearch/rera/` | State RERA importers (Karnataka, Haryana, Tamil Nadu, Maharashtra, Telangana from saved pages) and a polite, caching HTTP client |
| `housingsearch/cli.py` | `serve`, `seed`, `import-json`, `import-quotes`, `import-url`, `stats` |
| `scripts/generate_demo_data.py` | Reproducible synthetic dataset |
| `web/` | UI: `app.js` (router/header), `views/explore.js`, `views/detail.js`, `views/pages.js`, `charts.js` |

## Design choices

* **No build step, few dependencies.** Python + 3 packages; the UI is plain ES modules. Anyone can clone and run in a minute.
* **In-memory index.** A city has at most a few thousand projects; summarising them in memory makes rich filters (trust score, red-flag counts, fair-price verdicts) trivial and fast. The index rebuilds after every write. To scale to all of India, move summaries into a materialised table or a search engine (Meilisearch/Elasticsearch) and keep the same API.
* **Computed, explainable insights.** Trust score components and every red flag carry their reason so users can judge them.
* **History, not snapshots.** Price quotes are appended with source + date, enabling trends, spreads and "price since you saved it".

## Extending

* **Add a city:** add it to `CITY_STATE` (and its state to `STATES`) in `catalog.py`, then import projects.
* **Postgres:** port `db.py` and the SQL in `repository.py` (`?` → `%s`); everything else is DB-agnostic.
* **Price alerts by email:** add a `watches` table and a scheduled job that compares the latest quote with the watched price.
