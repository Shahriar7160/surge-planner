# S.U.R.G.E. in Rhino 8 / Grasshopper

## Main: the native definition (no scripts)
`SURGE_wards.gh` (binary) and `SURGE_wards.ghx` (same file as readable XML) rebuild the step 4 ward generator from
built-in components only.

1. Open the file. In the **File Path** component at the top left, select `rework/data/s4/gh/briefs_gh.csv`.
2. **Value List:** pick the site (0 = S1, 1 = S2, 2 = S3, 3 = S4).
3. **Sliders:** `BAY`, `MAX_PER_ROW`, `GAP`, `FENCE_GAP`, `GREEN_COL_BAYS`, `PC` (patient corridor), `OM` (outer
   margin), `EAVE` / `RIDGE` (tent), `H` (room height).

Groups on the canvas follow the tutorial lessons: wards (5), staff entry/exit (6), patient entry and circulation (7),
safe areas (8), far end (9), services and fences (10), 3D, colours and route (11).

**Learn it:** `GH_TUTORIAL.md` builds the definition lesson by lesson. Each lesson ends with a check against S1, and
the end of the tutorial lists the bugs found while reviewing the build. **Check it:** every rectangle should match
`data/s4/gh/reference_S1.csv`.

## Alternatives (Python inside Rhino 8)
- **A · Draw the generated layouts:** paste `surge_draw_layouts.py` into a Python 3 component. Inputs: `path`
  (full path to `data/s4/layouts.json`), `site`, `tent`. Outputs: `geo`, `colour`, `name`, `zone`.
- **B · Hops:** `python grasshopper/surge_hops_server.py`, then a Hops component pointing at
  `http://127.0.0.1:5000/surge_layout`.
- **C · Python generator inside Grasshopper:** `surge_generate_native.py` imports `pipeline/s4_layout.py`. Inputs:
  `repo` (path to the `rework` folder), `site`, `per_row`, `bay`, `tent`.
