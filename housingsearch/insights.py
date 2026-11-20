"""Buyer-facing analytics computed from raw project data.

Everything here is pure functions over dicts so it is easy to test and reuse.
"""

from __future__ import annotations

import re
import statistics
from datetime import date, datetime

from . import catalog

POSITIVE_WORDS = {
    "good", "great", "excellent", "spacious", "quality", "on time", "ontime", "happy",
    "recommend", "transparent", "responsive", "well maintained", "green", "peaceful",
    "connectivity", "value", "premium", "smooth", "helpful", "delivered",
}
NEGATIVE_WORDS = {
    "delay", "delayed", "poor", "bad", "leak", "leakage", "seepage", "crack", "cheat",
    "fraud", "pathetic", "worst", "unresponsive", "hidden", "escalation", "complaint",
    "water problem", "tanker", "traffic", "unfinished", "refund", "litigation", "stuck",
    "overpriced", "noisy", "flood", "waterlogging",
}

# keyword -> theme, used to summarise what reviewers talk about
THEMES = {
    "Construction quality": ["quality", "crack", "leak", "seepage", "finish", "material", "plaster"],
    "Delivery timeline": ["delay", "on time", "possession", "handover", "timeline", "delivered"],
    "Builder behaviour": ["sales", "cheat", "transparent", "responsive", "hidden", "refund", "crm"],
    "Location & connectivity": ["metro", "traffic", "connectivity", "road", "commute", "airport"],
    "Water & utilities": ["water", "tanker", "power", "electricity", "stp", "borewell"],
    "Amenities & maintenance": ["clubhouse", "pool", "gym", "maintenance", "amenities", "park"],
    "Price & value": ["price", "value", "overpriced", "appreciation", "expensive", "cheap", "rent"],
}


def parse_date(s: str | None) -> date | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s[:10] if fmt == "%Y-%m-%d" else s, fmt).date()
        except ValueError:
            continue
    return None


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def classify_sentiment(text: str, rating: float | None = None) -> str:
    if rating is not None:
        if rating >= 4:
            return "positive"
        if rating <= 2:
            return "negative"
    t = (text or "").lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "neutral"


# --------------------------------------------------------------------------- prices
def latest_quotes_by_source(quotes: list[dict]) -> list[dict]:
    """Most recent quote per (source, configuration), newest first."""
    latest: dict[tuple, dict] = {}
    for q in quotes:
        key = (q["source"], q.get("config_label") or "")
        if key not in latest or q["quoted_on"] > latest[key]["quoted_on"]:
            latest[key] = q
    return sorted(latest.values(), key=lambda q: (q["quoted_on"], q["source"]), reverse=True)


def price_summary(quotes: list[dict]) -> dict:
    if not quotes:
        return {"has_data": False}
    latest = latest_quotes_by_source(quotes)
    psf = [q["price_per_sqft"] for q in latest if q.get("price_per_sqft")]
    newest = max(q["quoted_on"] for q in quotes)

    # monthly median price-per-sqft series (all sources) for the trend chart
    by_month: dict[str, list[float]] = {}
    for q in quotes:
        if q.get("price_per_sqft"):
            by_month.setdefault(q["quoted_on"][:7], []).append(q["price_per_sqft"])
    series = [{"month": m, "psf": round(statistics.median(v))} for m, v in sorted(by_month.items())]

    change_12m = None
    if len(series) >= 2:
        last = series[-1]
        last_d = parse_date(last["month"])
        older = [s for s in series if months_between(parse_date(s["month"]), last_d) >= 11]
        base = older[-1] if older else series[0]
        if base["psf"]:
            change_12m = round((last["psf"] - base["psf"]) / base["psf"] * 100, 1)

    spread = None
    if len(psf) >= 2 and min(psf):
        spread = round((max(psf) - min(psf)) / min(psf) * 100, 1)

    sources = sorted({q["source"] for q in latest})
    return {
        "has_data": True,
        "latest_quote_date": newest,
        "psf_min": round(min(psf)) if psf else None,
        "psf_max": round(max(psf)) if psf else None,
        "psf_median": round(statistics.median(psf)) if psf else None,
        "source_spread_pct": spread,
        "change_12m_pct": change_12m,
        "sources": sources,
        "source_count": len(sources),
        "series": series,
        "cheapest_source": min(latest, key=lambda q: q.get("price_per_sqft") or 1e12)["source"] if psf else None,
    }


