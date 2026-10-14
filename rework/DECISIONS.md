# S.U.R.G.E. — locked decisions

## Step 0 (locked 2026-10-12)

| # | Decision | Locked value |
|---|---|---|
| 1 | Project name | **S.U.R.G.E.**: Spatial Unit Response Generator for Epidemics |
| 2 | One-sentence pitch | A disaster produces a flood of data; S.U.R.G.E. turns that data into treatment sites, ward sizes and ready-to-assemble wards, automatically. |
| 3 | Test case | Forest Guinea (Guéckédou · Macenta · Kissidougou), 2014 Ebola outbreak |
| 4 | Tools | Python for data → location → ward sizing; Grasshopper (linked with Hops) for the automatic ward design |
| 5 | Authorship | Sole author: Shahriar Bigdeli. Origin: 2015 studio project "Parametric Response System (P.R.S.)", Design 5A ARCT5500, UWA |

## Step 1: data

See `data/SOURCES.md`.

## Step 1 gaps (decided 2026-10-12)

| Gap | Decision |
|---|---|
| Pre-outbreak health facilities | Shahriar downloads (WHO / Maina et al. 2019) → `data/user/` |
| Rainfall / seasonal access | Shahriar downloads (CHIRPS 2014 monthly) → `data/user/chirps/` |
| Mobility | Road-travel-time gravity model on OSM 2014 + HRSL is the mobility layer. The whole project is a hypothetical scenario, so it is not flagged separately. |
| ETU coordinates, WorldPop 2014, whole-outbreak prefecture cases | Not pursued. Validation uses the sitrep CTE evidence; calibration uses WHO national weekly + prefecture sitreps. |
| Missing facility locations (incl. Guéckédou hospital) | Repaired by rule, not by hand: village-name matching, hospital at town centre, scenario placement for the rest. Every point records its `location_source`. Synthetic data is acceptable because the project showcases the workflow. Health-facility data is closed. |

## Step 2 (2026-10-12)

| Decision | Value |
|---|---|
| Outbreak model | Metapopulation SEIR on 90 settlement patches, road-time gravity mobility, calibrated to MoH prefecture sitreps (Aug–Oct 2014) |
| Reporting rate | Fixed at 40% (CDC 2014 ×2.5 correction), not fitted |
| Planning window | Aug–Oct 2014 (no forecast beyond the data) |
| Number of sites | Chosen automatically: smallest number reaching 95% coverage at 1.5 h → 4 |
| Optimiser | Capacitated maximal covering MILP, HiGHS (scipy.optimize.milp) |
| Parameters | All MUST/SHOULD thresholds and weights in `pipeline/s2_params.py` |

## Step 3 (2026-10-12)

| Decision | Value |
|---|---|
| Ratios | Draft from MSF/WHO guidance (from memory) in `pipeline/s3_params.py`, to be verified by Shahriar |
| Module | 12 beds; every ward rounded up to whole modules |
| Ward split | suspect 25% / probable 15% / confirmed 60% of isolation beds |
| Output for step 4 | `data/s3/briefs.json` |

## Step 4 (2026-10-12)

| Decision | Value |
|---|---|
| Kit of parts | 6 m structural bay; ward module 6 × 18 m (12 beds), from the 2015 origami tent; 6 × 6 m service bays |
| Generator | Rule-based layout in Python (`pipeline/s4_layout.py`) with automatic checks |
| Grasshopper (first) | Python 3 draw component + Hops server (`grasshopper/`); Rhino 8 |
| Grasshopper (final, 2026-10-14) | Native definition `grasshopper/SURGE_wards.gh`, built by hand from built-in components so every rule is visible; it reads `data/s4/gh/briefs_gh.csv` and matches `reference_S*.csv`. Tutorial: `grasshopper/GH_TUTORIAL.md` |

## Step 5: web planner (2026-10-14)

| Decision | Value |
|---|---|
| Engine | Browser port of the step 3 brief and step 4 layout rules (`web/js/engine.js`), tested against the Python output; Grasshopper stays the design/teaching file |
| Site choice | The user picks one of the 936 MUST-passing candidates (or an optimised site) on the map, not any point |
| Demand | Confirmed patients start at the modelled demand (brief for S1–S4, otherwise reachable peak demand capped at 120) and can be overridden |
| Hosting | Static site, GitHub Pages via Actions; no map tiles (own vector base map) |
