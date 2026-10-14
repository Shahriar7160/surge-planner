"""S.U.R.G.E. step 2 — every parameter in one place.

Change a number here and rerun:  python pipeline/s2_run.py
MUST parameters are hard filters: a candidate site that fails one is removed.
SHOULD parameters are weighted scores used to rank the sites that pass.
"""

# ------------------------------------------------------------------ road network
SPEED_KMH = {  # dry season
    "trunk": 50, "trunk_link": 40, "primary": 45, "secondary": 35, "tertiary": 28, "tertiary_link": 25,
    "road": 20, "unclassified": 20, "residential": 15, "service": 12, "track": 10,
    "path": 4, "footway": 4, "pedestrian": 4,
}
TRUCK_ROADS = {"trunk", "trunk_link", "primary", "secondary", "tertiary", "tertiary_link", "road",
               "unclassified", "residential", "service", "track"}
RAINY_FACTOR = {"track": 0.5, "path": 0.6, "footway": 0.6, "unclassified": 0.7, "road": 0.7}  # × speed
RAINY_MONTH_MM = 300            # a month with more rain than this uses rainy-season speeds (CHIRPS 2014)
WALK_KMH = 4                    # off-network access to the nearest road node

# ------------------------------------------------------------------ outbreak model (calibrated in s2_outbreak)
START_DATE = "2013-12-01"       # index case, Meliandou (Guéckédou)
SEED_PLACE = "Meliandou"
INCUBATION_D = 9.4              # 1/sigma
INFECTIOUS_D = 7.4              # 1/gamma
HORIZON = "2014-10-31"          # forecast to (3 months after planning date; beyond this the fit is extrapolation)
PLANNING_FROM = "2014-08-01"    # S.U.R.G.E. is deployed with data up to here; demand counted after it
MOBILITY_DECAY_H = 2.0          # gravity kernel exp(-t / decay)
P_SEEK_CARE = 0.7               # share of symptomatic cases that need an isolation bed
LENGTH_OF_STAY_D = 10           # days in a bed
SUSPECT_PER_CONFIRMED = 1.0     # suspects admitted per confirmed case (MoH sitreps ~1:1)
REPORTING_RATE = 0.4            # share of true cases that were reported (CDC, Meltzer et al. 2014: ×2.5 correction)
MIN_MOBILITY_SHARE = 0.005      # floor so patches stay coupled (identifiability)

# ------------------------------------------------------------------ MUST parameters (hard filters)
MUST = {
    "max_patient_travel_h": 1.5,        # #3 patients reach the site by road within this time
    "max_slope_pct": 5.0,               # #6 flat, buildable land
    "exclude_landcover": [80, 90, 95],  # #6 water, wetland, mangrove (ESA WorldCover classes)
    "exclude_tree_cover": True,         # #6 not inside closed forest (WorldCover 10)
    "min_river_distance_m": 200,        # #7 flood risk: keep clear of rivers and streams
    "min_settlement_distance_m": 500,   # #5 isolation from villages/towns (hamlets: half)
    "max_road_distance_m": 1000,        # #4 truck access: within this of a truck-passable road
    "max_water_distance_m": 2000,       # #8 water supply from a river or stream
    "max_lab_travel_h": 2.0,            # #9 sample transport to a hospital (mobile-lab hub)
    "min_buildable_cells": 4,           # #10 suitable 90 m cells within 150 m (room for modules + buffer)
}

# ------------------------------------------------------------------ SHOULD parameters (weights sum to 1)
SHOULD = {
    "cell_coverage": 0.10,          # #11 near a mobile-phone tower (reporting)
    "near_hospital": 0.20,          # #12 referral and staff from an existing hospital
    "helipad_space": 0.10,          # #13 open, very flat grass nearby (drones, helicopter)
    "rainy_access": 0.15,           # #14 travel time barely worse in the rainy season
    "border_flow": 0.10,            # #15 near the Sierra Leone / Liberia border (cross-border cases)
    "waste_downhill": 0.10,         # #16 site lower than surrounding settlements (wastewater away from them)
    "burial_space": 0.05,           # #17 more suitable land nearby for a safe burial site
    "community_acceptance": 0.10,   # #18 away from forest edges (sacred forest proxy)
    "fuel_supply": 0.10,            # #19 close to a town (fuel, power, markets)
}

# ------------------------------------------------------------------ optimisation
CANDIDATE_SPACING_M = 500
BEDS_PER_MODULE = 12
MAX_MODULES_PER_SITE = 10
MAX_SITES = 8                   # budget: upper limit on the number of treatment centres
AUTO_SITES = True               # choose the smallest number of sites that reaches TARGET_COVERAGE
TARGET_COVERAGE = 0.95          # share of peak bed demand covered within the travel limit
SCORE_WEIGHT = 0.15             # how much the SHOULD score counts against covered demand
SWEEP_SITES = [2, 3, 4, 5, 6, 8, 10]
SWEEP_TRAVEL_H = [0.75, 1.0, 1.5, 2.0, 3.0]
