# Data format

HousingSearch stores everything in one SQLite file (`data/housingsearch.db`). You load data with JSON (full project records) or CSV (price quotes). A complete example is in [`examples/sample_import.json`](../examples/sample_import.json).

## JSON project record

```jsonc
{
  "properties": [
    {
      // ---- identity (name + city + locality are required)
      "name": "Example Meadows",
      "city": "Pune",                      // state is inferred for supported cities
      "locality": "Baner",
      "slug": "optional-stable-id",        // optional; otherwise generated from name+locality+city
      "builder": "Example Developers",     // or a full builder object (see below)

      // ---- location
      "address": "…", "pincode": "411045", "lat": 18.559, "lng": 73.786,

      // ---- project
      "property_type": "Apartment",        // Apartment | Villa | Row House | Penthouse | Plot
      "status": "Under Construction",      // Pre-launch | Under Construction | Ready to Move
      "launch_date": "2025-03-01",
      "total_units": 320, "available_units": 140,
      "towers": 3, "floors": 24, "land_area_acres": 4.2, "open_space_pct": 70,
      "amenities": ["Swimming pool", "Gym"],
      "bank_approvals": ["SBI", "HDFC Bank"],
      "description": "…",

      // ---- RERA
      "rera_number": "P52100000000",
      "rera_status": "Registered",         // Registered | Applied | Lapsed | Revoked | Not Registered
      "rera_possession_date": "2029-06-30",// date declared to RERA (legally binding)
      "builder_possession_date": "2028-12-31", // date the builder/brokers advertise
      "construction_progress": 35,         // % from the latest RERA quarterly update

      // ---- child collections
      "configurations": [ { "label": "2 BHK", "bhk": 2, "carpet_sqft": 760, "super_builtup_sqft": 1010,
                            "price_min": 11500000, "price_max": 12400000,
                            "units_total": 180, "units_available": 80, "facing": "East" } ],
      "price_quotes":   [ { "config_label": "2 BHK", "source": "Housing.com", "source_url": "https://…",
                            "price": 11800000, "price_per_sqft": 11683, "quoted_on": "2026-11-02",
                            "notes": "Asking price" } ],
      "approvals":      [ { "code": "PLAN", "status": "Obtained", "reference": "PMC/BP/000",
                            "issued_on": "2024-12-01", "document_url": "https://…" } ],
      "reviews":        [ { "source": "Reddit", "url": "https://…", "author": "u/x", "rating": null,
                            "posted_on": "2026-09-20", "title": "…", "body": "…" } ],
      "litigation":     [ { "forum": "RERA", "case_ref": "CC000", "filed_on": "2026-02-01",
                            "status": "Open", "summary": "…", "url": "https://…" } ],
      "nearby":         [ { "category": "Metro", "name": "…", "distance_km": 1.4 } ]
    }
  ]
}
```

### Builder object

```json
{ "name": "Example Developers", "established_year": 2004, "projects_delivered": 18,
  "projects_ongoing": 4, "on_time_delivery_pct": 72, "avg_delay_months": 7,
  "rera_complaints": 9, "website": "https://…", "description": "…" }
```

### Approval codes

| Code | Approval | Stage |
|---|---|---|
| `TITLE` | Clear land title & title search report | pre-launch |
| `EC` | Encumbrance Certificate | pre-launch |
| `LAND_USE` | Land-use conversion (DC conversion / NA order / CLU) | pre-launch |
| `PLAN` | Building plan sanction | pre-launch |
| `CC` | Commencement Certificate | pre-launch |
| `RERA` | RERA registration | pre-launch |
| `ENV` | Environmental Clearance (SEIAA, ≥ 20,000 sq m) | pre-launch |
| `AAI` | Height clearance NOC (Airports Authority of India) | pre-launch |
| `FIRE` | Fire NOC | construction |
| `PCB` | Pollution board Consent to Establish | construction |
| `WATER` | Water & sewerage connection NOC | construction |
| `POWER` | Electricity load sanction | construction |
| `OC` | Occupancy Certificate | completion |
| `COMPLETION` | Completion Certificate | completion |
| `KHATA` | Khata / property-tax assessment | completion |

Statuses: `Obtained`, `Pending`, `Missing`, `Not Yet Due`, `Not Applicable`, `Unknown`.
An approval you don't supply is shown as `Unknown` (or `Not Yet Due` for completion-stage approvals on unfinished projects). Mandatory approvals that are `Unknown` count as **missing** for red flags.

## Merge rules

Records are matched by `slug`, then by `rera_number`, then by generated slug (name + locality + city).

* Scalar fields you include overwrite stored values; fields you omit are kept.
* `configurations`, `approvals` and `nearby` are **replaced** when supplied (they describe current state).
* `price_quotes`, `reviews` and `litigation` are **appended** and de-duplicated, so you can import new quotes every week and keep history.

## CSV price quotes

Columns (header row required): `project, city, locality, config_label, source, source_url, price, price_per_sqft, quoted_on, notes`.
`price` accepts `11800000`, `1.18 Cr`, `85 L`, `₹ 85,00,000`. Rows whose project+city don't match an existing project are reported as `unmatched`. See [`examples/sample_quotes.csv`](../examples/sample_quotes.csv).
