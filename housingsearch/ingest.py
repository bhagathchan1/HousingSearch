"""Importers that bring data into HousingSearch.

Sources supported out of the box
--------------------------------
1. JSON file  – full project records (see docs/DATA_FORMAT.md). Best for bulk loads,
                exports from RERA portals you have downloaded, or partner feeds/APIs.
2. CSV file   – price quotes you or a data partner collected
                (project, city, source, price, date ...). Ideal for tracking a
                shortlist across portals over time.
3. URL        – fetches ONE public page you point it at and extracts schema.org
                JSON-LD (most builder and listing pages publish this). Honours
                robots.txt and identifies itself; it never crawls.

Why no bulk scraper for housing.com / 99acres?  Their terms of use prohibit
automated scraping and they actively block it. HousingSearch instead (a) imports
data you are allowed to use, and (b) gives one-click "verify live" links to every
portal for each project. See docs/DATA_SOURCES.md for licensed data options.
"""

from __future__ import annotations

import csv
import json
import re
import urllib.request
import urllib.robotparser
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from . import config
from .repository import slugify, upsert_property


def import_json(conn, path: str | Path) -> int:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data["properties"] if isinstance(data, dict) else data
    n = 0
    for rec in records:
        upsert_property(conn, rec)
        n += 1
    conn.commit()
    return n


def import_records(conn, records: list[dict]) -> int:
    for rec in records:
        upsert_property(conn, rec)
    conn.commit()
    return len(records)


QUOTE_CSV_COLUMNS = ["project", "city", "locality", "config_label", "source", "source_url",
                     "price", "price_per_sqft", "quoted_on", "notes"]


def import_quotes_csv(conn, path: str | Path) -> dict:
    """Append price quotes. Each row must identify an existing project by name + city
    (locality optional, helps disambiguate)."""
    added, unmatched = 0, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            sql = "SELECT id, name, locality, city FROM properties WHERE lower(name)=lower(?) AND lower(city)=lower(?)"
            args = [row.get("project", ""), row.get("city", "")]
            if row.get("locality"):
                sql += " AND lower(locality)=lower(?)"
                args.append(row["locality"])
            p = conn.execute(sql, args).fetchone()
            if not p:
                unmatched.append(row.get("project"))
                continue
            upsert_property(conn, {
                "slug": conn.execute("SELECT slug FROM properties WHERE id=?", (p["id"],)).fetchone()["slug"],
                "name": p["name"], "city": p["city"], "locality": p["locality"],
                "price_quotes": [{
                    "config_label": row.get("config_label") or None,
                    "source": row.get("source") or "Manual entry",
                    "source_url": row.get("source_url") or None,
                    "price": _f(row.get("price")),
                    "price_per_sqft": _f(row.get("price_per_sqft")),
                    "quoted_on": row.get("quoted_on") or date.today().isoformat(),
                    "notes": row.get("notes") or None,
                }],
            })
            added += 1
    conn.commit()
    return {"added": added, "unmatched": sorted(set(filter(None, unmatched)))}


def _f(v):
    if v in (None, ""):
        return None
    v = str(v).replace(",", "").replace("₹", "").strip().lower()
    mult = 1
    if v.endswith("cr"):
        mult, v = 1e7, v[:-2]
    elif v.endswith("l") or v.endswith("lakh") or v.endswith("lac"):
        mult, v = 1e5, re.sub(r"(lakh|lac|l)$", "", v)
    try:
        return float(v) * mult
    except ValueError:
        return None


# ----------------------------------------------------------------- URL / JSON-LD
class FetchNotAllowed(Exception):
    pass


def _robots_allows(url: str) -> bool:
    parts = urlparse(url)
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(f"{parts.scheme}://{parts.netloc}/robots.txt")
    try:
        rp.read()
    except Exception:
        return False
    return rp.can_fetch(config.USER_AGENT, url)


def fetch_jsonld(url: str, timeout: int = 15) -> list[dict]:
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("Only http(s) URLs are supported")
    if not _robots_allows(url):
        raise FetchNotAllowed(f"robots.txt of {urlparse(url).netloc} disallows fetching this page")
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (scheme checked above)
        html = resp.read(3_000_000).decode("utf-8", "replace")
    return extract_jsonld(html)


def extract_jsonld(html: str) -> list[dict]:
    blocks = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I)
    out: list[dict] = []
    for b in blocks:
        try:
            data = json.loads(b.strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            d = stack.pop()
            if isinstance(d, dict):
                if "@graph" in d:
                    stack.extend(d["@graph"])
                out.append(d)
            elif isinstance(d, list):
                stack.extend(d)
    return out


def jsonld_to_record(items: list[dict], url: str, city: str, locality: str | None = None) -> dict | None:
    """Map schema.org Residence/Product/Offer/Place data to a HousingSearch record."""
    name, offers, addr, geo, rating = None, [], {}, {}, None
    for d in items:
        t = d.get("@type")
        types = t if isinstance(t, list) else [t]
        if any(x in ("Residence", "ApartmentComplex", "Apartment", "Product", "Place", "House",
                     "SingleFamilyResidence", "RealEstateListing", "Accommodation") for x in types):
            name = name or d.get("name")
            addr = addr or (d.get("address") if isinstance(d.get("address"), dict) else {})
            geo = geo or (d.get("geo") or {})
            rating = rating or d.get("aggregateRating")
            o = d.get("offers")
            if isinstance(o, dict):
                offers.append(o)
            elif isinstance(o, list):
                offers.extend(x for x in o if isinstance(x, dict))
        if "Offer" in types or "AggregateOffer" in types:
            offers.append(d)
    if not name:
        return None
    host = urlparse(url).netloc.replace("www.", "")
    today = date.today().isoformat()
    quotes = []
    for o in offers:
        for key in ("price", "lowPrice", "highPrice"):
            if o.get(key):
                quotes.append({"source": host, "source_url": url, "price": _f(o[key]),
                               "quoted_on": (o.get("validFrom") or today)[:10], "notes": f"schema.org {key}"})
    rec = {
        "name": name,
        "city": city,
        "locality": locality or addr.get("addressLocality") or city,
        "address": ", ".join(filter(None, [addr.get("streetAddress"), addr.get("addressLocality")])) or None,
        "pincode": addr.get("postalCode"),
        "lat": _f(geo.get("latitude")),
        "lng": _f(geo.get("longitude")),
        "price_quotes": quotes,
    }
    if rating and rating.get("ratingValue"):
        rec["reviews"] = [{"source": host, "url": url, "author": "Aggregate", "rating": _f(rating["ratingValue"]),
                           "posted_on": today, "title": f"Aggregate rating ({rating.get('reviewCount', '?')} reviews)",
                           "body": f"Aggregate rating published on {host}."}]
    rec["slug"] = slugify(rec["name"], rec["locality"], city)
    return {k: v for k, v in rec.items() if v not in (None, [], "")}
