"""RERA Karnataka (rera.karnataka.gov.in) importer.

List:     POST /projectViewDetails with a district -> table of approved projects with
          promoter, project name, status, taluk, type, approval and completion dates
          and every extension granted.
Complete: GET /viewAllCompletedProjects -> projects that applied for completion.
Details:  POST /projectDetails (action=<row id>) -> address, PIN, coordinates and the
          unit mix (BHK type, count, carpet area). ~430 KB per project, so optional.
"""

from __future__ import annotations

import re
from datetime import date

from .common import dms_to_decimal, latest_date, plausible_coords, record_slug, rows, text, title_case

BASE = "https://rera.karnataka.gov.in"
PORTAL = BASE + "/viewAllProjects"

# district on the portal -> city in HousingSearch
DISTRICTS = {"Bengaluru Urban": "Bengaluru", "Bengaluru  Rural": "Bengaluru"}

RESIDENTIAL_TYPES = {
    "residential/group housing": "Apartment",
    "residential": "Apartment",
    "mixed development": "Apartment",
    "plotted development": "Plot",
    "villas": "Villa",
    "villa": "Villa",
}


def parse_list(html: str) -> list[dict]:
    m = re.search(r'<table[^>]*id="approvedTable".*?</table>', html, re.S) or re.search(r"<table.*</table>", html, re.S)
    if not m:
        return []
    out = []
    for c in rows(m.group(0)):
        if len(c) < 16:
            continue
        rid = re.search(r'id="(\d+)"', c[3])
        out.append({
            "row_id": rid.group(1) if rid else None,
            "ack": text(c[1]),
            "reg": text(c[2]),
            "promoter": text(c[4]),
            "name": text(re.sub(r"<p.*?</p>", "", c[5], flags=re.S)),
            "status": text(c[6]),
            "district": text(c[7]),
            "taluk": text(c[8]),
            "type": text(c[9]),
            # The header row lists "APPLIED ON" but the data rows omit that cell, so the
            # remaining columns are shifted left by one relative to the headers.
            "approved_on": text(c[10]),
            "completion": text(c[11]),
            "completion_at_reg": text(c[12]),
            "extensions": " ".join(text(x) for x in c[13:16]),
        })
    return out


def parse_completed(html: str) -> set[str]:
    return set(re.findall(r"PRM/KA/RERA/[0-9A-Z/]+", html))


def _coord(v: str) -> float | None:
    """Coordinates as builders type them: 13.0344, 13°02'03.9"N, 130203.9N (run-together DMS)."""
    v = (v or "").strip()
    if not v:
        return None
    if any(ch in v for ch in "°'\"’”"):
        return dms_to_decimal(v)
    m = re.match(r"(\d+(?:\.\d+)?)", v)
    if not m:
        return None
    x = float(m.group(1))
    if x < 180:
        return x
    if 100000 <= x < 1000000:  # DDMMSS.ss without separators
        d, rest = divmod(x, 10000)
        mi, se = divmod(rest, 100)
        return round(d + mi / 60 + se / 3600, 6) if mi < 60 and se < 60 else None
    return None


def parse_details(html: str) -> dict:
    b = text(re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S))
    out: dict = {}
    la = lo = None
    lat_m = re.search(r"Latitude\s*:\s*([^:]{0,40}?)\s*(?:North\s+)?Longitude\s*:\s*([^:]{0,40}?)(?:\s+(?:East|North|South|West|Plan|Sch)|$)", b)
    if lat_m:
        la, lo = _coord(lat_m.group(1)), _coord(lat_m.group(2))
        pair = re.match(r"\s*(\d{1,2}\.\d+)\s*,\s*(\d{2}\.\d+)", lat_m.group(1))
        if pair:  # "13.29, 77.55" typed into the latitude box
            la, lo = float(pair.group(1)), float(pair.group(2))
    la, lo = plausible_coords("Bengaluru", la, lo, 70)
    if la:
        out["lat"], out["lng"] = la, lo
    addr = re.search(r"Project Address\s*:\s*(.*?)\s+District\s*:", b)
    if addr:
        out["address"] = addr.group(1).strip(" ,.")
    i = b.find("Project Address")
    pin = re.search(r"Pin Code\s*:\s*(\d{6})", b[i:i + 500]) if i >= 0 else None
    if pin:
        out["pincode"] = pin.group(1)
    configs, seen = [], set()
    for t, n, area in re.findall(
            r"Type of Inventory\s*:\s*(.*?)\s+No of Inventory\s*:\s*(\d+)\s+Carpet Area \(Sq Mtr\)\s*:\s*([\d.]+)", b):
        if (t, n, area) in seen:  # "as per registered plan" and "as per modified plan" repeat rows
            continue
        seen.add((t, n, area))
        n = int(n)
        area = float(area)
        # The portal reports total carpet area for the inventory line; convert to per unit.
        per_unit = area / n if n and area / n > 15 else area
        if not (15 <= per_unit <= 1000):
            per_unit = None
        bhk = re.search(r"(\d+(?:\.\d)?)\s*BHK", t, re.I)
        configs.append({
            "label": t.strip(),
            "bhk": float(bhk.group(1)) if bhk else None,
            "carpet_sqft": round(per_unit * 10.7639) if per_unit else None,
            "units_total": n,
        })
    if configs:
        out["configurations"] = configs
        out["total_units"] = sum(c["units_total"] for c in configs)
    return out


