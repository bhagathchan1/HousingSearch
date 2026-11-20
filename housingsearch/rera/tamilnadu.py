"""TNRERA (rera.tn.gov.in) importer — registered building projects, one table per year.

Each row has: registration number and date, promoter, project description with survey
numbers and address, approval details (planning / building permission references),
completion date, site coordinates and current status.
"""

from __future__ import annotations

import re

from .common import first_date, plausible_coords, record_slug, rows, text, title_case

BASE = "https://rera.tn.gov.in"
LIST_URL = BASE + "/registered-building/tn"

# district in the address -> city in HousingSearch (Chennai metropolitan area)
METRO = {
    "Chennai": re.compile(r"\b(chennai|kancheepuram|kanchipuram|chengalpattu|chengalpet|tiruvallur|thiruvallur)\b", re.I),
}


def parse_list(html: str) -> list[dict]:
    out = []
    for c in rows(html):
        if len(c) < 8:
            continue
        reg_txt = text(c[1])
        m = re.search(r"(TN/?RERA/[0-9A-Z/]+|TN/\d+/[A-Za-z]+/\d+/\d+)", reg_txt)
        if not m:
            continue
        project = text(c[3])
        other = text(c[6])
        lat = re.search(r"Latitude\s*[-:]?\s*(\d+\.\d+)", other, re.I)
        lng = re.search(r"Longitude\s*[-:]?\s*(\d+\.\d+)", other, re.I)
        out.append({
            "reg": m.group(1).rstrip("/"),
            "reg_date": first_date(reg_txt),
            "promoter_raw": text(c[2]),
            "project": project,
            "approvals": text(c[4]),
            "completion": first_date(text(c[5]).replace(".", "-")),
            "lat": float(lat.group(1)) if lat else None,
            "lng": float(lng.group(1)) if lng else None,
            "status": text(c[-1]),
        })
    return out


def _name(project: str) -> str:
    m = re.search(r"Project Name\s*:\s*(.*?)(?:\s+(?:Registration|Proposed|Construction|Residential|Regularisation)\b|$)",
                  project, re.I)
    name = (m.group(1) if m else project[:60]).strip(" ,.-")
    return title_case(name[:120]) or "Unnamed project"


def _promoter(raw: str) -> str:
    name = re.split(r",|\s+rep(?:resented)?\s+by\b|\s+Door\s+No", raw, maxsplit=1, flags=re.I)[0]
    return title_case(re.sub(r"^M/s\.?\s*", "", name, flags=re.I))


def _locality(project: str) -> str:
    for rx in (r"of\s+([A-Za-z .'\-]+?)\s+Vill?age", r"([A-Za-z .'\-]+?)\s+Vill?age", r"([A-Za-z .'\-]+?)\s+Taluk"):
        m = re.search(rx, project, re.I)
        if m:
            loc = re.sub(r"^(?:the\s+)?(?:limits\s+of\s+)?", "", m.group(1).strip(" ,.-"), flags=re.I)
            loc = loc.split(",")[-1].strip()
            if 2 < len(loc) < 40:
                return title_case(loc)
    return "Other"


def _ptype(project: str) -> str:
    p = project.lower()
    if re.search(r"\bvillas?\b", p):
        return "Villa"
    if "row house" in p:
        return "Row House"
    if "plot" in p and "dwelling" not in p:
        return "Plot"
    return "Apartment"


def _units(project: str) -> int | None:
    m = re.search(r"(\d{1,5})\s+(?:Nos\.?\s+(?:of\s+)?)?(?:Dwelling\s+Units|D\.?U\.?s?|flats|units)\b", project, re.I)
    return int(m.group(1)) if m else None


def to_record(r: dict) -> dict | None:
    city = next((c for c, rx in METRO.items() if rx.search(r["project"]) or rx.search(r["promoter_raw"][-120:])), None)
    if not city or re.search(r"\bcommercial\b", r["project"], re.I) and not re.search(r"residential|dwelling", r["project"], re.I):
        return None
    status = r["status"].lower()
    done = "completed" in status
    progress = re.search(r"(\d{1,3})\s*%", r["status"])
    approvals = [{"code": "RERA", "status": "Obtained", "reference": r["reg"], "issued_on": r["reg_date"]}]
    if re.search(r"planning permission|building permission|\bPP\b|permit", r["approvals"], re.I):
        approvals.append({"code": "PLAN", "status": "Obtained", "notes": r["approvals"][:400]})
    return {
        "slug": record_slug("tn", r["reg"]),
        "name": _name(r["project"]),
        "builder": _promoter(r["promoter_raw"]),
        "city": city,
        "state": "Tamil Nadu",
        "locality": _locality(r["project"]),
        "address": r["project"][:300],
        **dict(zip(("lat", "lng"), plausible_coords(city, r["lat"], r["lng"], 70))),
        "property_type": _ptype(r["project"]),
        "status": "Ready to Move" if done else "Under Construction",
        "construction_progress": 100 if done else (int(progress.group(1)) if progress else None),
        "launch_date": r["reg_date"],
        "rera_number": r["reg"],
        "rera_status": "Registered",
        "rera_authority": "TNRERA",
        "rera_url": LIST_URL,
        "rera_possession_date": r["completion"],
        "total_units": _units(r["project"]),
        "description": r["project"][:600] + " Source: TNRERA public register.",
        "approvals": approvals,
        "is_demo": 0,
    }


def fetch(fetcher, years=None, log=print) -> list[dict]:
    first = fetcher.get(LIST_URL)  # newest year; on a fresh run this also sets the session cookie
    token = re.search(r'name="_token"\s+value="([^"]+)"', first)
    available = re.findall(r'<option[^>]*value="(\d{4})"', first) or []
    years = [str(y) for y in (years or available)]
    records = []
    for y in years:
        log(f"Tamil Nadu: fetching registered building projects for {y}")
        if y == (available[0] if available else None):
            html = first
        else:
            if len(fetcher.jar) == 0:  # first page came from cache: start a live session for the token
                try:
                    live = fetcher.get(LIST_URL, use_cache=False)
                    token = re.search(r'name="_token"\s+value="([^"]+)"', live) or token
                except Exception as e:  # portal down: cached year pages (if any) still work
                    log(f"  could not start a session ({e}); using cached pages only")
            html = fetcher.post(LIST_URL, {"_token": token.group(1) if token else "", "year": y})
        listed = parse_list(html)
        recs = [x for x in (to_record(r) for r in listed) if x]
        log(f"  {len(listed)} rows, {len(recs)} in the Chennai metro area")
        records += recs
    return records
