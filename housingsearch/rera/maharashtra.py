"""MahaRERA (maharera.maharashtra.gov.in) importer.

The public "Search Project" list is paginated (10 projects per page, oldest first) and
can be filtered by district code. Each card has: registration number, project name,
promoter, taluka, PIN code, district, coordinates and a link to the full application.
Maharashtra has 50,000+ projects, so by default only the newest `max_pages` pages per
district are imported — the projects a buyer is most likely to be looking at.
"""

from __future__ import annotations

import re

from .common import plausible_coords, record_slug, text, title_case

BASE = "https://www.maharera.maharashtra.gov.in"
SEARCH = BASE + "/projects-search-result"

# MahaRERA district code (also the prefix of the registration number) -> city
DISTRICTS = {
    "518": ("Mumbai Suburban", "Mumbai"),
    "519": ("Mumbai City", "Mumbai"),
    "517": ("Thane", "Thane"),
    "521": ("Pune", "Pune"),
}


def parse_page(html: str) -> list[dict]:
    out = []
    for card in re.split(r'<div class="row shadow p-3 mb-5 bg-body rounded">', html)[1:]:
        reg = re.search(r"#\s*(P\d{11})", card)
        if not reg:
            continue
        name = re.search(r'<h4 class="title4">\s*<strong>(.*?)</strong>', card, re.S)
        promoter = re.search(r'<p class="darkBlue bold[^"]*">(.*?)</p>', card, re.S)
        geo = re.search(r"query=(-?[\d.]+),(-?[\d.]+)\"[^>]*>\s*<em[^>]*></em>\s*([^<]*)<", card)

        def field(label):
            m = re.search(rf'<div class="greyColor">{label}</div>\s*<p>(.*?)</p>', card, re.S)
            return text(m.group(1)) if m else None

        view = re.search(r'href="(https://maharerait\.maharashtra\.gov\.in/public/project/view/\d+)"', card)
        out.append({
            "reg": reg.group(1),
            "name": text(name.group(1)) if name else None,
            "promoter": text(promoter.group(1)) if promoter else None,
            "lat": float(geo.group(1)) if geo else None,
            "lng": float(geo.group(2)) if geo else None,
            "taluka": text(geo.group(3)) if geo else None,
            "pincode": field("Pincode"),
            "district": field("District"),
            "last_modified": field("Last Modified"),
            "extension": "extension" in card.lower() and "N/A</a>" not in card.split("Extension Certificate")[-1][:120],
            "url": view.group(1) if view else None,
        })
    return out


def to_record(r: dict, city: str) -> dict | None:
    if not r["name"]:
        return None
    lat, lng = plausible_coords(city, r["lat"], r["lng"])
    return {
        "slug": record_slug("mh", r["reg"]),
        "name": title_case(r["name"]),
        "builder": title_case(r["promoter"] or ""),
        "city": city,
        "state": "Maharashtra",
        "locality": title_case(r["taluka"] or r["district"] or city),
        "pincode": r["pincode"],
        "lat": lat,
        "lng": lng,
        "property_type": "Apartment",
        "status": "Under Construction",
        "rera_number": r["reg"],
        "rera_status": "Registered",
        "rera_authority": "MahaRERA",
        "rera_url": r["url"] or SEARCH,
        "description": (f"Registered with MahaRERA ({r['district'] or city} district). Last updated on the portal "
                        f"{r['last_modified'] or '—'}." + (" An extension of the completion date has been granted."
                                                           if r["extension"] else "")
                        + " Construction status and completion date are on the project's MahaRERA page."
                        + " Source: MahaRERA public register."),
        "approvals": [{"code": "RERA", "status": "Obtained", "reference": r["reg"]}],
        "is_demo": 0,
    }


def _page(fetcher, code: str, page: int) -> list[dict]:
    params = {"project_name": "", "project_location": "", "project_completion_date": "", "project_state": "27",
              "project_district": code, "carpetAreas": "", "completionPercentages": "", "project_division": "",
              "page": page, "op": ""}
    return parse_page(fetcher.get(SEARCH, params))


def last_page(fetcher, code: str) -> int:
    """Binary search for the last non-empty page."""
    lo, hi = 1, 2
    while _page(fetcher, code, hi):
        lo, hi = hi, hi * 2
        if hi > 20000:
            break
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _page(fetcher, code, mid):
            lo = mid
        else:
            hi = mid
    return lo


def fetch(fetcher, districts=None, max_pages: int = 60, log=print) -> list[dict]:
    records = []
    for code in districts or list(DISTRICTS):
        dname, city = DISTRICTS[code]
        log(f"Maharashtra: finding the newest projects in {dname}")
        last = last_page(fetcher, code)
        first = max(1, last - max_pages + 1)
        log(f"  {last} pages in total (~{last * 10:,} projects); importing pages {first}-{last}")
        for p in range(last, first - 1, -1):
            for r in _page(fetcher, code, p):
                rec = to_record(r, city)
                if rec:
                    records.append(rec)
        log(f"  {len(records)} Maharashtra projects so far")
    return records
