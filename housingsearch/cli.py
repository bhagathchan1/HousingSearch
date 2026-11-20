"""Command line: run the server and manage data.

    python -m housingsearch serve                 # start web app (default)
    python -m housingsearch seed --reset          # (re)load the demo dataset
    python -m housingsearch import-json FILE      # import project records
    python -m housingsearch import-quotes FILE    # append price quotes from CSV
    python -m housingsearch import-url URL --city Bengaluru [--locality X]
    python -m housingsearch stats                 # print database summary
"""

from __future__ import annotations

import argparse
import json
import sys

from . import config, db, ingest


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="housingsearch", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=None, help=f"SQLite file (default {config.DB_PATH})")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="run the web app")
    s.add_argument("--host", default=config.HOST)
    s.add_argument("--port", type=int, default=config.PORT)
    s.add_argument("--reload", action="store_true")

    sd = sub.add_parser("seed", help="load demo data")
    sd.add_argument("--reset", action="store_true", help="delete existing data first")

    ij = sub.add_parser("import-json")
    ij.add_argument("file")
    iq = sub.add_parser("import-quotes")
    iq.add_argument("file")
    iu = sub.add_parser("import-url")
    iu.add_argument("url")
    iu.add_argument("--city", required=True)
    iu.add_argument("--locality")
    sub.add_parser("stats")

    a = p.parse_args(argv)
    cmd = a.cmd or "serve"

    if cmd == "serve":
        import uvicorn

        uvicorn.run("housingsearch.api:app", host=getattr(a, "host", config.HOST),
                    port=getattr(a, "port", config.PORT), reload=getattr(a, "reload", False))
        return 0

    conn = db.connect(a.db)
    db.init_schema(conn)

    if cmd == "seed":
        if a.reset:
            conn.executescript("DELETE FROM properties; DELETE FROM builders;")
        if not config.SEED_FILE.exists():
            print("Seed file missing. Generate it: python scripts/generate_demo_data.py", file=sys.stderr)
            return 1
        print(f"Imported {ingest.import_json(conn, config.SEED_FILE)} demo projects")
    elif cmd == "import-json":
        print(f"Imported {ingest.import_json(conn, a.file)} records from {a.file}")
    elif cmd == "import-quotes":
        print(json.dumps(ingest.import_quotes_csv(conn, a.file), indent=2))
    elif cmd == "import-url":
        items = ingest.fetch_jsonld(a.url)
        rec = ingest.jsonld_to_record(items, a.url, a.city, a.locality)
        if not rec:
            print("No schema.org property data found on that page", file=sys.stderr)
            return 2
        ingest.import_records(conn, [rec])
        print(json.dumps(rec, indent=2, ensure_ascii=False))
    elif cmd == "stats":
        for t in ("builders", "properties", "configurations", "price_quotes", "approvals", "reviews",
                  "litigation", "nearby"):
            print(f"{t:16} {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>7}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