def fair_price(psf_median: float | None, locality_psf: list[float]) -> dict:
    if not psf_median or len(locality_psf) < 2:
        return {"verdict": "Insufficient data", "delta_pct": None, "locality_median_psf": None}
    loc = statistics.median(locality_psf)
    delta = round((psf_median - loc) / loc * 100, 1)
    if delta <= -8:
        verdict = "Below locality average"
    elif delta >= 12:
        verdict = "Premium over locality"
    else:
        verdict = "In line with locality"
    return {"verdict": verdict, "delta_pct": delta, "locality_median_psf": round(loc)}


# ------------------------------------------------------------------------- delivery
def delivery_summary(prop: dict, today: date | None = None) -> dict:
    today = today or date.today()
    rera = parse_date(prop.get("rera_possession_date"))
    builder = parse_date(prop.get("builder_possession_date"))
    out = {
        "rera_date": prop.get("rera_possession_date"),
        "builder_date": prop.get("builder_possession_date"),
        "progress_pct": prop.get("construction_progress"),
        "gap_months": None,
        "overdue_months": None,
        "months_to_rera_date": None,
        "status": prop.get("status"),
    }
    if rera and builder:
        out["gap_months"] = months_between(builder, rera)  # positive: builder promises earlier than RERA
    if rera:
        m = months_between(today, rera)
        out["months_to_rera_date"] = m
        if m < 0 and prop.get("status") != "Ready to Move":
            out["overdue_months"] = -m
    # simple feasibility check: remaining work vs remaining time
    prog = prop.get("construction_progress")
    if rera and prog is not None and prop.get("status") == "Under Construction":
        remaining_months = max(months_between(today, rera), 0)
        out["on_track"] = not (prog < 60 and remaining_months < 12) and not (prog < 85 and remaining_months < 4)
    return out


# ------------------------------------------------------------------------ approvals
def approvals_summary(prop: dict, approvals: list[dict]) -> dict:
    state = prop.get("state", "")
    status = prop.get("status")
    have = {a["code"]: a for a in approvals}
    items = []
    for spec in catalog.APPROVALS:
        rec = have.get(spec["code"], {})
        st = rec.get("status")
        if not st:
            if spec["stage"] == "completion" and status != "Ready to Move":
                st = "Not Yet Due"
            elif spec["code"] == "RERA" and prop.get("rera_status") == "Registered":
                st = "Obtained"
            else:
                st = "Unknown"
        items.append(
            {
                "code": spec["code"],
                "name": spec["name"],
                "stage": spec["stage"],
                "mandatory": spec["mandatory"],
                "applies_when": spec.get("applies_when"),
                "why": spec["why"],
                "authority": catalog.authority_for(spec["code"], state),
                "status": st,
                "reference": rec.get("reference"),
                "issued_on": rec.get("issued_on"),
                "document_url": rec.get("document_url"),
                "notes": rec.get("notes"),
            }
        )
    due = [i for i in items if i["status"] not in ("Not Yet Due", "Not Applicable")]
    obtained = [i for i in due if i["status"] == "Obtained"]
    missing = [i for i in due if i["status"] == "Missing" or (i["status"] == "Unknown" and i["mandatory"])]
    pending = [i for i in due if i["status"] == "Pending"]
    return {
        "items": items,
        "due_count": len(due),
        "obtained_count": len(obtained),
        "pending_count": len(pending),
        "missing_count": len(missing),
        "missing": [i["name"] for i in missing],
        "completeness_pct": round(len(obtained) / len(due) * 100) if due else None,
    }


