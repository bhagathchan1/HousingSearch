"""Reference data: the approvals a residential project needs, RERA portals and
state-wise transaction costs.

The approval list is a buyer's checklist distilled from RERA disclosure formats and
state building bye-laws. Authority names differ by state, so each approval carries a
per-state authority map. Figures for stamp duty/registration are indicative defaults
for the cost calculator; always confirm the current rate with the sub-registrar.
"""

from __future__ import annotations

STATES = {
    "Karnataka": {
        "rera_name": "RERA Karnataka (K-RERA)",
        "rera_url": "https://rera.karnataka.gov.in/",
        "stamp_duty_pct": 5.6,  # 5% + surcharge & cess, for value > ₹45 lakh
        "stamp_duty_women_pct": 5.6,
        "registration_pct": 1.0,
        "registration_cap": None,
    },
    "Maharashtra": {
        "rera_name": "MahaRERA",
        "rera_url": "https://maharera.maharashtra.gov.in/",
        "stamp_duty_pct": 6.0,  # 5% + 1% metro cess in Mumbai / Pune
        "stamp_duty_women_pct": 5.0,
        "registration_pct": 1.0,
        "registration_cap": 30000,
    },
    "Telangana": {
        "rera_name": "TG RERA",
        "rera_url": "https://rerait.telangana.gov.in/",
        "stamp_duty_pct": 6.0,  # 4% stamp + 1.5% transfer duty + 0.5% registration bundled
        "stamp_duty_women_pct": 6.0,
        "registration_pct": 0.5,
        "registration_cap": None,
    },
    "Tamil Nadu": {
        "rera_name": "TNRERA",
        "rera_url": "https://rera.tn.gov.in/",
        "stamp_duty_pct": 7.0,
        "stamp_duty_women_pct": 7.0,
        "registration_pct": 2.0,
        "registration_cap": None,
    },
    "Haryana": {
        "rera_name": "HRERA Gurugram",
        "rera_url": "https://haryanarera.gov.in/",
        "stamp_duty_pct": 7.0,
        "stamp_duty_women_pct": 5.0,
        "registration_pct": 0.0,
        "registration_cap": 50000,  # slab-based flat fee, max ₹50,000
    },
    "Uttar Pradesh": {
        "rera_name": "UP RERA",
        "rera_url": "https://www.up-rera.in/",
        "stamp_duty_pct": 7.0,
        "stamp_duty_women_pct": 6.0,
        "registration_pct": 1.0,
        "registration_cap": None,
    },
}

CITY_STATE = {
    "Bengaluru": "Karnataka",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Thane": "Maharashtra",
    "Hyderabad": "Telangana",
    "Chennai": "Tamil Nadu",
    "Gurugram": "Haryana",
    "Noida": "Uttar Pradesh",
}

