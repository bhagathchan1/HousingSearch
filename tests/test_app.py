"""End-to-end tests for the API, importers and insight calculations.

Run with:  pytest -q
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from housingsearch import catalog, config, db, ingest, insights
from housingsearch.api import create_app

ROOT = config.ROOT_DIR


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "test.db"
    with TestClient(create_app(db_path=path)) as c:
        yield c


# ------------------------------------------------------------------ API
def test_health_and_meta(client):
    assert client.get("/api/health").json()["ok"]
    m = client.get("/api/meta").json()
    assert m["total_properties"] > 100
    assert {c["city"] for c in m["cities"]} >= {"Bengaluru", "Mumbai", "Pune", "Hyderabad"}
    assert m["has_demo_data"] is True
    assert len(m["approvals_catalog"]) == len(catalog.APPROVALS)


def test_city_filter_and_pagination(client):
    r = client.get("/api/properties", params={"city": "Pune", "page_size": 5}).json()
    assert r["total"] > 5 and len(r["results"]) == 5
    assert all(p["city"] == "Pune" for p in r["results"])
    r2 = client.get("/api/properties", params={"city": "Pune", "page_size": 5, "page": 2}).json()
    assert {p["id"] for p in r["results"]}.isdisjoint({p["id"] for p in r2["results"]})


def test_filters(client):
    r = client.get("/api/properties", params={
        "city": "Bengaluru", "bhk": "3", "rera_only": "1", "max_price": 2e7, "status": "Under Construction,Ready to Move",
        "page_size": 200}).json()
    for p in r["results"]:
        assert 3 in p["bhk"]
        assert p["rera_status"] == "Registered"
        assert p["price_min"] <= 2e7
        assert p["status"] in ("Under Construction", "Ready to Move")


def test_no_red_flags_and_approvals_filter(client):
    r = client.get("/api/properties", params={"no_red_flags": "1", "all_approvals": "1", "page_size": 200}).json()
    assert r["total"] > 0
    assert all(p["flags_critical"] == 0 and p["approvals_missing"] == 0 for p in r["results"])


def test_sorting(client):
    r = client.get("/api/properties", params={"city": "Mumbai", "sort": "psf_asc", "page_size": 200}).json()
    psfs = [p["psf"] for p in r["results"] if p["psf"]]
    assert psfs == sorted(psfs)


def test_search_and_typo_tolerance(client):
    any_name = client.get("/api/properties", params={"page_size": 1}).json()["results"][0]["name"]
    first = any_name.split()[0]
    hits = client.get("/api/properties", params={"q": first}).json()["results"]
    assert any(h["name"] == any_name for h in hits)
    typo = first[:-2] + first[-1]  # drop a letter
    assert client.get("/api/suggest", params={"q": typo}).json(), "fuzzy suggest should find a match"


def test_property_detail_has_everything(client):
    pid = client.get("/api/properties", params={"page_size": 1}).json()["results"][0]["id"]
    d = client.get(f"/api/properties/{pid}").json()
    for key in ("property", "builder", "configurations", "price_quotes", "latest_quotes", "prices", "fair_price",
                "delivery", "approvals", "reviews", "reviews_summary", "litigation", "nearby", "trust", "red_flags",
                "verify_links", "state_costs", "similar"):
        assert key in d, key
    assert len(d["approvals"]["items"]) == len(catalog.APPROVALS)
    assert d["verify_links"]["portals"] and d["verify_links"]["rera"]["url"].startswith("https://")
    # every quote says where it came from and when
    assert all(q["source"] and q["quoted_on"] for q in d["price_quotes"])


def test_404s(client):
    assert client.get("/api/properties/999999").status_code == 404
    assert client.get("/some/spa/route").status_code == 200  # SPA fallback


def test_compare_and_localities(client):
    ids = [p["id"] for p in client.get("/api/properties", params={"page_size": 3}).json()["results"]]
    assert len(client.get("/api/compare", params={"ids": ",".join(map(str, ids))}).json()) == 3
    loc = client.get("/api/localities/Bengaluru").json()
    assert loc and all(r["projects"] >= 1 for r in loc)


def test_csv_export(client):
    r = client.get("/api/properties/export.csv", params={"city": "Noida"})
    assert r.status_code == 200 and r.text.startswith("name,builder")


def test_admin_disabled_without_token(client):
    assert client.post("/api/admin/import", json={"properties": []}).status_code == 403


def test_ui_served(client):
    assert "HousingSearch" in client.get("/").text
    assert client.get("/static/js/app.js").status_code == 200


# ------------------------------------------------------------ importers
def test_json_and_csv_import(tmp_path):
    conn = db.connect(tmp_path / "x.db")
    db.init_schema(conn)
    n = ingest.import_json(conn, ROOT / "examples" / "sample_import.json")
    assert n == 1
    res = ingest.import_quotes_csv(conn, ROOT / "examples" / "sample_quotes.csv")
    assert res["added"] == 3 and res["unmatched"] == ["Unknown Project"]
    # re-import is idempotent for quotes
    ingest.import_quotes_csv(conn, ROOT / "examples" / "sample_quotes.csv")
    assert conn.execute("SELECT COUNT(*) FROM price_quotes").fetchone()[0] == 5


def test_price_parsing():
    assert ingest._f("1.25 Cr") == 1.25e7
    assert ingest._f("85 L") == 8.5e6
    assert ingest._f("₹ 9,800") == 9800


def test_jsonld_extraction():
    html = """<html><script type="application/ld+json">{"@context":"https://schema.org","@type":"ApartmentComplex",
      "name":"Test Towers","address":{"addressLocality":"Baner","postalCode":"411045"},
      "geo":{"latitude":18.56,"longitude":73.78},
      "offers":{"@type":"AggregateOffer","lowPrice":"9500000","highPrice":"15000000"}}</script></html>"""
    rec = ingest.jsonld_to_record(ingest.extract_jsonld(html), "https://example.com/p", "Pune")
    assert rec["name"] == "Test Towers" and rec["locality"] == "Baner"
    assert {q["price"] for q in rec["price_quotes"]} == {9.5e6, 1.5e7}


# --------------------------------------------------------------- insights
def test_delivery_overdue():
    d = insights.delivery_summary({"rera_possession_date": "2025-01-01", "status": "Under Construction"},
                                  today=date(2026, 1, 1))
    assert d["overdue_months"] == 12


def test_approvals_not_yet_due_for_under_construction():
    s = insights.approvals_summary({"state": "Karnataka", "status": "Under Construction", "rera_status": "Registered"}, [])
    oc = next(i for i in s["items"] if i["code"] == "OC")
    assert oc["status"] == "Not Yet Due"
    assert "BBMP" in next(i for i in s["items"] if i["code"] == "PLAN")["authority"]


def test_red_flag_for_unregistered():
    flags = insights.red_flags({"rera_status": "Not Registered"}, None, {}, {}, {"missing_count": 0}, {}, [])
    assert flags[0]["level"] == "critical"


def test_fair_price():
    assert insights.fair_price(9000, [10000, 10000, 10000])["verdict"] == "Below locality average"
    assert insights.fair_price(13000, [10000, 10000])["verdict"] == "Premium over locality"


def test_sentiment():
    assert insights.classify_sentiment("possession delayed, poor quality") == "negative"
    assert insights.classify_sentiment("great quality, delivered on time") == "positive"
