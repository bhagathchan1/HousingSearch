"""FastAPI application: JSON API under /api and the web UI at /."""

from __future__ import annotations

import csv
import io
import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, db, ingest
from .repository import Repository


def seed_files(demo: str = config.DEMO) -> list[Path]:
    """Seed files to load into an empty database.

    Real data (data/seed/rera_*.json etc.) is preferred. The synthetic demo dataset is
    used when there is no real data, or always/never with HS_DEMO=1/0.
    """
    real = sorted(p for p in config.SEED_DIR.glob("*.json") if p != config.SEED_FILE)
    use_demo = demo in ("1", "true", "yes", "always") or (demo == "auto" and not real)
    if demo in ("0", "false", "no", "never"):
        use_demo = False
    return real + ([config.SEED_FILE] if use_demo and config.SEED_FILE.exists() else [])


def create_app(db_path: str | Path | None = None, seed_if_empty: bool = True,
               seeds: list[Path] | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = db.connect(db_path)
        db.init_schema(conn)
        if seed_if_empty and db.is_empty(conn):
            for f in seeds if seeds is not None else seed_files():
                ingest.import_json(conn, f)
        app.state.conn = conn
        app.state.repo = Repository(conn)
        yield
        conn.close()

    app = FastAPI(
        title="HousingSearch API",
        version=__version__,
        description="Aggregated residential project data: prices by source, RERA, approvals, delivery, reviews.",
        lifespan=lifespan,
    )

    def repo(request: Request) -> Repository:
        return request.app.state.repo

    def require_admin(x_admin_token: str | None = Header(default=None)):
        if not config.ADMIN_TOKEN:
            raise HTTPException(403, "Write API disabled. Set HS_ADMIN_TOKEN to enable it.")
        if x_admin_token != config.ADMIN_TOKEN:
            raise HTTPException(401, "Invalid admin token")

    # ------------------------------------------------------------------ read API
    @app.get("/api/health")
    def health(r: Repository = Depends(repo)):
        return {"ok": True, "version": __version__, "properties": len(r.index())}

    @app.get("/api/meta")
    def meta(r: Repository = Depends(repo)):
        return r.meta()

    @app.get("/api/properties")
    def list_properties(
        request: Request,
        q: str | None = None,
        city: str | None = None,
        sort: str | None = None,
        page: int = 1,
        page_size: int = Query(24, le=200),
        r: Repository = Depends(repo),
    ):
        """Search & filter. Multi-value filters accept comma-separated values.

        Filters: locality, builder, property_type, status, rera_status, bhk (1,2,3,4=4+),
        min_price, max_price (INR), min_size, max_size (sq ft), min_psf, max_psf,
        possession_by (YYYY-MM), min_trust, min_rating, amenities, fair_price,
        rera_only, no_red_flags, all_approvals, available_only.
        Sort: relevance, trust, price_asc, price_desc, psf_asc, psf_desc, possession,
        rating, appreciation, name.
        """
        f = dict(request.query_params)
        f.update({"q": q, "city": city, "sort": sort, "page": page, "page_size": page_size})
        return r.search(f)

    @app.get("/api/properties/export.csv")
    def export_csv(request: Request, r: Repository = Depends(repo)):
        f = dict(request.query_params)
        f["page_size"] = 200
        rows, page = [], 1
        while True:
            f["page"] = page
            res = r.search(f)
            rows += res["results"]
            if len(rows) >= res["total"] or not res["results"]:
                break
            page += 1
        cols = ["name", "builder", "city", "locality", "property_type", "status", "rera_status", "rera_number",
                "possession_date", "price_min", "price_max", "psf", "price_change_12m", "configs", "available_units",
                "approvals_pct", "avg_rating", "review_count", "trust_score", "top_flag"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        for it in rows:
            w.writerow(["; ".join(it[c]) if isinstance(it[c], list) else it[c] for c in cols])
        buf.seek(0)
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": "attachment; filename=housingsearch.csv"})

    @app.get("/api/properties/{pid}")
    def property_detail(pid: int, r: Repository = Depends(repo)):
        d = r.detail(pid)
        if not d:
            raise HTTPException(404, "Property not found")
        return d

    @app.get("/api/suggest")
    def suggest(q: str, city: str | None = None, r: Repository = Depends(repo)):
        return r.suggest(q, city)

    @app.get("/api/compare")
    def compare(ids: str, r: Repository = Depends(repo)):
        out = []
        for s in ids.split(",")[:4]:
            if s.strip().isdigit() and (d := r.detail(int(s))):
                out.append(d)
        return out

    @app.get("/api/localities/{city}")
    def localities(city: str, r: Repository = Depends(repo)):
        return r.locality_stats(city)

    @app.get("/api/builders/{bid}")
    def builder(bid: int, r: Repository = Depends(repo)):
        d = r.builder_detail(bid)
        if not d:
            raise HTTPException(404, "Builder not found")
        return d

    # ----------------------------------------------------------------- write API
    @app.post("/api/admin/import", dependencies=[Depends(require_admin)])
    async def admin_import(request: Request, r: Repository = Depends(repo)):
        """Body: {"properties": [ ...records... ]} — same format as the JSON importer."""
        body = await request.json()
        records = body.get("properties") if isinstance(body, dict) else body
        if not isinstance(records, list):
            raise HTTPException(400, "Expected a list of property records")
        n = ingest.import_records(request.app.state.conn, records)
        r.invalidate()
        return {"imported": n}

    @app.post("/api/admin/import-url", dependencies=[Depends(require_admin)])
    async def admin_import_url(request: Request, r: Repository = Depends(repo)):
        body = await request.json()
        try:
            items = ingest.fetch_jsonld(body["url"])
        except ingest.FetchNotAllowed as e:
            raise HTTPException(403, str(e))
        except Exception as e:  # network / parse errors
            raise HTTPException(502, f"Could not fetch page: {e}")
        rec = ingest.jsonld_to_record(items, body["url"], body.get("city", ""), body.get("locality"))
        if not rec:
            raise HTTPException(422, "No schema.org property data found on that page")
        ingest.import_records(request.app.state.conn, [rec])
        r.invalidate()
        return {"imported": rec}

    # ------------------------------------------------------------------- web UI
    @app.middleware("http")
    async def revalidate_ui(request: Request, call_next):
        # The UI is plain ES modules without hashed filenames, so browsers must revalidate
        # them (cheap 304s via ETag) or they keep running old code after a deploy.
        response = await call_next(request)
        if not request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/static", StaticFiles(directory=config.WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(config.WEB_DIR / "index.html")

    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": getattr(exc, "detail", "Not found")}, status_code=404)
        return FileResponse(config.WEB_DIR / "index.html")

    return app


app = create_app()
