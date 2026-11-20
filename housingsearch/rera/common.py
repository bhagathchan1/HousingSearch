"""Parsing helpers shared by the state importers."""

from __future__ import annotations

import html as _html
import math
import re
from datetime import date, datetime

from ..repository import slugify

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def text(fragment: str) -> str:
    """HTML fragment -> clean single-line text."""
    return WS.sub(" ", _html.unescape(TAG.sub(" ", fragment or ""))).strip()


def rows(table_html: str) -> list[list[str]]:
    """Raw cell HTML for every <tr> that has <td> cells."""
    out = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S | re.I):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        if cells:
            out.append(cells)
    return out


_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})\b"), ("d", "m", "y")),
]


def dates_in(s: str) -> list[str]:
    """All dates found in a string, as ISO strings, in order of appearance."""
    found: list[tuple[int, str]] = []
    for rx, order in _DATE_PATTERNS:
        for m in rx.finditer(s or ""):
            parts = dict(zip(order, map(int, m.groups())))
            try:
                found.append((m.start(), date(parts["y"], parts["m"], parts["d"]).isoformat()))
            except ValueError:
                continue
    return [d for _, d in sorted(found)]


def first_date(s: str) -> str | None:
    d = dates_in(s)
    return d[0] if d else None


def latest_date(*values: str) -> str | None:
    ds = [d for v in values for d in dates_in(v)]
    return max(ds) if ds else None


def dms_to_decimal(s: str) -> float | None:
    """12°59'45.61"N -> 12.99600; also accepts plain decimals."""
    if not s:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*°\s*(\d+(?:\.\d+)?)?\s*['’]?\s*(\d+(?:\.\d+)?)?\s*[\"”]?\s*([NSEW])?", s)
    if m and "°" in s:
        deg, mins, secs, hemi = m.groups()
        v = float(deg) + float(mins or 0) / 60 + float(secs or 0) / 3600
        return round(-v if hemi in ("S", "W") else v, 6)
    m = re.search(r"-?\d+\.\d+", s)
    return float(m.group(0)) if m else None


def title_case(s: str) -> str:
    """'SOBHA LIMITED' -> 'Sobha Limited'; keeps mixed-case input as is."""
    s = re.sub(r"\s+", " ", (s or "").strip(" ,.-"))
    if not (s.isupper() or s.islower()):
        return s
    keep_upper = {"ii", "iii", "iv", "vi", "llp", "bhk", "dlf", "ns"}
    small = {"and", "of", "the", "at", "in", "by"}
    out = []
    for i, w in enumerate(s.lower().split()):
        if w in keep_upper:
            out.append(w.upper())
        elif i and w in small:
            out.append(w)
        else:  # capitalise the first letter and any letter after . - / ( & '
            out.append(re.sub(r"(^|[.\-/(&'])([a-z])", lambda m: m.group(1) + m.group(2).upper(), w))
    return " ".join(out)


def record_slug(state_code: str, rera_number: str) -> str:
    return "rera-" + state_code + "-" + slugify(rera_number)


def today_iso() -> str:
    return datetime.now().date().isoformat()


CITY_CENTERS = {
    "Bengaluru": (12.9716, 77.5946), "Gurugram": (28.4595, 77.0266), "Chennai": (13.0827, 80.2707),
    "Mumbai": (19.0760, 72.8777), "Thane": (19.2183, 72.9781), "Pune": (18.5204, 73.8567),
    "Hyderabad": (17.3850, 78.4867),
}


def plausible_coords(city: str, lat, lng, max_km: float = 50) -> tuple:
    """Return (lat, lng) if they fall within max_km of the city centre, else (None, None).

    Registers contain mistyped coordinates; a wrong pin is worse than no pin.
    """
    c = CITY_CENTERS.get(city)
    if lat is None or lng is None or not c:
        return (lat, lng) if c is None else (None, None)
    la1, lo1, la2, lo2 = map(math.radians, (lat, lng, *c))
    d = 2 * 6371 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2
                                       + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))
    return (lat, lng) if d <= max_km else (None, None)