def to_record(r: dict, completed: set[str], today: date | None = None) -> dict | None:
    ptype = RESIDENTIAL_TYPES.get(r["type"].lower())
    if not ptype:
        return None  # commercial-only projects are out of scope
    st = r["status"].upper()
    if st.startswith(("REJECTED", "WITHDRAWN")):
        return None  # never registered
    rera_status = "Revoked" if st.startswith("REVOKED") else "Registered"
    today = today or date.today()
    possession = latest_date(r["completion"], r["completion_at_reg"], r["extensions"])
    done = r["reg"] in completed
    status = "Ready to Move" if done else "Under Construction"
    return {
        "slug": record_slug("ka", r["reg"]),
        "name": title_case(r["name"]),
        "builder": title_case(r["promoter"]),
        "city": "Bengaluru" if r["district"].lower().startswith("bengaluru") else r["district"],
        "state": "Karnataka",
        "locality": r["taluk"] or r["district"],
        "property_type": ptype,
        "status": status,
        "launch_date": latest_date(r["approved_on"]) if r["approved_on"] else None,
        "rera_number": r["reg"],
        "rera_status": rera_status,
        "rera_authority": "RERA Karnataka (K-RERA)",
        "rera_url": PORTAL,
        "rera_possession_date": possession,
        "construction_progress": 100 if done else None,
        "description": (f"{title_case(r['type'])} project registered with RERA Karnataka "
                        f"(acknowledgement {r['ack']}). Approved on {r['approved_on'] or '—'}; "
                        f"proposed completion {r['completion'] or '—'}"
                        + (f"; extensions: {r['extensions']}" if r["extensions"].strip(" -") else "")
                        + ". Source: RERA Karnataka public register."),
        "approvals": [{"code": "RERA", "status": "Obtained" if rera_status == "Registered" else "Missing",
                       "reference": r["reg"], "issued_on": latest_date(r["approved_on"]),
                       "notes": None if rera_status == "Registered" else r["status"][:200]}],
        "is_demo": 0,
    }


def fetch(fetcher, districts=None, details: bool = False, details_limit: int | None = None,
          log=print) -> list[dict]:
    """List every residential project; optionally add details for the newest ongoing ones.

    Detail pages are large (~430 KB), so they are fetched newest-first (by RERA completion
    date) for projects not yet completed, up to `details_limit` per district.
    """
    districts = districts or list(DISTRICTS)
    log("Karnataka: fetching list of completed projects")
    completed = parse_completed(fetcher.get(BASE + "/viewAllCompletedProjects"))
    records = []
    for d in districts:
        log(f"Karnataka: fetching approved projects in {d.strip()}")
        html = fetcher.post(BASE + "/projectViewDetails", {
            "project": "", "firm": "", "appNo": "", "regNo": "", "district": d, "subdistrict": "0", "btn1": "Search"})
        pairs = [(r, rec) for r in parse_list(html) if (rec := to_record(r, completed))]
        log(f"  {len(pairs)} residential projects")
        if details:
            todo = sorted((p for p in pairs if p[1]["status"] != "Ready to Move" and p[0].get("row_id")),
                          key=lambda p: p[1]["rera_possession_date"] or "", reverse=True)[:details_limit]
            log(f"  fetching details for {len(todo)} ongoing projects (newest first)")
            for i, (r, rec) in enumerate(todo, 1):
                try:
                    rec.update(parse_details(fetcher.post(BASE + "/projectDetails", {"action": r["row_id"]})))
                except Exception as e:  # keep the list record even if details fail
                    log(f"  details failed for {r['reg']}: {e}")
                if i % 50 == 0:
                    log(f"  details: {i}/{len(todo)}")
        records += [rec for _, rec in pairs]
    return records
