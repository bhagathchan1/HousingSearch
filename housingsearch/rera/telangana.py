"""TG RERA (Telangana / Hyderabad) — import from search-result pages YOU saved.

TG RERA protects its project search with a CAPTCHA, so HousingSearch does not query it.
Instead:
  1. Open https://rerait.telangana.gov.in/SearchList/Search in your browser.
  2. Choose "Registered" projects, pick a district (Hyderabad, Ranga Reddy,
     Medchal-Malkajgiri or Sangareddy), type the CAPTCHA and search.
  3. Save the results page (Ctrl/Cmd+S, "Webpage, HTML only" or "Complete").
     If results are paginated, save each page (or show all rows first, if offered).
  4. python -m housingsearch import-rera tg --from-file page1.html page2.html ...

The parser finds the results table by its column headings, so it copes with layout
changes. If it can't recognise a page it says so — share the file to get it supported.
"""

from __future__ import annotations

import re
from pathlib import Path

from .common import latest_date, record_slug, text, title_case

PORTAL = "https://rerait.telangana.gov.in/SearchList/Search"

# District -> city. Everything in the Hyderabad metropolitan region maps to Hyderabad.
HYD_DISTRICTS = re.compile(r"hyderabad|ranga\s*reddy|rangareddy|medchal|malkajgiri|sangareddy", re.I)

# column heading synonyms -> field
COLUMNS = [
    ("name", re.compile(r"project\s*name|name\s*of\s*(?:the\s*)?project|^project$", re.I)),
    ("builder", re.compile(r"promoter|developer|company|firm|builder", re.I)),
    ("reg", re.compile(r"cert(?:ificate)?\.?\s*no|registration\s*(?:no|number)|reg\.?\s*no|rera\s*no|regist", re.I)),
    ("app", re.compile(r"application\s*(?:no|number)|ack", re.I)),
    ("district", re.compile(r"district", re.I)),
    ("mandal", re.compile(r"mandal|taluk|tehsil", re.I)),
    ("village", re.compile(r"village|locality|area|location", re.I)),
    ("address", re.compile(r"address", re.I)),
    ("type", re.compile(r"project\s*type|type\s*of\s*project|category", re.I)),
    ("status", re.compile(r"status", re.I)),
    ("completion", re.compile(r"complet|end\s*date|valid|expiry|proposed", re.I)),
    ("approved", re.compile(r"approv|registered\s*on|registration\s*date|date\s*of\s*reg", re.I)),
]

TG_REG = re.compile(r"\bP0\d{2}\d{5,8}\b")


class UnrecognisedPage(Exception):
    pass


def _map_headers(headers: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for i, h in enumerate(headers):
        for field, rx in COLUMNS:
            if field not in found and rx.search(h):
                # "Project Name" also matches the generic "project" rules; first match wins per column
                if any(idx == i for idx in found.values()):
                    continue
                found[field] = i
                break
    return found


def parse_saved(html: str) -> list[dict]:
    """Rows from every results table in a saved TG RERA page."""
    out = []
    for table in re.findall(r"<table.*?</table>", html, re.S | re.I):
        trs = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I)
        if not trs:
            continue
        head = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", trs[0], re.S | re.I)
        cols = _map_headers([text(h) for h in head])
        if "name" not in cols or not ({"reg", "builder"} & cols.keys()):
            continue
        for tr in trs[1:]:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
            if len(cells) < len(cols):
                continue
            row = {f: text(cells[i]) for f, i in cols.items() if i < len(cells)}
            if not row.get("name"):
                continue
            reg = TG_REG.search(text(tr))
            if reg and not TG_REG.search(row.get("reg", "")):
                row["reg"] = reg.group(0)
            link = re.search(r'href="(https?://[^"]*(?:rera|telangana)[^"]*)"', tr, re.I)
            row["url"] = link.group(1) if link else None
            out.append(row)
    return out


def to_record(r: dict) -> dict | None:
    district = r.get("district") or ""
    if district and not HYD_DISTRICTS.search(district):
        return None  # outside the Hyderabad region
    if re.search(r"commercial", r.get("type", ""), re.I) and not re.search(r"residential|mixed", r.get("type", ""), re.I):
        return None
    reg = (TG_REG.search(r.get("reg", "")) or TG_REG.search(r.get("app", "")) or None)
    reg = reg.group(0) if reg else (r.get("reg") or r.get("app") or "").strip()
    status = (r.get("status") or "").lower()
    rera_status = "Revoked" if "revok" in status else "Lapsed" if "laps" in status or "expir" in status else "Registered"
    done = "complet" in status
    locality = title_case(r.get("village") or r.get("mandal") or district or "Hyderabad")
    ptype = "Plot" if re.search(r"plot|layout|venture", r.get("type", ""), re.I) else \
        "Villa" if re.search(r"\bvillas?\b", (r.get("type", "") + " " + r["name"]), re.I) else "Apartment"
    return {
        "slug": record_slug("tg", reg or r["name"] + "-" + locality),
        "name": title_case(r["name"]),
        "builder": title_case(r.get("builder") or ""),
        "city": "Hyderabad",
        "state": "Telangana",
        "locality": locality,
        "address": r.get("address") or ", ".join(x for x in (r.get("village"), r.get("mandal"), district) if x) or None,
        "property_type": ptype,
        "status": "Ready to Move" if done else "Under Construction",
        "rera_number": reg or None,
        "rera_status": rera_status,
        "rera_authority": "TG RERA",
        "rera_url": r.get("url") or PORTAL,
        "rera_possession_date": latest_date(r.get("completion", "")),
        "launch_date": latest_date(r.get("approved", "")),
        "construction_progress": 100 if done else None,
        "description": (f"Registered with TG RERA{(' (' + district + ' district)') if district else ''}. "
                        + (f"Status on the register: {r.get('status')}. " if r.get("status") else "")
                        + "Source: TG RERA search results saved by the user."),
        "approvals": [{"code": "RERA", "status": "Obtained" if rera_status == "Registered" else "Missing",
                       "reference": reg or None}],
        "is_demo": 0,
    }


def from_files(paths: list[str | Path], log=print) -> list[dict]:
    records = []
    for p in paths:
        html = Path(p).read_text(encoding="utf-8", errors="replace")
        rows = parse_saved(html)
        if not rows:
            raise UnrecognisedPage(
                f"{p}: no TG RERA results table found. Make sure it is a saved search-results page; "
                "if it is, open an issue with the file so the parser can learn its layout.")
        recs = [x for x in (to_record(r) for r in rows) if x]
        log(f"Telangana: {p}: {len(rows)} rows, {len(recs)} in the Hyderabad region")
        records += recs
    return records
