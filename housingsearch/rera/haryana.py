"""Haryana RERA (haryanarera.gov.in) importer — Gurugram bench.

One page lists every project registered with HRERA Gurugram: registration certificate
number and date, project ID, name, builder, location (sector), registration validity,
lapsed status, and a link to the project's public page.
"""

from __future__ import annotations

import re

from .common import first_date, record_slug, rows, text, title_case

BASE = "https://haryanarera.gov.in"
LIST_URLS = {"Gurugram": BASE + "/admincontrol/registered_projects/2"}

# The register mixes in shops, malls and offices; the name is the only signal available.
COMMERCIAL = re.compile(r"commercial|\bmall\b|plaza|retail|office|business|cyber|\bsco\b|shop|hotel|hospital|"
                        r"warehouse|logistic|industrial|market|arcade|city cent(?:er|re)|it park|tech park|corporate", re.I)


def _ptype(name: str) -> str:
    n = name.lower()
    if "plot" in n:
        return "Plot"
    if re.search(r"\bvillas?\b", n):
        return "Villa"
    return "Apartment"


def _locality(location: str) -> str:
    loc = text(location).upper()
    m = re.search(r"SECTOR[\s\-]*(\d+[A-Z]?)", loc)
    if m:
        return f"Sector {m.group(1)}"
    loc = re.sub(r"\b(GURUGRAM|GURGAON|HARYANA|DISTRICT|TEHSIL)\b", " ", loc)
    loc = re.sub(r"[,\s]+", " ", loc).strip(" ,.-")
    return title_case(loc) or "Gurugram"


def parse_list(html: str) -> list[dict]:
    out = []
    for c in rows(html):
        if len(c) < 10:
            continue
        project_id = text(c[2])
        if not project_id.startswith("RERA-"):
            continue
        cert = text(c[1])
        link = re.search(r'href="([^"]*searchprojectDetail[^"]*)"', c[2])
        out.append({
            "cert": re.sub(r"\s*DATED.*|Lapsed Project.*", "", cert, flags=re.I).strip(),
            "cert_date": first_date(cert.replace(".", "-")),
            "lapsed": "lapsed" in cert.lower(),
            "project_id": project_id,
            "url": link.group(1) if link else None,
            "name": text(c[3]),
            "builder": text(c[4]),
            "location": text(c[5]),
            "district": text(c[6]),
            "valid_upto": first_date(text(c[9])),
            "qpr_missing": "qpr not uploaded" in " ".join(text(x).lower() for x in c[10:]),
            "has_oc_link": "oc/cc" in " ".join(text(x).lower() for x in c[10:]),
        })
    return out


def to_record(r: dict, city: str = "Gurugram") -> dict | None:
    if COMMERCIAL.search(r["name"]):
        return None
    notes = []
    if r["qpr_missing"]:
        notes.append("Quarterly progress report not uploaded")
    return {
        "slug": record_slug("hr", r["project_id"]),
        "name": title_case(r["name"]),
        "builder": title_case(r["builder"]),
        "city": city,
        "state": "Haryana",
        "locality": _locality(r["location"]),
        "address": title_case(r["location"]),
        "property_type": _ptype(r["name"]),
        # HRERA lists an "OC/CC/PCC" link once an occupation / (part) completion certificate is uploaded
        "status": "Ready to Move" if r["has_oc_link"] else "Under Construction",
        "launch_date": r["cert_date"],
        "rera_number": r["cert"],
        "rera_status": "Lapsed" if r["lapsed"] else "Registered",
        "rera_authority": "HRERA Gurugram",
        "rera_url": r["url"] or LIST_URLS[city],
        "rera_possession_date": r["valid_upto"],
        "description": (f"Registered with HRERA Gurugram as {r['project_id']} (certificate {r['cert']}"
                        f"{', dated ' + r['cert_date'] if r['cert_date'] else ''}). Registration valid up to "
                        f"{r['valid_upto'] or '—'}." + (" " + "; ".join(notes) + "." if notes else "")
                        + " Source: Haryana RERA public register."),
        "approvals": [{"code": "RERA", "status": "Obtained" if not r["lapsed"] else "Missing",
                       "reference": r["cert"], "issued_on": r["cert_date"],
                       "notes": "Registration lapsed per HRERA register" if r["lapsed"] else None}]
        + ([{"code": "OC", "status": "Obtained", "document_url": r["url"],
             "notes": "OC / CC / part-completion certificate uploaded on HRERA (may cover only some towers)"}]
           if r["has_oc_link"] else []),
        "is_demo": 0,
    }


def fetch(fetcher, cities=None, log=print) -> list[dict]:
    records = []
    for city in cities or list(LIST_URLS):
        log(f"Haryana: fetching registered projects for {city}")
        listed = parse_list(fetcher.get(LIST_URLS[city]))
        log(f"  {len(listed)} rows")
        records += [rec for rec in (to_record(r, city) for r in listed) if rec]
    return records
