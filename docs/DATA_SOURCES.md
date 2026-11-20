# Where real data comes from

HousingSearch ships with a **synthetic demo dataset** so every feature works out of the box. This page explains how to fill it with real data — legally and reliably.

## Why there is no built-in scraper for Housing.com, 99acres, MagicBricks…

Those portals' terms of use prohibit automated scraping, and they use bot protection. A scraper would break every few weeks and could get your IP or account blocked. HousingSearch takes a different approach:

1. **Import data you have the right to use** (below).
2. **"Verify live" links** on every project open a search for that exact project on each portal, forum and the official RERA portal, so the latest quote is one click away.
3. **Every price quote stores where and when it was quoted**, so you always know how fresh a number is.

## Recommended sources

| Data | Source | How to bring it in |
|---|---|---|
| RERA registration, possession date, progress, approvals uploaded by the builder | State RERA portals (K-RERA, MahaRERA, TG RERA, TNRERA, HRERA, UP RERA) | Download/record per project → JSON import. Several states publish project lists; some offer data on request. |
| Price quotes | Your own research across portals, builder cost sheets, broker quotes | Keep a CSV (`examples/sample_quotes.csv`) and run `import-quotes` weekly. |
| Bulk listings & prices | Licensed data providers (property-analytics firms, portal partner APIs) | Convert their feed to the JSON format and `POST /api/admin/import` on a schedule. |
| Builder & listing pages with schema.org data | Builder websites, some listing pages | `python -m housingsearch import-url URL --city X` (honours robots.txt, one page at a time). |
| Reviews | Reddit, Google Maps, forums, owners' groups | Record title, text, link, date → JSON import. Keep the original link. |
| Litigation | RERA complaint orders, e-Courts, e-Daakhil (consumer commission) | JSON import with case reference and link. |
| Stamp duty, registration | State IGR / sub-registrar sites | Edit `housingsearch/catalog.py` (`STATES`). |

## Commands

```bash
python -m housingsearch import-json my_projects.json
python -m housingsearch import-quotes my_quotes.csv
python -m housingsearch import-url https://builder.example.com/project --city Pune --locality Baner
python -m housingsearch stats
```

## Scheduled feeds via the API

```bash
export HS_ADMIN_TOKEN=change-me          # on the server
curl -X POST http://localhost:8000/api/admin/import \
     -H "X-Admin-Token: change-me" -H "Content-Type: application/json" \
     --data @my_projects.json
```

## Removing the demo data

```bash
rm data/housingsearch.db                    # start empty…
HS_DB_PATH=data/real.db python -m housingsearch import-json my_projects.json
HS_DB_PATH=data/real.db python -m housingsearch serve
```

The server only auto-loads the demo file when the database is empty. To stop that entirely, delete or rename `data/seed/demo_properties.json`.

## Writing a custom importer

Every importer ends by calling `repository.upsert_property(conn, record)` with a dict in the JSON format. To add a new source (for example a partner API), write a function that fetches and maps records, then call `ingest.import_records(conn, records)`. Respect each site's terms and robots.txt.
