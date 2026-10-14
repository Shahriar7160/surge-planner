"""S.U.R.G.E. step 3 — ratios that turn bed demand into a ward brief.

DRAFT values from general MSF / WHO Ebola treatment-centre guidance, written from memory.
Every entry carries a `note`; check and replace them, then rerun:  python pipeline/s3_run.py
"""

BEDS_PER_MODULE = 12            # one prefabricated ward module (2015 brief)
MIN_MODULES_PER_WARD = 1

# ---------------------------------------------------------------- beds
# Step 2 gives beds for symptomatic cases (= confirmed ward). Suspect and probable wards are added on top.
WARD_SPLIT = {                  # share of ALL isolation beds
    "suspect":   {"share": 0.25, "risk": "high", "note": "awaiting test result; single bays preferred"},
    "probable":  {"share": 0.15, "risk": "high", "note": "symptomatic, epidemiological link, awaiting confirmation"},
    "confirmed": {"share": 0.60, "risk": "high", "note": "laboratory-confirmed cases"},
}

# ---------------------------------------------------------------- staff (people per bed over 24 h, plus fixed)
STAFF = {
    "clinical_confirmed": {"per_bed": 2.0, "fixed": 0, "note": "doctors + nurses, confirmed ward"},
    "clinical_suspect_probable": {"per_bed": 1.0, "fixed": 0, "note": "doctors + nurses, suspect/probable wards"},
    "hygiene": {"per_bed": 1.0, "fixed": 4, "note": "water-sanitation-hygiene, sprayers, burial team"},
    "lab": {"per_bed": 0.03, "fixed": 4, "note": "on-site PCR lab (mobile lab of the 2015 brief)"},
    "pharmacy_logistics": {"per_bed": 0.3, "fixed": 4, "note": "stores, supply chain, drivers"},
    "admin_psychosocial": {"per_bed": 0.1, "fixed": 4, "note": "admin, data, health promotion, counselling"},
    "security": {"per_bed": 0.0, "fixed": 6, "note": "gates and perimeter"},
}
SHIFTS = 3
STAFF_ON_SITE_DORM_SHARE = 0.3  # share of staff housed on site (international / travelling staff)

# ---------------------------------------------------------------- daily supplies
SUPPLY = {
    "water_l_per_bed": {"value": 400, "note": "WHO range 300–400 L per patient per day"},
    "water_l_per_staff": {"value": 50, "note": "drinking, washing, chlorine solutions"},
    "power_kw_per_bed": {"value": 1.0, "note": "lighting, fans, oxygen, lab; plus base load"},
    "power_kw_base": {"value": 15, "note": "lab, stores, admin"},
    "medical_waste_kg_per_bed": {"value": 8, "note": "PPE and patient waste, all incinerated"},
    "ppe_sets_per_clinical_staff": {"value": 2, "note": "entries into the red zone per person per day"},
    "chlorine_l_per_bed": {"value": 20, "note": "0.05% and 0.5% solutions"},
}

# ---------------------------------------------------------------- spaces (m² = fixed + per_bed × beds)
# zone: red = high risk, amber = transition (dress/undress, decontamination), green = low risk, service = outside
SPACES = [
    # name,                 zone,     fixed, per_bed, per_ward, note
    ("triage",              "amber",   30,    0.4,  0,  "screening at the single patient entrance"),
    ("ward_suspect",        "red",     0,     9.0,  0,  "9 m² per bed incl. aisle"),
    ("ward_probable",       "red",     0,     9.0,  0,  ""),
    ("ward_confirmed",      "red",     0,     9.0,  0,  ""),
    ("donning",             "green",   0,     0,    15, "one dressing room per ward"),
    ("doffing_decon",       "amber",   0,     0,    20, "undressing + chlorine showers, one per ward"),
    ("patient_discharge",   "amber",   12,    0,    0,  "shower and clean clothes for recovered patients"),
    ("morgue",              "red",     0,     0.6,  0,  "≈ 1 place per 10 confirmed beds × 6 m²"),
    ("lab",                 "green",   40,    0,    0,  "PCR lab, sample reception from the red side"),
    ("pharmacy",            "green",   20,    0.3,  0,  ""),
    ("stores",              "green",   30,    0.5,  0,  "PPE, consumables"),
    ("laundry",             "amber",   20,    0.4,  0,  ""),
    ("staff_rest",          "green",   0,     0,    0,  "computed: 1.5 m² per person on shift"),
    ("staff_dormitory",     "service", 0,     0,    0,  "computed: 6 m² per resident staff"),
    ("admin_data",          "green",   20,    0.1,  0,  ""),
    ("family_visiting",     "amber",   30,    0,    0,  "talk across the double fence"),
    ("water_treatment",     "service", 40,    0,    0,  "bladder tanks + chlorination (2015 water filtering cycle)"),
    ("generator",           "service", 25,    0,    0,  ""),
    ("incinerator_waste",   "red",     25,    0.1,  0,  "downwind, inside the red perimeter"),
    ("loading_zone",        "service", 150,   0,    0,  "truck turning and unloading"),
    ("burial_area",         "service", 0,     0,    0,  "computed: 3 m² per expected death over 90 days"),
]
CIRCULATION_FACTOR = 1.30       # corridors, one-way routes between zones
SITE_COVERAGE = 0.35            # built footprint / fenced plot (open space, buffers, fire breaks)
FENCE_GAP_M = 1.0               # double fence, 1 m apart (MSF)
CASE_FATALITY = 0.6             # for morgue and burial sizing (2014 Guinea ≈ 60–70%)

# ---------------------------------------------------------------- deployment
PLANNING_FROM = "2014-08-01"
DEPLOY_DAYS = 14                # first modules usable two weeks after the decision
