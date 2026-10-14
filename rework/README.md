# S.U.R.G.E. — Spatial Unit Response Generator for Epidemics

> A disaster produces a flood of data; S.U.R.G.E. turns that data into treatment sites, ward sizes and
> ready-to-assemble wards, automatically.

**Test case:** Forest Guinea (Guéckédou · Macenta · Kissidougou), 2014 Ebola outbreak.
**Tools:** Python (data → outbreak → location → ward sizing) and Grasshopper (automatic ward design).
**Author:** Shahriar Bigdeli. A rework of the 2015 UWA studio project "Parametric Response System (P.R.S.)",
Design 5A ARCT5500. The scenario is hypothetical; some inputs are repaired or synthetic (each one is labelled), because
the project demonstrates the workflow.

---

## What the project does

```
 1 DATA            2 LOCATION                 3 WARD SIZE              4 WARD DESIGN
 population,   →   outbreak model → bed   →   beds → modules,      →   kit of parts + layout rules
 roads, cases,     demand → MUST filters,     staff, supplies,         → plan, 3D, checks
 terrain, rain,    SHOULD scores → optimiser  every room's area        (Python generator and native
 facilities        picks the sites                                     Grasshopper definition)
```

**Step 1 · Data.** Open datasets for the study area are downloaded, clipped and aligned on a 90 m grid: Meta HRSL
population, Copernicus 30 m terrain, ESA WorldCover land cover, OSM 2014 roads and places, geoBoundaries admin areas,
Guinea MoH and WHO case reports (2014), MoH health-facility list, CHIRPS 2014 monthly rainfall. Missing facility
locations (including the Guéckédou hospital) are repaired by rule, and every point records how it was located.
→ `data/SOURCES.md`, `data/DATA_QA.md`

**Step 2 · Location.** A metapopulation SEIR model on 90 settlement patches, linked by a road-travel-time gravity model,
is calibrated to the 2014 MoH case counts (R₀ 1.56, log RMSE 0.096). Its bed demand feeds the siting:
- **MUST** filters remove land that is too steep, flooded, forest or water, too close to houses, without truck access,
  water or lab reach, or too small: 68,885 candidates → 936.
- **SHOULD** criteria score the rest (hospital nearby, rainy-season access, helipad space, waste downhill, …).
- A capacitated maximal covering optimiser (MILP, HiGHS) picks the sites. The number of sites is chosen
  automatically: the smallest number that serves ≥ 95% of peak demand within 1.5 h.

**Result:** 4 sites serve 97% of peak demand. The 2015 grid method needed 33 units. The two largest sites sit next to
Macenta and Guéckédou, where the 2014 treatment centres actually opened. Nine scenarios and a 200-run Monte Carlo show
how the choice changes when a variable changes. → `data/s2/README.md`

**Step 3 · Ward size.** For each site: peak confirmed beds → suspect / probable / confirmed wards (25 / 15 / 60%) →
rounded up to 12-bed modules → staff, water, power and the area of every support room
(`area = fixed + per_bed × beds + per_ward × wards`). S1: 120 confirmed beds → 5 / 3 / 10 modules = 216 beds, 668 staff.
→ `data/s3/README.md`

**Step 4 · Ward design.** A kit of parts on a 6 m structural bay: the 2015 origami tent becomes a 6 × 18 m, 12-bed ward
module, and every support room is a whole number of 6 × 6 m bays. Layout rules place everything:
- triage is the only patient entrance;
- patients move one way: suspect → probable → confirmed → discharge or morgue;
- every ward row starts with donning, a PPE store and doffing;
- the low-risk column sits behind a double fence;
- rows wrap at a maximum length to keep staff walks short.

Automatic checks test the bed count, overlaps, red/green contact and staff walking distance. → `data/s4/README.md`

The ward design exists twice, and the two versions match:
- `pipeline/s4_layout.py`: the Python generator, used for the figures and the map.
- `grasshopper/SURGE_wards.gh`: a native Grasshopper definition (no scripts) that reads the brief CSV and rebuilds
  the same layout with sliders. `grasshopper/GH_TUTORIAL.md` teaches how to build it, lesson by lesson.

---

## Folder map

| Path | What it is |
|---|---|
| `DECISIONS.md` | every locked decision, step by step |
| `pipeline/` | Python, one file per step (`s1_*` data, `s2_*` location, `s3_*` ward size, `s4_*` ward design); all parameters in `s2_params.py`, `s3_params.py`, `s4_params.py` |
| `data/processed/` | aligned rasters and vectors (step 1) |
| `data/s2/`, `data/s3/`, `data/s4/` | results and figures of steps 2–4, each with a README |
| `data/s4/gh/` | CSVs for Grasshopper: `briefs_gh.csv` (one row per site) and `reference_S*.csv` (expected rectangles) |
| `grasshopper/SURGE_wards.gh` / `.ghx` | the native Grasshopper definition |
| `grasshopper/GH_TUTORIAL.md` | lessons 1–12: build the definition yourself, with checks and common bugs |
| `grasshopper/GH_BUILD_GUIDE.md` | compact technical spec of the same definition |
| `grasshopper/*.py` | alternatives: draw from `layouts.json`, run the Python generator inside GH, Hops server |
| `web/` | the web planner (static site; `pipeline/s5_web_export.py` writes its data) |
| `mockup/SURGE_rework_mockup.pdf` | 12-page A3 layout of the final presentation |
| `data/raw/`, `data/user/` | downloads (not needed to read the results) |

## Run it

```
cd rework
python -m venv .venv && .venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip
python pipeline/s1_fetch.py all && python pipeline/s1_facilities.py && python pipeline/s1_qa.py
python pipeline/s2_run.py && python pipeline/s2_figures.py && python pipeline/s2_report.py
python pipeline/s2_scenarios.py && python pipeline/s2_scenario_figures.py
python pipeline/s3_run.py && python pipeline/s3_figures.py
python pipeline/s4_run.py && python pipeline/s4_gh_export.py
python pipeline/s5_web_export.py && node web/test/engine.test.mjs
```
Step 1 downloads several GB. The processed results of every step are committed, so you can start at any step.

## Change a parameter, see the effect

| Change | Where | Effect |
|---|---|---|
| travel limit, coverage target, MUST thresholds, SHOULD weights | `pipeline/s2_params.py` | different sites (see `data/s2/scenarios/`) |
| staff and area ratios, ward split, module size | `pipeline/s3_params.py` | different briefs |
| bay, modules per row, gaps, margins | `pipeline/s4_params.py`, or the sliders in `SURGE_wards.gh` | different layouts |

**Step 5 · Web planner.** `web/` runs the same workflow in the browser: pick one of the 936 candidate sites on the
map, set the number of confirmed patients, and get the brief, the ward layout (plan, 3D, footprint on the map) and its
rule checks. You can then adjust the layout with sliders. The browser engine is a port of steps 3–4 and is tested
against the Python results. → `web/README.md`