# stage: when the approval is expected.
#   pre_launch  -> must exist before the builder may advertise / take bookings
#   construction-> required before / during construction
#   completion  -> issued only once the building is complete
# mandatory: False means "depends on project size / location" (see `applies_when`).
APPROVALS = [
    {
        "code": "TITLE",
        "name": "Clear land title & title search report",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Proves the builder (or landowner in a JDA) owns the land. A 30-year title search by an advocate is standard.",
        "authority": {"default": "Sub-Registrar records / advocate title opinion"},
    },
    {
        "code": "EC",
        "name": "Encumbrance Certificate (EC)",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Shows the land is free of mortgages and legal dues. Look for 13–30 years of history.",
        "authority": {"default": "Sub-Registrar Office"},
    },
    {
        "code": "LAND_USE",
        "name": "Land-use conversion (agricultural → residential)",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Building homes on agricultural land without conversion is illegal and blocks registration and loans.",
        "authority": {
            "Karnataka": "Deputy Commissioner (DC conversion)",
            "Maharashtra": "Collector (NA order)",
            "Telangana": "RDO / HMDA (NALA conversion)",
            "Tamil Nadu": "DTCP / CMDA (land-use classification)",
            "Haryana": "DTCP Haryana (CLU / licence)",
            "Uttar Pradesh": "Noida / YEIDA Authority (lease allotment)",
            "default": "District Collector",
        },
    },
    {
        "code": "PLAN",
        "name": "Building plan sanction",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Approved layout & floor plans. Deviations from the sanctioned plan can block the Occupancy Certificate.",
        "authority": {
            "Karnataka": "BBMP / BDA / BMRDA",
            "Maharashtra": "BMC / PMC / PMRDA",
            "Telangana": "GHMC / HMDA",
            "Tamil Nadu": "CMDA / DTCP",
            "Haryana": "DTCP Haryana",
            "Uttar Pradesh": "Noida Authority",
            "default": "Local planning authority",
        },
    },
    {
        "code": "CC",
        "name": "Commencement Certificate",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Permission to start construction. Without it, construction is unauthorised.",
        "authority": {"default": "Local planning authority / municipal corporation"},
    },
    {
        "code": "RERA",
        "name": "RERA registration",
        "stage": "pre_launch",
        "mandatory": True,
        "why": "Mandatory for projects > 500 sq m or > 8 units. Builder cannot advertise or sell without it.",
        "authority": {"default": "State RERA authority"},
    },
    {
        "code": "ENV",
        "name": "Environmental Clearance",
        "stage": "pre_launch",
        "mandatory": False,
        "applies_when": "Built-up area ≥ 20,000 sq m",
        "why": "Required from SEIAA for large projects; violations have led to court-ordered demolitions.",
        "authority": {"default": "State Environment Impact Assessment Authority (SEIAA)"},
    },
    {
        "code": "FIRE",
        "name": "Fire NOC",
        "stage": "construction",
        "mandatory": False,
        "applies_when": "Buildings above 15 m (≈ 5 floors) — almost all high-rises",
        "why": "Provisional NOC at plan stage, final NOC before occupancy.",
        "authority": {"default": "State Fire & Emergency Services"},
    },
    {
        "code": "AAI",
        "name": "Height clearance NOC",
        "stage": "pre_launch",
        "mandatory": False,
        "applies_when": "Near airports / defence zones or tall towers",
        "why": "Airports Authority of India must clear building height near flight paths.",
        "authority": {"default": "Airports Authority of India (NOCAS)"},
    },
    {
        "code": "PCB",
        "name": "Consent to Establish (pollution board)",
        "stage": "construction",
        "mandatory": False,
        "applies_when": "Large projects with STP / DG sets",
        "why": "Covers sewage treatment and waste handling. Consent to Operate follows at completion.",
        "authority": {
            "Karnataka": "KSPCB",
            "Maharashtra": "MPCB",
            "Telangana": "TGPCB",
            "Tamil Nadu": "TNPCB",
            "Haryana": "HSPCB",
            "Uttar Pradesh": "UPPCB",
            "default": "State Pollution Control Board",
        },
    },
    {
        "code": "WATER",
        "name": "Water & sewerage connection NOC",
        "stage": "construction",
        "mandatory": True,
        "why": "Without it, residents depend on tankers indefinitely.",
        "authority": {
            "Karnataka": "BWSSB",
            "Maharashtra": "BMC / PMC water dept.",
            "Telangana": "HMWSSB",
            "Tamil Nadu": "CMWSSB",
            "Haryana": "GMDA",
            "Uttar Pradesh": "Noida Authority (Jal)",
            "default": "Water supply board",
        },
    },
    {
        "code": "POWER",
        "name": "Electricity load sanction",
        "stage": "construction",
        "mandatory": True,
        "why": "Permanent power connection; temporary construction supply is costlier for residents.",
        "authority": {
            "Karnataka": "BESCOM",
            "Maharashtra": "MSEDCL / Adani / Tata Power",
            "Telangana": "TGSPDCL",
            "Tamil Nadu": "TANGEDCO",
            "Haryana": "DHBVN",
            "Uttar Pradesh": "PVVNL",
            "default": "Electricity distribution company",
        },
    },
    {
        "code": "OC",
        "name": "Occupancy Certificate (OC)",
        "stage": "completion",
        "mandatory": True,
        "why": "Certifies the building follows the sanctioned plan and is safe to occupy. Without OC, utilities and resale can be blocked.",
        "authority": {"default": "Local planning authority / municipal corporation"},
    },
    {
        "code": "COMPLETION",
        "name": "Completion Certificate",
        "stage": "completion",
        "mandatory": True,
        "why": "Confirms construction is finished per approved plans.",
        "authority": {"default": "Local planning authority / municipal corporation"},
    },
    {
        "code": "KHATA",
        "name": "Khata / property-tax assessment",
        "stage": "completion",
        "mandatory": True,
        "why": "Needed to pay property tax, transfer ownership and get loans on resale.",
        "authority": {
            "Karnataka": "BBMP (A-Khata)",
            "Maharashtra": "Municipal corporation property tax",
            "default": "Municipal corporation",
        },
    },
]

APPROVAL_BY_CODE = {a["code"]: a for a in APPROVALS}

APPROVAL_STATUSES = ["Obtained", "Pending", "Missing", "Not Yet Due", "Not Applicable", "Unknown"]


def authority_for(code: str, state: str) -> str:
    a = APPROVAL_BY_CODE.get(code)
    if not a:
        return ""
    return a["authority"].get(state) or a["authority"]["default"]


# Listing portals a buyer typically cross-checks. Used to build "verify live" links:
# a site-restricted web search for the project name, so the user sees the current
# quote on each portal without this tool scraping them.
PORTALS = [
    {"name": "Housing.com", "domain": "housing.com"},
    {"name": "99acres", "domain": "99acres.com"},
    {"name": "MagicBricks", "domain": "magicbricks.com"},
    {"name": "NoBroker", "domain": "nobroker.in"},
    {"name": "Square Yards", "domain": "squareyards.com"},
    {"name": "PropTiger", "domain": "proptiger.com"},
    {"name": "Commonfloor", "domain": "commonfloor.com"},
]

FORUMS = [
    {"name": "Reddit", "domain": "reddit.com"},
    {"name": "Google Maps reviews", "domain": "google.com/maps"},
    {"name": "Team-BHP / IndiaPropertyForum", "domain": "indianrealestateforum.com"},
    {"name": "MouthShut", "domain": "mouthshut.com"},
    {"name": "Consumer complaints", "domain": "consumercomplaints.in"},
]

GST = {
    "under_construction_pct": 5.0,  # without ITC; 1% for affordable (≤ ₹45L & ≤ 60/90 sqm)
    "affordable_pct": 1.0,
    "affordable_limit": 4_500_000,
}