# -------------------------------------------------------------------------- reviews
def reviews_summary(reviews: list[dict]) -> dict:
    if not reviews:
        return {"count": 0}
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    ratings = []
    by_source: dict[str, dict] = {}
    theme_hits: dict[str, dict] = {t: {"positive": 0, "negative": 0, "neutral": 0} for t in THEMES}
    for r in reviews:
        s = r.get("sentiment") or classify_sentiment(f"{r.get('title','')} {r.get('body','')}", r.get("rating"))
        counts[s] += 1
        if r.get("rating"):
            ratings.append(r["rating"])
        src = by_source.setdefault(r["source"], {"source": r["source"], "count": 0, "ratings": []})
        src["count"] += 1
        if r.get("rating"):
            src["ratings"].append(r["rating"])
        text = f"{r.get('title','')} {r.get('body','')}".lower()
        for theme, words in THEMES.items():
            if any(re.search(r"\b" + re.escape(w), text) for w in words):
                theme_hits[theme][s] += 1
    sources = [
        {"source": v["source"], "count": v["count"],
         "avg_rating": round(sum(v["ratings"]) / len(v["ratings"]), 1) if v["ratings"] else None}
        for v in by_source.values()
    ]
    themes = []
    for theme, c in theme_hits.items():
        total = sum(c.values())
        if total:
            themes.append({"theme": theme, "mentions": total, **c,
                           "tone": "positive" if c["positive"] > c["negative"] else
                                   "negative" if c["negative"] > c["positive"] else "mixed"})
    themes.sort(key=lambda t: t["mentions"], reverse=True)
    return {
        "count": len(reviews),
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "sentiment": counts,
        "positive_pct": round(counts["positive"] / len(reviews) * 100),
        "negative_pct": round(counts["negative"] / len(reviews) * 100),
        "sources": sorted(sources, key=lambda s: s["count"], reverse=True),
        "themes": themes,
    }


# ------------------------------------------------------------------ flags and score
def red_flags(prop, builder, prices, delivery, approvals, reviews, litigation) -> list[dict]:
    flags: list[dict] = []

    def add(level, title, detail):
        flags.append({"level": level, "title": title, "detail": detail})

    rs = prop.get("rera_status")
    if rs in (None, "", "Not Registered"):
        add("critical", "Not RERA registered", "Selling an unregistered project is illegal in most cases. Do not pay any booking amount.")
    elif rs in ("Lapsed", "Revoked"):
        add("critical", f"RERA registration {rs.lower()}", "Check the RERA portal for extension orders before proceeding.")
    elif rs == "Applied":
        add("warning", "RERA registration only applied for", "Builder cannot legally accept bookings until registration is granted.")

    if approvals.get("missing_count"):
        add("critical" if approvals["missing_count"] >= 2 else "warning",
            f"{approvals['missing_count']} required approval(s) missing or unverified",
            ", ".join(approvals["missing"]))

    if delivery.get("overdue_months"):
        add("critical", f"Possession overdue by {delivery['overdue_months']} months",
            "Past the RERA-declared date. You may be entitled to interest for delay under RERA Sec 18.")
    elif delivery.get("on_track") is False:
        add("warning", "Construction pace looks behind schedule",
            f"{delivery.get('progress_pct')}% complete with {delivery.get('months_to_rera_date')} months to the RERA date.")
    if delivery.get("gap_months") and delivery["gap_months"] >= 9:
        add("info", f"Builder's advertised date is {delivery['gap_months']} months earlier than RERA date",
            "Plan your finances around the RERA date — it is the legally binding one.")

    if prices.get("source_spread_pct") and prices["source_spread_pct"] >= 12:
        add("info", f"Quotes differ by {prices['source_spread_pct']}% across sources",
            f"Negotiate — the lowest quote seen was on {prices.get('cheapest_source')}.")

    if builder:
        otd = builder.get("on_time_delivery_pct")
        if otd is not None and otd < 60:
            add("warning", f"Builder delivered only {round(otd)}% of projects on time",
                f"Average delay {builder.get('avg_delay_months') or '?'} months across past projects.")
        if (builder.get("rera_complaints") or 0) >= 25:
            add("warning", f"{builder['rera_complaints']} RERA complaints against builder", "Read the orders on the RERA portal.")

    open_cases = [l for l in litigation if l.get("status") == "Open"]
    if open_cases:
        add("warning" if len(open_cases) < 3 else "critical",
            f"{len(open_cases)} open case(s) involving the project",
            "; ".join(f"{l['forum']}: {l.get('summary','')}" for l in open_cases[:3]))

    if reviews.get("count", 0) >= 4 and reviews.get("negative_pct", 0) >= 45:
        add("warning", f"{reviews['negative_pct']}% of reviews are negative",
            "Top concerns: " + ", ".join(t["theme"] for t in reviews.get("themes", []) if t["tone"] == "negative")[:200])

    if not prop.get("bank_approvals"):
        add("info", "No bank loan approvals recorded", "Major banks pre-approving a project is a useful independent check.")

    if prop.get("status") == "Ready to Move" and any(
        i["code"] == "OC" and i["status"] != "Obtained" for i in approvals.get("items", [])
    ):
        add("critical", "Ready-to-move but Occupancy Certificate not confirmed",
            "Do not take possession or register without OC.")

    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(flags, key=lambda f: order[f["level"]])


