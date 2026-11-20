"""Data access + in-memory search index.

All projects are summarised into a lightweight index held in memory (a city has
at most a few thousand projects, so this is fast and keeps filtering flexible).
The index is rebuilt whenever data is written.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
import statistics
import threading
from datetime import datetime

from . import catalog, insights
from .db import row_to_dict

_lock = threading.Lock()


def _children(conn, table: str, pid: int, order: str = "id") -> list[dict]:
    return [dict(r) for r in conn.execute(f"SELECT * FROM {table} WHERE property_id=? ORDER BY {order}", (pid,))]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower()).strip()


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._index: list[dict] | None = None
        self._details: dict[int, dict] = {}

    # ------------------------------------------------------------------ indexing
    def invalidate(self) -> None:
        with _lock:
            self._index = None
            self._details.clear()

    def index(self) -> list[dict]:
        with _lock:
            if self._index is None:
                self._index = self._build_index()
            return self._index

    def _build_index(self) -> list[dict]:
        conn = self.conn
        builders = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM builders")}
        props = [row_to_dict(r) for r in conn.execute("SELECT * FROM properties")]
        confs = _group(conn, "configurations")
        quotes = _group(conn, "price_quotes")
        apprs = _group(conn, "approvals")
        revs = _group(conn, "reviews")
        lits = _group(conn, "litigation")

        # locality price-per-sqft medians feed the fair-price check
        loc_psf: dict[tuple, list[float]] = {}
        price_sum: dict[int, dict] = {}
        for p in props:
            ps = insights.price_summary(quotes.get(p["id"], []))
            price_sum[p["id"]] = ps
            if ps.get("psf_median"):
                loc_psf.setdefault((p["city"], p["locality"]), []).append(ps["psf_median"])

        out = []
        for p in props:
            pid = p["id"]
            b = builders.get(p.get("builder_id"))
            cs = confs.get(pid, [])
            ps = price_sum[pid]
            dl = insights.delivery_summary(p)
            ap = insights.approvals_summary(p, apprs.get(pid, []))
            rv = insights.reviews_summary(revs.get(pid, []))
            lt = lits.get(pid, [])
            fp = insights.fair_price(ps.get("psf_median"), loc_psf.get((p["city"], p["locality"]), []))
            ts = insights.trust_score(p, b, dl, ap, rv, lt)
            flags = insights.red_flags(p, b, ps, dl, ap, rv, lt)
            prices = [c["price_min"] for c in cs if c.get("price_min")] + [c["price_max"] for c in cs if c.get("price_max")]
            sizes = [c["super_builtup_sqft"] or c["carpet_sqft"] for c in cs if (c.get("super_builtup_sqft") or c.get("carpet_sqft"))]
            out.append({
                "id": pid,
                "slug": p["slug"],
                "name": p["name"],
                "builder": b["name"] if b else None,
                "builder_id": p.get("builder_id"),
                "city": p["city"],
                "state": p["state"],
                "locality": p["locality"],
                "pincode": p.get("pincode"),
                "lat": p.get("lat"),
                "lng": p.get("lng"),
                "property_type": p.get("property_type"),
                "status": p.get("status"),
                "rera_status": p.get("rera_status"),
                "rera_number": p.get("rera_number"),
                "possession_date": p.get("rera_possession_date"),
                "builder_possession_date": p.get("builder_possession_date"),
                "price_min": min(prices) if prices else None,
                "price_max": max(prices) if prices else None,
                "size_min": min(sizes) if sizes else None,
                "size_max": max(sizes) if sizes else None,
                "bhk": sorted({c["bhk"] for c in cs if c.get("bhk") is not None}),
                "configs": [c["label"] for c in cs],
                "total_units": p.get("total_units"),
                "available_units": p.get("available_units"),
                "psf": ps.get("psf_median"),
                "price_change_12m": ps.get("change_12m_pct"),
                "latest_quote_date": ps.get("latest_quote_date"),
                "source_count": ps.get("source_count", 0),
                "fair_price": fp,
                "approvals_pct": ap.get("completeness_pct"),
                "approvals_missing": ap.get("missing_count"),
                "review_count": rv.get("count", 0),
                "avg_rating": rv.get("avg_rating"),
                "trust_score": ts["score"],
                "trust_grade": ts["grade"],
                "flags_critical": sum(1 for f in flags if f["level"] == "critical"),
                "flags_warning": sum(1 for f in flags if f["level"] == "warning"),
                "top_flag": flags[0]["title"] if flags and flags[0]["level"] != "info" else None,
                "amenities": p.get("amenities") or [],
                "overdue_months": dl.get("overdue_months"),
                "is_demo": bool(p.get("is_demo")),
                "updated_at": p.get("updated_at"),
                "_search": _norm(" ".join(filter(None, [
                    p["name"], b["name"] if b else "", p["locality"], p["city"], p.get("rera_number"),
                    p.get("pincode"), p.get("address"), p.get("property_type")]))),
            })
        return out

    # ------------------------------------------------------------------ queries
    def search(self, f: dict) -> dict:
        items = self.index()
        q = _norm(f.get("q") or "")
        scored: list[tuple[float, dict]] = []
        for it in items:
            if not _passes(it, f):
                continue
            score = _match_score(q, it) if q else 1.0
            if score > 0:
                scored.append((score, it))

        sort = f.get("sort") or ("relevance" if q else "trust")
        keyfuncs = {
            "relevance": lambda t: (-t[0], -t[1]["trust_score"]),
            "trust": lambda t: -t[1]["trust_score"],
            "price_asc": lambda t: t[1]["price_min"] or 1e15,
            "price_desc": lambda t: -(t[1]["price_max"] or 0),
            "psf_asc": lambda t: t[1]["psf"] or 1e9,
            "psf_desc": lambda t: -(t[1]["psf"] or 0),
            "possession": lambda t: t[1]["possession_date"] or "9999",
            "rating": lambda t: -(t[1]["avg_rating"] or 0),
            "appreciation": lambda t: -(t[1]["price_change_12m"] or -999),
            "name": lambda t: t[1]["name"].lower(),
        }
        scored.sort(key=keyfuncs.get(sort, keyfuncs["trust"]))
        results = [{k: v for k, v in it.items() if not k.startswith("_")} for _, it in scored]

        page = max(int(f.get("page") or 1), 1)
        size = min(max(int(f.get("page_size") or 24), 1), 200)
        start = (page - 1) * size
        return {
            "total": len(results),
            "page": page,
            "page_size": size,
            "results": results[start:start + size],
            "facets": _facets([it for _, it in scored]),
        }

    def suggest(self, q: str, city: str | None = None, limit: int = 8) -> list[dict]:
        qn = _norm(q)
        if not qn:
            return []
        hits = []
        for it in self.index():
            if city and it["city"] != city:
                continue
            s = _match_score(qn, it)
            if s > 0:
                hits.append((s, it))
        hits.sort(key=lambda t: -t[0])
        out = [{"id": it["id"], "name": it["name"], "builder": it["builder"], "locality": it["locality"],
                "city": it["city"], "type": "project"} for _, it in hits[:limit]]
        # locality suggestions
        seen = set()
        for it in self.index():
            key = (it["city"], it["locality"])
            if key in seen or (city and it["city"] != city):
                continue
            if _norm(it["locality"]).startswith(qn) or qn in _norm(it["locality"]):
                seen.add(key)
                out.append({"name": it["locality"], "city": it["city"], "type": "locality"})
        return out[: limit + 4]

    def detail(self, pid: int) -> dict | None:
        if pid in self._details:
            return self._details[pid]
        conn = self.conn
        p = row_to_dict(conn.execute("SELECT * FROM properties WHERE id=?", (pid,)).fetchone())
        if not p:
            return None
        b = row_to_dict(conn.execute("SELECT * FROM builders WHERE id=?", (p.get("builder_id"),)).fetchone())
        confs = _children(conn, "configurations", pid, "bhk, carpet_sqft")
        quotes = _children(conn, "price_quotes", pid, "quoted_on DESC")
        apprs = _children(conn, "approvals", pid)
        revs = _children(conn, "reviews", pid, "posted_on DESC")
        lits = _children(conn, "litigation", pid, "filed_on DESC")
        near = _children(conn, "nearby", pid, "distance_km")
        for r in revs:
            r["sentiment"] = r.get("sentiment") or insights.classify_sentiment(
                f"{r.get('title','')} {r.get('body','')}", r.get("rating"))

        idx = {it["id"]: it for it in self.index()}
        loc_psf = [it["psf"] for it in idx.values()
                   if it["city"] == p["city"] and it["locality"] == p["locality"] and it["psf"]]
        ps = insights.price_summary(quotes)
        dl = insights.delivery_summary(p)
        ap = insights.approvals_summary(p, apprs)
        rv = insights.reviews_summary(revs)
        fp = insights.fair_price(ps.get("psf_median"), loc_psf)
        ts = insights.trust_score(p, b, dl, ap, rv, lits)
        flags = insights.red_flags(p, b, ps, dl, ap, rv, lits)

        # similar projects: same city, overlapping price band, nearest psf
        me = idx.get(pid, {})
        similar = sorted(
            (it for it in idx.values() if it["id"] != pid and it["city"] == p["city"] and it["psf"]),
            key=lambda it: (it["locality"] != p["locality"], abs((it["psf"] or 0) - (me.get("psf") or 0))),
        )[:6]

        detail = {
            "property": p,
            "builder": b,
            "configurations": confs,
            "price_quotes": quotes,
            "latest_quotes": insights.latest_quotes_by_source(quotes),
            "prices": ps,
            "fair_price": fp,
            "delivery": dl,
            "approvals": ap,
            "reviews": revs,
            "reviews_summary": rv,
            "litigation": lits,
            "nearby": near,
            "trust": ts,
            "red_flags": flags,
            "verify_links": insights.verify_links(p),
            "state_costs": catalog.STATES.get(p["state"], {}),
            "gst": catalog.GST,
            "similar": [{k: v for k, v in s.items() if not k.startswith("_")} for s in similar],
            "summary": {k: v for k, v in me.items() if not k.startswith("_")},
        }
        self._details[pid] = detail
        return detail

    def meta(self) -> dict:
        idx = self.index()
        cities: dict[str, dict] = {}
        for it in idx:
            c = cities.setdefault(it["city"], {"city": it["city"], "state": it["state"], "count": 0, "localities": {}})
            c["count"] += 1
            c["localities"][it["locality"]] = c["localities"].get(it["locality"], 0) + 1
        city_list = [
            {**c, "localities": [{"name": k, "count": v} for k, v in sorted(c["localities"].items())]}
            for c in sorted(cities.values(), key=lambda c: -c["count"])
        ]
        amen: dict[str, int] = {}
        for it in idx:
            for a in it["amenities"]:
                amen[a] = amen.get(a, 0) + 1
        prices = [it["price_min"] for it in idx if it["price_min"]]
        last_update = max((it["latest_quote_date"] or "" for it in idx), default=None)
        return {
            "total_properties": len(idx),
            "cities": city_list,
            "builders": sorted({it["builder"] for it in idx if it["builder"]}),
            "property_types": sorted({it["property_type"] for it in idx if it["property_type"]}),
            "statuses": ["Pre-launch", "Under Construction", "Ready to Move"],
            "rera_statuses": sorted({it["rera_status"] for it in idx if it["rera_status"]}),
            "amenities": [a for a, _ in sorted(amen.items(), key=lambda t: -t[1])],
            "price_range": [min(prices), max(prices)] if prices else [0, 0],
            "has_demo_data": any(it["is_demo"] for it in idx),
            "last_price_update": last_update,
            "approvals_catalog": catalog.APPROVALS,
            "states": catalog.STATES,
        }

    def locality_stats(self, city: str) -> list[dict]:
        groups: dict[str, list[dict]] = {}
        for it in self.index():
            if it["city"] == city:
                groups.setdefault(it["locality"], []).append(it)
        out = []
        for loc, items in groups.items():
            psf = [i["psf"] for i in items if i["psf"]]
            chg = [i["price_change_12m"] for i in items if i["price_change_12m"] is not None]
            out.append({
                "locality": loc,
                "projects": len(items),
                "median_psf": round(statistics.median(psf)) if psf else None,
                "min_psf": round(min(psf)) if psf else None,
                "max_psf": round(max(psf)) if psf else None,
                "avg_change_12m": round(sum(chg) / len(chg), 1) if chg else None,
                "ready_to_move": sum(1 for i in items if i["status"] == "Ready to Move"),
                "avg_trust": round(sum(i["trust_score"] for i in items) / len(items)),
                "lat": statistics.mean([i["lat"] for i in items if i["lat"]]) if any(i["lat"] for i in items) else None,
                "lng": statistics.mean([i["lng"] for i in items if i["lng"]]) if any(i["lng"] for i in items) else None,
            })
        return sorted(out, key=lambda r: -(r["median_psf"] or 0))

    def builder_detail(self, bid: int) -> dict | None:
        b = row_to_dict(self.conn.execute("SELECT * FROM builders WHERE id=?", (bid,)).fetchone())
        if not b:
            return None
        projects = [{k: v for k, v in it.items() if not k.startswith("_")} for it in self.index() if it["builder_id"] == bid]
        return {"builder": b, "projects": projects}


# ---------------------------------------------------------------------- helpers
def _group(conn, table: str) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in conn.execute(f"SELECT * FROM {table}"):
        out.setdefault(r["property_id"], []).append(dict(r))
    return out


def _match_score(q: str, it: dict) -> float:
    hay = it["_search"]
    if q in hay:
        bonus = 3 if _norm(it["name"]).startswith(q) else 2 if q in _norm(it["name"]) else 1
        return 10 + bonus
    tokens = q.split()
    words = hay.split()
    score = 0.0
    for t in tokens:
        if t in hay:
            score += 2
            continue
        # tolerate typos: "prestge" -> "prestige"
        best = max((difflib.SequenceMatcher(None, t, w).ratio() for w in words), default=0)
        if best >= 0.8:
            score += best
        else:
            return 0
    return score


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _list(v) -> list[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [x for x in v if x]
    return [x.strip() for x in str(v).split(",") if x.strip()]


def _passes(it: dict, f: dict) -> bool:
    if f.get("city") and it["city"] != f["city"]:
        return False
    locs = _list(f.get("locality"))
    if locs and it["locality"] not in locs:
        return False
    builders = _list(f.get("builder"))
    if builders and it["builder"] not in builders:
        return False
    types = _list(f.get("property_type"))
    if types and it["property_type"] not in types:
        return False
    statuses = _list(f.get("status"))
    if statuses and it["status"] not in statuses:
        return False
    rera = _list(f.get("rera_status"))
    if rera and it["rera_status"] not in rera:
        return False
    if f.get("rera_only") in ("1", "true", True) and it["rera_status"] != "Registered":
        return False
    bhks = [float(b) for b in _list(f.get("bhk"))]
    if bhks:
        # "4" means 4+ BHK
        if not any((b >= 4 and any(x >= 4 for x in it["bhk"])) or b in it["bhk"] for b in bhks):
            return False
    lo, hi = _num(f.get("min_price")), _num(f.get("max_price"))
    if lo is not None and (it["price_max"] or 0) < lo:
        return False
    if hi is not None and (it["price_min"] or 1e15) > hi:
        return False
    slo, shi = _num(f.get("min_size")), _num(f.get("max_size"))
    if slo is not None and (it["size_max"] or 0) < slo:
        return False
    if shi is not None and (it["size_min"] or 1e9) > shi:
        return False
    plo, phi = _num(f.get("min_psf")), _num(f.get("max_psf"))
    if plo is not None and (it["psf"] or 0) < plo:
        return False
    if phi is not None and (it["psf"] or 1e9) > phi:
        return False
    if f.get("possession_by"):
        if it["status"] != "Ready to Move" and (not it["possession_date"] or it["possession_date"][:7] > f["possession_by"][:7]):
            return False
    ms = _num(f.get("min_trust"))
    if ms is not None and it["trust_score"] < ms:
        return False
    mr = _num(f.get("min_rating"))
    if mr is not None and (it["avg_rating"] or 0) < mr:
        return False
    if f.get("no_red_flags") in ("1", "true", True) and it["flags_critical"]:
        return False
    if f.get("all_approvals") in ("1", "true", True) and it["approvals_missing"]:
        return False
    if f.get("available_only") in ("1", "true", True) and not it["available_units"]:
        return False
    amen = _list(f.get("amenities"))
    if amen and not all(a in it["amenities"] for a in amen):
        return False
    fair = _list(f.get("fair_price"))
    if fair and it["fair_price"]["verdict"] not in fair:
        return False
    return True


def _facets(items: list[dict]) -> dict:
    def count(key):
        c: dict = {}
        for it in items:
            v = it.get(key)
            if v:
                c[v] = c.get(v, 0) + 1
        return c

    bhk: dict = {}
    for it in items:
        for b in it["bhk"]:
            k = "4+" if b >= 4 else str(int(b)) if b == int(b) else str(b)
            bhk[k] = bhk.get(k, 0) + 1
    return {
        "locality": count("locality"),
        "status": count("status"),
        "property_type": count("property_type"),
        "rera_status": count("rera_status"),
        "builder": count("builder"),
        "bhk": bhk,
    }


# ------------------------------------------------------------------- writes
def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def upsert_builder(conn, b: dict) -> int:
    row = conn.execute("SELECT id FROM builders WHERE name=?", (b["name"],)).fetchone()
    cols = ["established_year", "projects_delivered", "projects_ongoing", "on_time_delivery_pct",
            "avg_delay_months", "rera_complaints", "website", "description"]
    if row:
        sets = [c for c in cols if c in b]
        if sets:
            conn.execute(f"UPDATE builders SET {', '.join(c + '=?' for c in sets)} WHERE id=?",
                         [b[c] for c in sets] + [row["id"]])
        return row["id"]
    cur = conn.execute(
        f"INSERT INTO builders (name, {', '.join(cols)}) VALUES (?{', ?' * len(cols)})",
        [b["name"]] + [b.get(c) for c in cols],
    )
    return cur.lastrowid


PROPERTY_COLS = [
    "name", "city", "state", "locality", "address", "pincode", "lat", "lng", "property_type", "status",
    "launch_date", "rera_number", "rera_status", "rera_authority", "rera_url", "rera_possession_date",
    "builder_possession_date", "construction_progress", "total_units", "available_units", "towers", "floors",
    "land_area_acres", "open_space_pct", "amenities", "bank_approvals", "description", "is_demo",
]

CHILD_TABLES = {
    "configurations": ["label", "bhk", "carpet_sqft", "super_builtup_sqft", "price_min", "price_max",
                       "units_total", "units_available", "facing"],
    "price_quotes": ["config_label", "source", "source_url", "price", "price_per_sqft", "quoted_on", "notes"],
    "approvals": ["code", "status", "reference", "issued_on", "document_url", "notes"],
    "reviews": ["source", "url", "author", "rating", "posted_on", "title", "body", "sentiment"],
    "litigation": ["forum", "case_ref", "filed_on", "status", "summary", "url"],
    "nearby": ["category", "name", "distance_km"],
}


def slugify(*parts: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", " ".join(parts).lower())).strip("-")


def upsert_property(conn, rec: dict, replace_children: bool = False) -> int:
    """Insert or merge one project record (the JSON import format, see docs/DATA_FORMAT.md).

    Matching: by `slug` if given, else by RERA number, else by name + locality + city.
    Price quotes, reviews and litigation are appended (deduplicated); configurations
    and approvals are replaced when supplied, since they describe current state.
    """
    rec = dict(rec)
    if not rec.get("state"):
        rec["state"] = catalog.CITY_STATE.get(rec.get("city", ""), rec.get("state") or "")
    if rec.get("state") in catalog.STATES:
        rec.setdefault("rera_url", catalog.STATES[rec["state"]]["rera_url"])
        rec.setdefault("rera_authority", catalog.STATES[rec["state"]]["rera_name"])
    for k in ("amenities", "bank_approvals"):
        if k in rec and not isinstance(rec[k], str):
            rec[k] = json.dumps(rec[k] or [])
    builder_id = None
    if rec.get("builder"):
        b = rec["builder"] if isinstance(rec["builder"], dict) else {"name": rec["builder"]}
        builder_id = upsert_builder(conn, b)

    slug = rec.get("slug") or slugify(rec["name"], rec.get("locality", ""), rec.get("city", ""))
    row = conn.execute("SELECT id FROM properties WHERE slug=?", (slug,)).fetchone()
    if not row and rec.get("rera_number"):
        row = conn.execute("SELECT id FROM properties WHERE rera_number=?", (rec["rera_number"],)).fetchone()

    present = [c for c in PROPERTY_COLS if c in rec]
    if row:
        pid = row["id"]
        sets = present + (["builder_id"] if builder_id else []) + ["updated_at"]
        vals = [rec[c] for c in present] + ([builder_id] if builder_id else []) + [now_iso()]
        conn.execute(f"UPDATE properties SET {', '.join(s + '=?' for s in sets)} WHERE id=?", vals + [pid])
    else:
        cols = ["slug", "builder_id", "updated_at"] + present
        vals = [slug, builder_id, now_iso()] + [rec[c] for c in present]
        pid = conn.execute(
            f"INSERT INTO properties ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", vals
        ).lastrowid

    for table, cols in CHILD_TABLES.items():
        rows = rec.get(table)
        if rows is None:
            continue
        replace = replace_children or table in ("configurations", "approvals", "nearby")
        if replace:
            conn.execute(f"DELETE FROM {table} WHERE property_id=?", (pid,))
        for r in rows:
            if not replace and table in ("price_quotes", "reviews", "litigation"):
                key = {"price_quotes": ("source", "quoted_on", "config_label"),
                       "reviews": ("source", "author", "posted_on", "title"),
                       "litigation": ("forum", "case_ref")}[table]
                where = " AND ".join(f"COALESCE({k},'')=COALESCE(?,'')" for k in key)
                if conn.execute(f"SELECT 1 FROM {table} WHERE property_id=? AND {where}",
                                [pid] + [r.get(k) for k in key]).fetchone():
                    continue
            conn.execute(
                f"INSERT INTO {table} (property_id, {', '.join(cols)}) VALUES (?{', ?' * len(cols)})",
                [pid] + [r.get(c) for c in cols],
            )
    return pid
