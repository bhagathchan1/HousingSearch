"""Generate the DEMO dataset shipped with HousingSearch.

IMPORTANT: every builder, project, RERA number, price quote, review and case in the
output is SYNTHETIC. Localities, airports and state rules are real so that the
analytics behave realistically, but no record describes a real project. Each record
is flagged `is_demo: true`, RERA numbers carry a `DEMO-` prefix, and the UI shows a
banner. Replace with real data via the importers (see docs/DATA_SOURCES.md).

    python scripts/generate_demo_data.py            # writes data/seed/demo_properties.json
    python scripts/generate_demo_data.py --seed 7   # different but reproducible dataset
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 11, 20)
OUT = Path(__file__).resolve().parent.parent / "data" / "seed" / "demo_properties.json"

# city -> (state, airport(name, lat, lng), [(locality, lat, lng, base_psf, pincode)])
CITIES = {
    "Bengaluru": ("Karnataka", ("Kempegowda International Airport", 13.1986, 77.7066), [
        ("Whitefield", 12.9698, 77.7500, 8600, "560066"), ("Sarjapur Road", 12.9100, 77.6800, 8300, "560035"),
        ("Hebbal", 13.0358, 77.5970, 12500, "560024"), ("Electronic City", 12.8452, 77.6602, 6300, "560100"),
        ("Devanahalli", 13.2437, 77.7136, 6100, "562110"), ("Yelahanka", 13.1005, 77.5963, 7900, "560064"),
        ("Bannerghatta Road", 12.8930, 77.5970, 8900, "560076"), ("Kanakapura Road", 12.8700, 77.5500, 7700, "560062"),
        ("HSR Layout", 12.9116, 77.6389, 13800, "560102"), ("Hennur", 13.0350, 77.6400, 8100, "560043"),
        ("Thanisandra", 13.0570, 77.6330, 8400, "560077"), ("Varthur", 12.9400, 77.7470, 7600, "560087"),
    ]),
    "Mumbai": ("Maharashtra", ("Chhatrapati Shivaji Maharaj International Airport", 19.0896, 72.8656), [
        ("Andheri West", 19.1364, 72.8296, 30500, "400053"), ("Powai", 19.1176, 72.9060, 27500, "400076"),
        ("Thane West", 19.2183, 72.9781, 15800, "400601"), ("Borivali East", 19.2307, 72.8567, 24000, "400066"),
        ("Goregaon East", 19.1663, 72.8526, 24500, "400063"), ("Chembur", 19.0522, 72.9005, 26500, "400071"),
        ("Kharghar", 19.0473, 73.0699, 12800, "410210"), ("Mulund West", 19.1726, 72.9425, 21000, "400080"),
    ]),
    "Pune": ("Maharashtra", ("Pune International Airport", 18.5821, 73.9197), [
        ("Hinjewadi", 18.5913, 73.7389, 7700, "411057"), ("Baner", 18.5590, 73.7868, 11200, "411045"),
        ("Wakad", 18.5993, 73.7625, 8600, "411057"), ("Kharadi", 18.5515, 73.9348, 10200, "411014"),
        ("Hadapsar", 18.5089, 73.9260, 8000, "411028"), ("Wagholi", 18.5808, 73.9787, 5900, "412207"),
    ]),
    "Hyderabad": ("Telangana", ("Rajiv Gandhi International Airport", 17.2403, 78.4294), [
        ("Gachibowli", 17.4401, 78.3489, 10600, "500032"), ("Kokapet", 17.3950, 78.3300, 11800, "500075"),
        ("Kondapur", 17.4700, 78.3570, 9900, "500084"), ("Tellapur", 17.4750, 78.2900, 7900, "502032"),
        ("Miyapur", 17.4968, 78.3614, 7500, "500049"), ("Narsingi", 17.3860, 78.3570, 9200, "500089"),
    ]),
    "Chennai": ("Tamil Nadu", ("Chennai International Airport", 12.9941, 80.1709), [
        ("Sholinganallur", 12.9010, 80.2279, 7300, "600119"), ("Porur", 13.0382, 80.1565, 7900, "600116"),
        ("Velachery", 12.9815, 80.2180, 9900, "600042"), ("Perumbakkam", 12.8920, 80.2010, 6200, "600100"),
        ("Anna Nagar", 13.0850, 80.2101, 15200, "600040"),
    ]),
    "Gurugram": ("Haryana", ("Indira Gandhi International Airport", 28.5562, 77.1000), [
        ("Golf Course Extension Road", 28.4100, 77.0800, 17500, "122102"),
        ("Dwarka Expressway", 28.4950, 77.0050, 13200, "122505"),
        ("Sohna Road", 28.4000, 77.0500, 11600, "122018"), ("Sector 65", 28.4000, 77.0700, 16200, "122102"),
    ]),
    "Noida": ("Uttar Pradesh", ("Indira Gandhi International Airport", 28.5562, 77.1000), [
        ("Sector 150", 28.4570, 77.4970, 9600, "201310"), ("Noida Extension", 28.6000, 77.4300, 6600, "201318"),
        ("Sector 137", 28.5100, 77.4100, 8600, "201305"), ("Sector 75", 28.5750, 77.3830, 8900, "201301"),
    ]),
}
COUNTS = {"Bengaluru": 40, "Mumbai": 24, "Pune": 22, "Hyderabad": 22, "Chennai": 16, "Gurugram": 15, "Noida": 15}

# Fictional builders. quality: 0.0 (poor) .. 1.0 (excellent); premium multiplies price.
BUILDERS = [
    ("Kestrel Habitat", 0.92, 1.18), ("Saptarishi Builders", 0.55, 0.95), ("Indigo Crest Developers", 0.80, 1.10),
    ("Banyan Grove Realty", 0.70, 1.00), ("Northwind Estates", 0.35, 0.90), ("Lotus Petal Homes", 0.65, 0.97),
    ("Silverline Constructions", 0.88, 1.12), ("Monsoon Ridge Developers", 0.25, 0.86), ("Terracotta Living", 0.75, 1.04),
    ("Polaris Infra Homes", 0.60, 0.98), ("Riverstone Realty", 0.95, 1.22), ("Copperleaf Developers", 0.45, 0.92),
    ("Saffron Skies Builders", 0.82, 1.08), ("Evergreen Arcadia", 0.68, 1.01), ("Granite & Glass Developers", 0.90, 1.20),
    ("Bluebell Habitat", 0.50, 0.94), ("Orchid Valley Realty", 0.78, 1.05), ("Vistara Buildwell", 0.40, 0.91),
]
SUFFIXES = ["Greens", "Heights", "Residency", "Enclave", "Vista", "Serenity", "Skyview", "Meadows", "Palms",
            "Horizon", "Aurum", "Crest", "Woods", "Lakeside", "Elysium", "One", "Boulevard", "Gardens", "Altura",
            "Harmony", "Sapphire", "Orchards", "Avenue", "Springs"]
AMENITIES = ["Swimming pool", "Gym", "Clubhouse", "Children's play area", "Jogging track", "Power backup",
             "24x7 security", "EV charging", "Co-working space", "Indoor games", "Tennis court", "Badminton court",
             "Rainwater harvesting", "STP", "Pet park", "Amphitheatre", "Party hall", "Senior citizen zone",
             "Yoga deck", "Supermarket", "Cricket pitch", "Sky lounge"]
BANKS = ["SBI", "HDFC Bank", "ICICI Bank", "Axis Bank", "LIC HFL", "Kotak Mahindra Bank", "Bank of Baroda",
         "PNB Housing", "Bajaj Housing Finance"]
SOURCES = [("Housing.com", 0.00), ("99acres", 0.015), ("MagicBricks", 0.01), ("NoBroker", -0.02),
           ("Square Yards", 0.005), ("Builder website", 0.035), ("Channel partner (broker)", -0.035),
           ("PropTiger", 0.0)]
REVIEW_SOURCES = ["Reddit", "Google Maps", "IndianRealEstateForum", "MouthShut", "Housing.com resident reviews",
                  "99acres resident reviews", "Facebook owners' group", "Twitter / X"]

POS_REVIEWS = [
    ("Happy with construction quality", "Site visits every quarter — the quality of plaster and fittings is good. Builder has been transparent about progress."),
    ("On time so far", "Construction is moving as per the RERA timeline. Slab work done on schedule, CRM team is responsive."),
    ("Great connectivity", "Metro and the tech park are close by, commute is easy. Value for money compared to nearby projects."),
    ("Well maintained amenities", "Moved in last year. Clubhouse, pool and gym are well maintained and the maintenance team is helpful."),
    ("Good appreciation", "Bought at launch, price has gone up nicely. Rent demand is good in this area."),
    ("Spacious layouts", "Efficient layouts with good ventilation, very little wasted space. Recommend the east-facing units."),
    ("Smooth registration", "Registration and handover were smooth. All documents including OC were shared on time."),
]
NEU_REVIEWS = [
    ("Decent but pricey", "Layouts are fine, amenities are standard. Price is on the higher side for this location."),
    ("Traffic during peak hours", "Project is okay, but the approach road gets congested in the evening. Metro should help once ready."),
    ("Average experience", "Neither great nor bad. Sales team promised more than what was delivered on the clubhouse."),
    ("Waiting for possession", "Progress is visible but slower than the brochure suggested. Keeping fingers crossed."),
]
NEG_REVIEWS = [
    ("Possession delayed again", "Possession was promised two years back, still not delivered. Builder keeps giving new dates, no compensation for delay."),
    ("Water problem", "No BWSSB/municipal connection yet, we depend on tankers. Maintenance charges keep going up."),
    ("Poor construction quality", "Seepage and cracks within the first year, leakage in bathrooms. Complaint tickets are not resolved."),
    ("Hidden charges", "Sales team hid extra charges for car parking and clubhouse at the time of booking. Felt cheated."),
    ("Unresponsive CRM", "CRM is unresponsive to escalation emails. Several owners have filed RERA complaints."),
    ("Unfinished amenities", "Took possession but clubhouse and pool are unfinished even after a year."),
    ("Waterlogging during rains", "The approach road floods every monsoon. Waterlogging in the basement parking too."),
]
HANDLES = ["homebuyer", "blr_dweller", "flat_hunter", "nri_investor", "techie", "owner", "resident", "firsthome",
           "investor", "commuter", "familyof4", "ex_tenant", "realty_watch", "punekar", "mumbaikar", "hyd_buyer"]


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def month_add(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    return date(d.year + y, m + 1, min(d.day, 28))


def rera_number(r, state, city):
    n = r.randint(1000, 9999)
    return "DEMO-" + {
        "Karnataka": f"PRM/KA/RERA/1251/{r.randint(300, 480)}/PR/{r.randint(170101, 261031)}/{n:06d}",
        "Maharashtra": f"P{'5180' if city == 'Mumbai' else '5210'}00{r.randint(10000, 99999)}",
        "Telangana": f"P02400{r.randint(10000, 99999)}",
        "Tamil Nadu": f"TN/29/Building/{n:04d}/{r.randint(2020, 2026)}",
        "Haryana": f"RC/REP/HARERA/GGM/{r.randint(500, 999)}/{r.randint(200, 700)}/{r.randint(2021, 2026)}/{r.randint(10, 99)}",
        "Uttar Pradesh": f"UPRERAPRJ{r.randint(100000, 999999)}",
    }[state]


def make_configs(r, ptype, psf):
    if ptype == "Apartment":
        pool = [("1 BHK", 1, 430, 560), ("2 BHK", 2, 640, 820), ("2.5 BHK", 2.5, 850, 980),
                ("3 BHK", 3, 1000, 1350), ("3.5 BHK", 3.5, 1350, 1550), ("4 BHK", 4, 1600, 2300)]
        start = r.randint(0, 2)
        picks = pool[start:start + r.randint(2, 4)]
    elif ptype == "Villa":
        picks = [("3 BHK Villa", 3, 1700, 2200), ("4 BHK Villa", 4, 2300, 3200), ("5 BHK Villa", 5, 3300, 4500)][: r.randint(2, 3)]
    else:  # Row House
        picks = [("3 BHK Row House", 3, 1450, 1800), ("4 BHK Row House", 4, 1900, 2400)]
    load = r.uniform(1.25, 1.38)  # super built-up / carpet loading
    out = []
    for label, bhk, lo, hi in picks:
        carpet = round(r.uniform(lo, hi) / 5) * 5
        sb = round(carpet * load / 5) * 5
        sb_hi = round(sb * r.uniform(1.03, 1.12) / 5) * 5
        units = r.randint(40, 260)
        out.append({
            "label": label, "bhk": bhk, "carpet_sqft": carpet, "super_builtup_sqft": sb,
            "price_min": round(sb * psf, -4), "price_max": round(sb_hi * psf * r.uniform(1.02, 1.08), -4),
            "units_total": units, "facing": r.choice(["East / North", "All facings", "East / West", "North"]),
        })
    return out


def build(seed: int) -> dict:
    r = random.Random(seed)
    used_names = set()
    records = []
    builder_stats: dict[str, dict] = {}

    for city, (state, airport, locs) in CITIES.items():
        for i in range(COUNTS[city]):
            bname, quality, premium = r.choice(BUILDERS)
            loc, lat, lng, base_psf, pin = r.choice(locs)
            short = bname.split()[0]
            for _ in range(20):
                name = f"{short} {r.choice(SUFFIXES)}"
                if name not in used_names:
                    break
                name = f"{short} {r.choice(SUFFIXES)} {r.choice(['II', 'Phase 2', 'Grand', 'Prime'])}"
                if name not in used_names:
                    break
            used_names.add(name)
            plat, plng = lat + r.uniform(-0.018, 0.018), lng + r.uniform(-0.018, 0.018)
            ptype = r.choices(["Apartment", "Villa", "Row House"], [0.8, 0.12, 0.08])[0]
            if city == "Mumbai":
                ptype = "Apartment"

            # timeline
            status = r.choices(["Pre-launch", "Under Construction", "Ready to Move"], [0.1, 0.62, 0.28])[0]
            if status == "Ready to Move":
                launch = month_add(TODAY, -r.randint(40, 90))
                rera_pos = month_add(launch, r.randint(36, 54))
                if rera_pos > TODAY:
                    rera_pos = month_add(TODAY, -r.randint(1, 18))
                progress = 100
            elif status == "Under Construction":
                launch = month_add(TODAY, -r.randint(4, 52))
                rera_pos = month_add(launch, r.randint(40, 66))
                # poor builders overrun their RERA date
                if quality < 0.45 and r.random() < 0.6:
                    rera_pos = month_add(TODAY, -r.randint(2, 20))
                elapsed = (TODAY - launch).days
                total = max((rera_pos - launch).days, 1)
                progress = int(min(97, max(5, elapsed / total * 100 * r.uniform(0.6 + quality * 0.3, 1.05))))
            else:
                launch = month_add(TODAY, r.randint(0, 3))
                rera_pos = month_add(launch, r.randint(48, 66))
                progress = 0
            builder_pos = month_add(rera_pos, -r.choice([0, 0, 3, 6, 6, 9, 12, 12, 18]))

            # RERA
            rera_status = "Registered"
            if status == "Pre-launch" and r.random() < 0.5:
                rera_status = "Applied"
            if quality < 0.45 and status == "Under Construction" and rera_pos < TODAY and r.random() < 0.5:
                rera_status = "Lapsed"
            if quality < 0.3 and r.random() < 0.12:
                rera_status = "Not Registered"

            psf = base_psf * premium * r.uniform(0.9, 1.1) * (1.15 if ptype == "Villa" else 1)
            configs = make_configs(r, ptype, psf)
            total_units = sum(c["units_total"] for c in configs)
            sold_frac = {"Pre-launch": r.uniform(0.0, 0.25), "Under Construction": r.uniform(0.35, 0.9),
                         "Ready to Move": r.uniform(0.85, 1.0)}[status]
            for c in configs:
                c["units_available"] = max(0, int(c["units_total"] * (1 - sold_frac) * r.uniform(0.7, 1.3)))
            avail = sum(c["units_available"] for c in configs)
            land = round(r.uniform(2.0, 18.0) if ptype == "Apartment" else r.uniform(8, 40), 1)

            # price history: monthly drift, quotes from several sources every ~2 months
            yearly = r.uniform(0.02, 0.13) + (0.02 if quality > 0.8 else 0)
            hist_start = max(launch, month_add(TODAY, -24))
            months = max(1, (TODAY.year - hist_start.year) * 12 + TODAY.month - hist_start.month)
            srcs = r.sample(SOURCES, r.randint(3, 6))
            main = configs[min(1, len(configs) - 1)]
            quotes = []
            for m in range(0, months + 1, 2):
                d = month_add(hist_start, m)
                if d > TODAY:
                    d = TODAY
                factor = (1 + yearly) ** ((m - months) / 12)
                for sname, bias in srcs:
                    if r.random() < 0.2:
                        continue
                    q_psf = psf * factor * (1 + bias + r.uniform(-0.03, 0.03))
                    quotes.append({
                        "config_label": main["label"], "source": sname, "source_url": None,
                        "price_per_sqft": round(q_psf), "price": round(q_psf * main["super_builtup_sqft"], -4),
                        "quoted_on": (d - timedelta(days=r.randint(0, 20))).isoformat(),
                        "notes": "Demo quote (synthetic)",
                    })
            # latest per other configuration
            for c in configs:
                if c is main:
                    continue
                for sname, bias in r.sample(srcs, min(2, len(srcs))):
                    q_psf = psf * (1 + bias + r.uniform(-0.03, 0.03))
                    quotes.append({
                        "config_label": c["label"], "source": sname, "source_url": None,
                        "price_per_sqft": round(q_psf), "price": round(q_psf * c["super_builtup_sqft"], -4),
                        "quoted_on": (TODAY - timedelta(days=r.randint(2, 40))).isoformat(),
                        "notes": "Demo quote (synthetic)",
                    })

            # approvals
            def appr(code, ok_prob, date_from=launch):
                roll = r.random()
                if roll < ok_prob:
                    return {"code": code, "status": "Obtained",
                            "reference": f"DEMO/{code}/{r.randint(1000, 9999)}",
                            "issued_on": month_add(date_from, -r.randint(1, 10)).isoformat()}
                if roll < ok_prob + (1 - ok_prob) * 0.5:
                    return {"code": code, "status": "Pending", "notes": "Applied; awaiting authority"}
                return {"code": code, "status": "Missing", "notes": "Not disclosed on RERA portal"}

            ok = 0.55 + quality * 0.45
            approvals = [appr("TITLE", min(1, ok + 0.15)), appr("EC", min(1, ok + 0.15)), appr("LAND_USE", min(1, ok + 0.1)),
                         appr("PLAN", min(1, ok + 0.1)), appr("CC", ok)]
            approvals.append({"code": "ENV", "status": "Not Applicable", "notes": "Built-up area below 20,000 sq m"}
                             if land < 4 else appr("ENV", ok))
            approvals.append(appr("FIRE", ok) if ptype == "Apartment" else
                             {"code": "FIRE", "status": "Not Applicable", "notes": "Low-rise"})
            near_air = haversine((plat, plng), airport[1:]) < 20
            approvals.append(appr("AAI", ok) if near_air or ptype == "Apartment" else
                             {"code": "AAI", "status": "Not Applicable"})
            approvals.append(appr("PCB", ok))
            approvals.append(appr("WATER", ok - 0.1))
            approvals.append(appr("POWER", ok))
            if status == "Pre-launch":
                for a in approvals:
                    if a["code"] in ("CC", "FIRE", "PCB", "WATER", "POWER") and a["status"] != "Not Applicable":
                        a.update({"status": "Pending", "notes": "Expected before construction"})
            if status == "Ready to Move":
                for code in ("OC", "COMPLETION", "KHATA"):
                    approvals.append(appr(code, min(1, ok + 0.05), rera_pos))

            # reviews
            n_rev = r.randint(3, 12) if status != "Pre-launch" else r.randint(0, 3)
            reviews = []
            for _ in range(n_rev):
                p_pos = 0.15 + quality * 0.7
                roll = r.random()
                if roll < p_pos:
                    title, body = r.choice(POS_REVIEWS)
                    rating = r.choice([4, 4, 5, 5, 4.5])
                elif roll < p_pos + 0.15:
                    title, body = r.choice(NEU_REVIEWS)
                    rating = 3
                else:
                    title, body = r.choice(NEG_REVIEWS)
                    rating = r.choice([1, 1.5, 2, 2])
                src = r.choice(REVIEW_SOURCES)
                if src in ("Reddit", "IndianRealEstateForum", "Facebook owners' group", "Twitter / X"):
                    rating = None  # forums have no star ratings
                reviews.append({
                    "source": src, "url": None, "author": f"{r.choice(HANDLES)}_{r.randint(10, 999)}",
                    "rating": rating, "posted_on": (TODAY - timedelta(days=r.randint(5, 700))).isoformat(),
                    "title": title, "body": body.replace("BWSSB/municipal", "municipal" if state != "Karnataka" else "BWSSB"),
                })

            # litigation
            lit = []
            n_cases = r.choices([0, 1, 2, 3], [quality * 0.9 + 0.1, 0.25, 0.12 * (1 - quality), 0.1 * (1 - quality)])[0]
            for k in range(n_cases):
                forum = r.choice(["RERA", "RERA", "Consumer Commission", "High Court"])
                lit.append({
                    "forum": forum, "case_ref": f"DEMO-{forum[:3].upper()}-{r.randint(100, 999)}/{r.randint(2022, 2026)}",
                    "filed_on": (TODAY - timedelta(days=r.randint(30, 900))).isoformat(),
                    "status": r.choice(["Open", "Open", "Disposed"]) if quality < 0.6 else r.choice(["Disposed", "Settled", "Open"]),
                    "summary": r.choice(["Allottees seek interest for delayed possession",
                                         "Refund claim after cancellation",
                                         "Dispute over super built-up area calculation",
                                         "Complaint on deviation from sanctioned plan",
                                         "Landowner dispute under joint development agreement"]),
                })

            nearby = [
                {"category": "Airport", "name": airport[0], "distance_km": round(haversine((plat, plng), airport[1:]), 1)},
                {"category": "Metro", "name": f"{loc} metro station" + (" (under construction)" if r.random() < 0.4 else ""),
                 "distance_km": round(r.uniform(0.4, 6), 1)},
                {"category": "School", "name": "International school (IB/CBSE)", "distance_km": round(r.uniform(0.5, 4), 1)},
                {"category": "Hospital", "name": "Multi-speciality hospital", "distance_km": round(r.uniform(0.8, 6), 1)},
                {"category": "IT Park", "name": "Tech park / office hub", "distance_km": round(r.uniform(1, 12), 1)},
                {"category": "Mall", "name": "Shopping mall", "distance_km": round(r.uniform(1, 8), 1)},
                {"category": "Railway", "name": "Railway station", "distance_km": round(r.uniform(2, 15), 1)},
            ]

            bank_n = int(r.uniform(0, 3) + quality * 5) if rera_status == "Registered" else r.randint(0, 1)
            rec = {
                "name": name,
                "builder": bname,
                "city": city, "state": state, "locality": loc, "pincode": pin,
                "address": f"{name}, {loc}, {city} {pin}",
                "lat": round(plat, 5), "lng": round(plng, 5),
                "property_type": ptype, "status": status,
                "launch_date": launch.isoformat(),
                "rera_number": rera_number(r, state, city) if rera_status != "Not Registered" else None,
                "rera_status": rera_status,
                "rera_possession_date": rera_pos.isoformat(),
                "builder_possession_date": builder_pos.isoformat(),
                "construction_progress": progress,
                "total_units": total_units, "available_units": avail,
                "towers": r.randint(1, 12) if ptype == "Apartment" else None,
                "floors": r.randint(12, 45 if city == "Mumbai" else 32) if ptype == "Apartment" else r.randint(2, 4),
                "land_area_acres": land, "open_space_pct": round(r.uniform(55, 82)),
                "amenities": sorted(r.sample(AMENITIES, r.randint(7, 17))),
                "bank_approvals": sorted(r.sample(BANKS, min(bank_n, len(BANKS)))),
                "description": (f"{name} is a {ptype.lower()} project by {bname} in {loc}, {city}, spread across "
                                f"{land} acres with {total_units} units in {', '.join(c['label'] for c in configs)} "
                                f"configurations. [Synthetic demo record]"),
                "is_demo": 1,
                "configurations": configs,
                "price_quotes": quotes,
                "approvals": approvals,
                "reviews": reviews,
                "litigation": lit,
                "nearby": nearby,
            }
            records.append(rec)
            bs = builder_stats.setdefault(bname, {"quality": quality, "projects": 0})
            bs["projects"] += 1

    # builder profiles (attached to the first record of each builder)
    seen = set()
    for rec in records:
        b = rec["builder"]
        if b in seen:
            continue
        seen.add(b)
        q = builder_stats[b]["quality"]
        rec["builder"] = {
            "name": b,
            "established_year": r.randint(1985, 2015),
            "projects_delivered": int(5 + q * 40 + r.randint(0, 10)),
            "projects_ongoing": builder_stats[b]["projects"] + r.randint(0, 6),
            "on_time_delivery_pct": round(min(98, max(15, q * 100 + r.uniform(-8, 6))), 1),
            "avg_delay_months": round(max(0, (1 - q) * 30 + r.uniform(-3, 4)), 1),
            "rera_complaints": int((1 - q) * 70 + r.randint(0, 12)),
            "website": None,
            "description": f"{b} is a fictional developer used in HousingSearch demo data.",
        }
    return {"generated_on": TODAY.isoformat(), "disclaimer": "SYNTHETIC DEMO DATA — not real projects.",
            "properties": records}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    data = build(a.seed)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    n = len(data["properties"])
    q = sum(len(p["price_quotes"]) for p in data["properties"])
    print(f"Wrote {n} demo projects, {q} price quotes -> {a.out}")
