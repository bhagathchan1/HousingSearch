# Where real data comes from

HousingSearch ships with **real project lists from four state RERA registers** (`data/seed/rera_*.json`), plus a **synthetic demo dataset** that is used only when no real data is present (or with `HS_DEMO=1`). This page explains where the data comes from and how to add more — legally and reliably.

## State RERA registers (built in)

```bash
python -m housingsearch import-rera ka hr tn mh                 # update the database
python -m housingsearch import-rera ka --details --save-seed    # Karnataka with addresses, map locations and unit mix
```

| Code | Register | City in the app | What's imported | How |
|---|---|---|---|---|
| `ka` | [RERA Karnataka](https://rera.karnataka.gov.in/viewAllProjects) | Bengaluru (Urban + Rural districts) | Every residential project: RERA number, promoter, taluk, type, approval date, proposed completion date and extensions, completion status. With `--details`: address, PIN, coordinates, unit mix (BHK, count, carpet area) | One search per district, plus one page per project for details (newest ongoing first, `--details-limit`) |
| `hr` | [HRERA Gurugram](https://haryanarera.gov.in/admincontrol/registered_projects/2) | Gurugram | RERA certificate, project ID, builder, sector, registration validity, lapsed status, OC/CC uploaded, link to the project page. Commercial projects are skipped by name | One page |
| `tn` | [TNRERA](https://rera.tn.gov.in/registered-building/tn) | Chennai metro (Chennai, Kancheepuram, Chengalpattu, Tiruvallur) | RERA number, promoter, project description, planning/building permission references, completion date, coordinates, progress status | One page per year (the portal offers the last three years) |
| `mh` | [MahaRERA](https://maharera.maharashtra.gov.in/projects-search-result) | Mumbai, Thane, Pune | RERA number, project, promoter, taluka, PIN, coordinates, link to the full application | 10 projects per page; the newest `--max-pages` pages per district (default 60 ≈ 600 projects) |

How the importers behave:
* They identify themselves (`HS_USER_AGENT`), honour robots.txt, wait `--delay` seconds (default 2) between requests to a portal, and cache every page in `data/cache/rera`, so re-runs don't hit the portals again (`--refresh` to re-download).
* Projects keep a stable id (`rera-<state>-<registration number>`), so re-importing updates them and keeps any prices or reviews you added.
* `--save-seed` writes `data/seed/rera_<state>.json`; a fresh deployment (e.g. Render) loads those files on start.

What the registers **don't** contain: prices, availability, reviews, and (except Tamil Nadu's planning permission and Gurugram's OC/CC) individual approval documents. The app shows these as "not published" / "not verified" rather than guessing, and the trust score is marked **limited data** until enough is known.

Not covered:
* **Telangana (Hyderabad):** TG RERA protects its project search with a CAPTCHA, so HousingSearch never queries it. Two ways to get Hyderabad projects:
  1. **Saved pages (quick):** search the [TG RERA portal](https://rerait.telangana.gov.in/SearchList/Search) yourself — "Registered" projects, district *Hyderabad*, *Ranga Reddy*, *Medchal-Malkajgiri* or *Sangareddy* — type the CAPTCHA, save the results page (Ctrl/Cmd+S), then run `python -m housingsearch import-rera tg --from-file page1.html page2.html --save-seed`. The importer finds the results table by its column headings and keeps only the Hyderabad region.
  2. **RTI (complete list):** request the full register as a spreadsheet with the ready-to-send letter in [RTI_TG_RERA.md](RTI_TG_RERA.md).
* **Uttar Pradesh (Noida):** the UP RERA portal was down for maintenance when the importers were built; worth re-checking.

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
