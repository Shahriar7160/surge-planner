# S.U.R.G.E. web planner

A static web page (no server) that runs the S.U.R.G.E. workflow in the browser:

1. **Pick a candidate site on the map.** The dots are the 936 sites that passed all ten MUST filters in step 2,
   coloured by their SHOULD score. The page opens with no site picked; after your first pick the four optimised
   S.U.R.G.E. sites appear as large rings, so you can compare your choice with the optimiser's. The site card shows the
   score breakdown, travel time to hospital and road, and which settlements the site reaches within the patient travel
   limit (dry or rainy season, from the 2014 road network).
2. **Set the number of confirmed patients.** It starts at the modelled demand: the step 3 brief for an optimised
   site, otherwise the peak demand of the settlements it reaches, capped at one site's capacity (120 beds).
   The brief follows the step 3 ratios: wards, modules, staff, water, power, plot size and whether it fits the land.
3. **Adjust the wards.** Sliders change the kit and rules (modules per row, bay, gaps, corridor, low-risk column,
   fences, margins). The layout, its rule checks, the plan, the 3D model and the footprint on the map update live.
   *Copy CSV for Grasshopper* gives one row in the `briefs_gh.csv` format, so the same site opens in
   `grasshopper/SURGE_wards.gh`.

## How it relates to the Python pipeline and Grasshopper
- `js/engine.js` is a line-by-line port of `pipeline/s3_run.py` (brief) and `pipeline/s4_layout.py` (layout and
  checks). `test/engine.test.mjs` checks it against the committed Python results for all four sites
  (`node test/engine.test.mjs`).
- `data/` is written by `python pipeline/s5_web_export.py`: candidates with their scores and map orientation,
  the settlement patches with their modelled peak demand, travel-time matrices in `travel.json` (candidate → settlement, minutes,
  dry and rainy season) and the map layers.
- Grasshopper cannot run in a browser. The Grasshopper definition and this page apply the same rules, so they can
  be compared rectangle by rectangle (`data/s4/gh/reference_S*.csv`).

## Run locally
```
cd rework/web
python -m http.server 8000      # then open http://localhost:8000
```
(Opening `index.html` directly from disk does not work, because the browser blocks loading the data files.)

## Publish
- **GitHub Pages:** `.github/workflows/pages.yml` deploys this folder on every push to `main` or `surge` that touches
  it. One-time setup: repository *Settings → Pages → Source: GitHub Actions*.
- **Single file:** `python build_single.py` writes `dist/index.html` with all CSS and JS inlined (plus `dist/data/`).

Libraries (in `vendor/`, MIT licence): Leaflet 1.9.4, three.js r128 with OrbitControls. No map tiles: the base map is
drawn from the project's own data (prefectures, 2014 roads, settlements, health facilities).