def trust_score(prop, builder, delivery, approvals, reviews, litigation) -> dict:
    """0-100 heuristic. Transparent: returns the components."""
    comp = {}
    comp["rera"] = {"Registered": 25, "Applied": 8}.get(prop.get("rera_status"), 0)
    comp["approvals"] = round(25 * (approvals.get("completeness_pct") or 0) / 100)
    if builder and builder.get("on_time_delivery_pct") is not None:
        comp["builder"] = round(20 * builder["on_time_delivery_pct"] / 100)
    else:
        comp["builder"] = 8
    d = 15
    if delivery.get("overdue_months"):
        d = max(0, 15 - delivery["overdue_months"])
    elif delivery.get("on_track") is False:
        d = 7
    comp["delivery"] = d
    if reviews.get("count"):
        comp["reviews"] = round(10 * (reviews["positive_pct"] + 0.5 * (100 - reviews["positive_pct"] - reviews["negative_pct"])) / 100)
    else:
        comp["reviews"] = 5
    open_cases = sum(1 for l in litigation if l.get("status") == "Open")
    comp["legal"] = max(0, 5 - 2 * open_cases)
    score = sum(comp.values())
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"
    return {"score": score, "grade": grade, "components": comp,
            "max": {"rera": 25, "approvals": 25, "builder": 20, "delivery": 15, "reviews": 10, "legal": 5}}


def verify_links(prop: dict) -> dict:
    """Links that let the user cross-check live data at the original sources."""
    from urllib.parse import quote_plus

    q = f'"{prop["name"]}" {prop["locality"]} {prop["city"]}'
    state = catalog.STATES.get(prop.get("state", ""), {})
    return {
        "portals": [
            {"name": p["name"], "url": f"https://www.google.com/search?q={quote_plus(q + ' site:' + p['domain'])}"}
            for p in catalog.PORTALS
        ],
        "forums": [
            {"name": f["name"], "url": f"https://www.google.com/search?q={quote_plus(q + ' review site:' + f['domain'])}"}
            for f in catalog.FORUMS
        ],
        "rera": {"name": state.get("rera_name", "State RERA"), "url": prop.get("rera_url") or state.get("rera_url")},
        "map": f"https://www.openstreetmap.org/?mlat={prop.get('lat')}&mlon={prop.get('lng')}#map=15/{prop.get('lat')}/{prop.get('lng')}"
        if prop.get("lat") else None,
    }
