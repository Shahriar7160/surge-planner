# S.U.R.G.E. — native Grasshopper build guide (step 4: automatic ward design)

> **Building it yourself? Start with `GH_TUTORIAL.md`** — the same thing as 12 hands-on lessons. This file is the compact spec (e.g. for Codex).

This guide rebuilds the ward-layout generator (`pipeline/s4_layout.py`) as a **native Grasshopper definition**: only built-in
components, **no Python / C# script components**. Every design rule is its own labelled group, so the logic can be read on
the canvas. The Python version stays as the reference. Your definition must reproduce its rectangles exactly
(`data/s4/gh/reference_S1.csv` … `reference_S4.csv`).

Target: **Rhino 8, Grasshopper 1.0**, metres.

---

## 0 · Notes for the builder (human or Codex)

- **Native only.** Allowed: components from the Params, Maths, Sets, Vector, Curve, Surface, Transform and Display tabs.
  Not allowed: GhPython, Python 3 Script, C# Script, VB Script, Hops or any plug-in.
- **Group everything.** Create one Grasshopper *Group* per section below, named exactly as the headings (e.g. `D · Ward modules`).
  Use a *Scribble* or *Panel* at the top of each group with the one-line rule it encodes (given in each section).
- **Wires left to right.** Inputs (group A) on the far left; preview/bake (M) and checks (N) on the far right.
- **Name every important slider and panel** (right-click → name) with the variable names used here (`BAY`, `x_red` …).
- **How to deliver the file:** a `.gh` file written by hand without opening Grasshopper usually fails to load.
  Two reliable routes:
  1. A person builds it following this guide (about 2–3 hours).
  2. A **Rhino 8 script that builds the definition**: it instantiates native components through the Grasshopper SDK
     (`Grasshopper.Instances.ComponentServer`), places them, connects wires, groups them and saves `surge_wards.gh`.
     The saved definition still contains only native components; the script is just the builder.
- **Done means:** for S1–S4, every rectangle matches the reference CSV to 0.01 m (group Z shows no mismatches), and
  group N shows the values in the table in section N.

### Coordinate system
Local plan in metres on the World XY plane. **Origin (0, 0) = bottom-left corner of the low-risk column.**
The road is below (negative Y), and patient flow runs upward (+Y). The reference image is `data/s4/gh/fig_12_groups.png`.

### Data files (in `rework/data/s4/gh/`)
- `briefs_gh.csv`: header line plus one line per site. Read with **Read File**; each line is split with **Text Split** at `,`.
- `reference_S1.csv` … `reference_S4.csv`: expected rectangles, `name,zone,kind,x,y,w,h,group`.
- `reference_checks.csv`: expected check values.

Column index of `briefs_gh.csv` after splitting a line (0-based):

| idx | column | idx | column | idx | column |
|---|---|---|---|---|---|
| 0 | site_id | 9 | area_morgue | 18 | area_loading_zone |
| 1 | near | 10 | area_incinerator_waste | 19 | area_staff_dormitory |
| 2 | modules_suspect | 11 | area_admin_data | 20 | area_burial_area |
| 3 | modules_probable | 12 | area_lab | 21 | rotation_deg |
| 4 | modules_confirmed | 13 | area_pharmacy | 22 | mirrored (0/1) |
| 5 | beds_total | 14 | area_stores | 23 | lon |
| 6 | area_triage | 15 | area_staff_rest | 24 | lat |
| 7 | area_family_visiting | 16 | area_water_treatment | | |
| 8 | area_laundry | 17 | area_generator | | |

### The one reusable rule: "width in whole bays"
Many spaces are sized by this rule (it is `_bays(area, depth)` in Python):

```
bays(area, depth) = max(1, ceiling(area / depth / BAY)) × BAY
```

Native recipe, used many times below. Make it once, check it, then copy-paste it; or make it a **Cluster** named `Bays`
with inputs `area`, `depth`, `BAY` and output `width`, since clusters are native:
1. **Division** (Maths › Operators) `area ÷ depth` →
2. **Division** `÷ BAY` →
3. **Round** (Maths › Util) → use the **Ceiling** output →
4. **Maximum** (Maths › Util) with `1` →
5. **Multiplication** `× BAY` → `width`.

Check: `bays(116.4, 6)` = **24**, `bays(30, 6)` = **6**, `bays(334.5, 12)` = **30**.

---

## A · Inputs
*Rule: every dimension of the kit of parts is a slider; nothing is typed inside formulas.*

| Name | Component | Value / range |
|---|---|---|
| `briefs_file` | Params › Input › **File Path** (or a **Panel** with the full path) | `…\rework\data\s4\gh\briefs_gh.csv` |
| `site` | Params › Input › **Value List** | S1 → 1, S2 → 2, S3 → 3, S4 → 4 (the value is the **line index** in the CSV) |
| `BAY` | Number Slider | 6.0 (4.8–7.2) |
| `MODULE_W` | Number Slider | 6.0 |
| `MODULE_D` | Number Slider | 18.0 |
| `MODULE_H` | Number Slider | 2.8 (eave) |
| `MODULE_RIDGE` | Number Slider | 4.6 |
| `SERVICE_H` | Number Slider | 3.0 |
| `MAX_PER_ROW` | Number Slider (integer) | 5 (2–8) |
| `ROW_GAP` | Number Slider | 3.0 |
| `PATIENT_CORRIDOR` (`PC`) | Number Slider | 3.0 |
| `GREEN_COL_BAYS` | Number Slider (integer) | 2 |
| `FENCE_GAP` | Number Slider | 1.0 |
| `OUTER_MARGIN` (`OM`) | Number Slider | 6.0 |
| `MAX_STAFF_WALK` | Number Slider | 45 |
| `BEDS_PER_MODULE` | Number Slider (integer) | 12 |

## B · Read the brief
*Rule: the design starts from the data. Every number comes from step 3's brief for the chosen site.*

1. **Read File** (Params › Input) ← `briefs_file`. Output: list of lines.
2. **List Item** ← lines, index = `site`. → one line of text.
3. **Text Split** (Sets › Text) with separator `,` → list of 25 fields.
4. **List Item** (zoom in and use ⊕ to add outputs, or use one List Item per value) to pull out these values, then
   pass each through a **Number** param (Params › Primitive) and name it:

| Name | Field idx | S1 value |
|---|---|---|
| `n_suspect` | 2 | 5 |
| `n_probable` | 3 | 3 |
| `n_confirmed` | 4 | 10 |
| `beds_total` | 5 | 216 |
| `a_triage` | 6 | 116.4 |
| `a_family` | 7 | 30 |
| `a_laundry` | 8 | 106.4 |
| `a_morgue` | 9 | 72 |
| `a_incinerator` | 10 | 46.6 |
| `a_admin`, `a_lab`, `a_pharmacy`, `a_stores`, `a_staff_rest` | 11–15 | 41.6, 40, 84.8, 138, 334.5 |
| `a_water`, `a_generator`, `a_loading` | 16–18 | 40, 25, 150 |
| `a_dormitory`, `a_burial` | 19–20 | 1206, 1944 |
| `rotation_deg`, `mirrored` | 21–22 | 37.0, 0 |

## C · Derived dimensions
*Rule: the column positions follow from the kit of parts: low-risk column, fence gap, staff interface, wards, corridor.*

Use **Multiplication / Addition / Maximum / Minimum** components (or one **Expression** component per value; Expression
is native and allowed). S1 results in brackets:

| Name | Formula | S1 |
|---|---|---|
| `green_w` | `GREEN_COL_BAYS × BAY` | 12 |
| `x_red` | `green_w + FENCE_GAP` | 13 |
| `x_mod` | `x_red + BAY` | 19 |
| `n_row_max` | `min(MAX_PER_ROW, max(n_suspect, n_probable, n_confirmed))` | 5 |
| `row_len` | `n_row_max × MODULE_W` | 30 |
| `x_corr` | `x_mod + row_len` | 49 |
| `row_pitch` | `MODULE_D + ROW_GAP` | 21 |
| `Y0` (first row) | `BAY + ROW_GAP` | 9 |

## D · Ward modules
*Rule: wards in the order suspect → probable → confirmed; each ward fills rows of at most `n_row_max` modules; a ward
always starts a new row.* There is no loop: each module's row and column follow from its index.

1. **Merge** (Sets › Tree) `n_suspect`, `n_probable`, `n_confirmed` → list `n_w` = [5, 3, 10].
2. `rows_w` = **Division** `n_w ÷ n_row_max` → **Round** (Ceiling) → [1, 1, 2].
3. **Mass Addition** (Maths › Operators) on `rows_w`:
   - `Result` → `rows_total` = 4.
   - `Partial Results` [1, 2, 4] **minus** `rows_w` → `row_offset_w` = [0, 1, 2] (first row of each ward).
4. **Graft** `n_w` and `row_offset_w` (right-click the input → Graft) so each ward is its own branch {0}, {1}, {2}.
5. **Series** (Sets › Sequence) start 0, step 1, count = grafted `n_w` → `j` per branch (0…4 | 0…2 | 0…9).
6. **Integer Division** (Maths › Operators) `j ÷ n_row_max` → `row_in_ward`.
   **Modulus** (Maths › Operators) `j mod n_row_max` → `col`.
7. `r` = `row_offset_w + row_in_ward` (the grafted offset matches each branch).
8. `x` = `x_mod + col × MODULE_W`; `y` = `Y0 + r × row_pitch`.
9. **Construct Point** (x, y, 0) → corner A; **Construct Point** (x + MODULE_W, y + MODULE_D, 0) → corner B.
10. **Rectangle 2Pt** (Curve › Primitive), plane = World XY → `ward_modules` (tree: {0} suspect, {1} probable, {2} confirmed).

Check S1: 18 rectangles. suspect_M1 corner (19, 9); confirmed_M6 corner (19, 72); confirmed_M10 corner (43, 72).

## E · Staff interface per row (donning · PPE store · doffing)
*Rule: every ward row starts with a staff interface on the low-risk side. Staff enter red through donning and leave through
doffing. These are the only parts allowed to touch both green and red.*

1. **Series** start 0, step 1, count `rows_total` → `r` = [0, 1, 2, 3].
2. `y_r` = `Y0 + r × row_pitch` → [9, 30, 51, 72].
3. Three **Rectangle 2Pt**, all `BAY × BAY` wide, at `x = x_red`:
   - `donning`: (x_red, y_r) → (x_red + BAY, y_r + BAY), zone **green**
   - `ppe_store`: (x_red, y_r + BAY) → (x_red + BAY, y_r + 2·BAY), zone **green**
   - `doffing`: (x_red, y_r + 2·BAY) → (x_red + BAY, y_r + 3·BAY), zone **amber**

Check S1 row 0: donning (13, 9), store (13, 15), doffing (13, 21).

## F · Triage, family visiting, patient corridor
*Rule: patients enter only through triage at the road side, then move along one one-way corridor beside the ward rows.*

| Part | Corner A | Corner B | Zone | S1 |
|---|---|---|---|---|
| `triage` | (x_red, 0) | (x_red + w_t, BAY) | amber | w_t = `max(bays(a_triage, BAY), 2·BAY)` = 24 → (13,0)–(37,6) |
| `family_visiting` | (x_red + w_t, 0) | (+ `bays(a_family, BAY)`, BAY) | amber | (37,0)–(43,6) |
| `patient_corridor` | (x_corr, BAY) | (x_corr + PC, `yt` − ROW_GAP) | red | (49,6)–(52,90) |

`yt` = `Y0 + rows_total × row_pitch` (first y above the last ward row): S1 = **93**. Define it here and reuse it in G, H, J, K.

## G · Low-risk column
*Rule: admin, lab, pharmacy, stores and staff rest are stacked in one column, kept behind the double fence.*

1. **Merge** the five areas in this order: `a_admin, a_lab, a_pharmacy, a_stores, a_staff_rest`.
2. Heights `h` = `bays(area, depth = green_w)` → [6, 6, 12, 12, 30].
3. **Mass Addition** on `h`: `Partial Results` − `h` → `y_g` = [0, 6, 12, 24, 36]; `Result` → `gy_total` = 66.
4. **Rectangle 2Pt** (0, y_g) → (green_w, y_g + h), zone **green**.
5. `top` = `max(yt + BAY, gy_total)` → S1 **99**.

## H · Far end (discharge, laundry, morgue, incinerator)
*Rule: the patient route ends at discharge or morgue. Waste and the incinerator are last, downwind.*

| Part | x | width | Zone | S1 |
|---|---|---|---|---|
| `patient_discharge` | `x_red` | `BAY` | amber | (13,93) w 6 |
| `laundry` | `x_red + BAY` | `w_l = bays(a_laundry, BAY)` | amber | (19,93) w 18 |
| `morgue` | `mx = max(x_corr + PC − w_m, x_red + BAY + w_l + FENCE_GAP)` | `w_m = bays(a_morgue, BAY)` | red | (40,93) w 12 |
| `incinerator` | `max(x_corr + PC, mx + w_m) + FENCE_GAP` | `bays(a_incinerator, BAY)` | red | (53,93) w 12 |

All four: y from `yt` to `yt + BAY`. The `max(...)` in `mx` stops the morgue overlapping the laundry when rows are short.
That is a real collision the Python checks caught at `MAX_PER_ROW` = 3.

## I · Services, dormitory, burial (outside the clinical fence)
*Rule: water, power and deliveries sit along the road outside the fence; the dormitory and burial area sit beside the
compound.*

`sy = −OM − BAY` (S1: −12).

| Part | Corner A | Size (w × h) | S1 |
|---|---|---|---|
| `water_treatment` | (0, sy) | `w_w = bays(a_water, BAY)` × BAY | (0,−12) 12×6 |
| `generator` | (w_w + BAY, sy) | `w_g = bays(a_generator, BAY)` × BAY | (18,−12) 6×6 |
| `loading_zone` | (w_w + BAY + w_g + BAY, sy − BAY) | `bays(a_loading, 2·BAY)` × 2·BAY | (30,−18) 18×12 |
| `staff_dormitory` | (right + 2·OM, 0) | `bays(a_dormitory, 2·BAY)` × 2·BAY | (77,0) 102×12 |
| `burial_area` | (right + 2·OM, top − 3·BAY) | `bays(max(a_burial, 36), 3·BAY)` × 3·BAY | (77,81) 108×18 |

`right` = the largest X of every rectangle from D–H plus water, generator and loading.
Natively: **Merge** those curves → **Bounding Box** (right-click → *Union box*) → **Deconstruct Box** → X domain →
**Deconstruct Domain** → End. S1 = **65**.

## J · Fences
*Rule: a double fence (gap `FENCE_GAP`) around the compound, and an inner fence around the red zone.*

1. **Outer fence:** **Merge** all clinical rectangles (groups D, E, F, G, H; *not* I) → **Bounding Box** (Union box) →
   take its base rectangle (Deconstruct Box → domains → **Rectangle** from X/Y domains) → **Offset Curve** (Curve › Util)
   by `OM`, corner type *Sharp*. S1: from (−6, −6) to (71, 105) → **77 × 111 m**.
   Second line: **Offset Curve** of that by `FENCE_GAP`.
2. **Inner red fence:** Rectangle 2Pt from (`x_red − FENCE_GAP/2`, `BAY + ROW_GAP/2`) to (`x1 + FENCE_GAP/2`, `top`), where
   `x1` = the X end of the clinical bounding box *before* the offset. S1: (12.5, 7.5)–(65.5, 99).

## K · Patient flow
*Rule: one route, one direction.*

Points, merged in this order, then **PolyLine** (Curve › Spline), not closed:
1. (`x_red + BAY`, `BAY/2`): inside triage → S1 (19, 3)
2. (`x_corr + PC/2`, `BAY/2`): along the triage front to the corridor → (50.5, 3)
3. for every row `r`: (`x_corr + PC/2`, `y_r + MODULE_D/2`) → (50.5, 18), (50.5, 39), (50.5, 60), (50.5, 81)
4. (`x_corr + PC/2`, `yt + BAY/2`) → (50.5, 96)

**Length** (Curve › Analysis) → `patient_path` = **124.5 m** for S1.

## L · 3D massing (kit of parts)
*Rule: ward modules are the 2015 folded tent; everything else is a simple box.*

1. **Folded tent** (per ward module rectangle, keep the tree from D):
   - **Deconstruct Rectangle** or **Explode**, then take the corner (x, y) and use `MODULE_W`.
   - Five points in the module's front plane (y = module y):
     (x, y, 0) · (x, y, MODULE_H) · (x + W/2, y, MODULE_RIDGE) · (x + W, y, MODULE_H) · (x + W, y, 0)
   - **PolyLine** with *Closed* = True → **Boundary Surfaces** → **Extrude** (Surface › Freeform) along
     **Unit Y** × `MODULE_D` → closed solid.
   - *(optional origami folds)* **Divide Curve** on the two eave lines and the ridge (6 segments) and **Line** between
     matching points, to draw the folds.
2. **Boxes** for every other rectangle: **Boundary Surfaces** → **Extrude** along **Unit Z** × `SERVICE_H`
   (patient corridor: 0.2).

## M · Colours, preview, labels
*Rule: colour = risk zone, so the plan reads as red / amber / green at a glance.*

Use one **Custom Preview** (Display › Preview) per zone, each fed by a **Colour Swatch** (Params › Input):

| Zone | Parts | Colour (R,G,B) |
|---|---|---|
| red | patient corridor, morgue, incinerator | 227, 73, 72 |
| ward · suspect / probable / confirmed | D branches {0} {1} {2} | 246,185,178 / 238,139,129 / 184,48,47 |
| amber | triage, family, doffing, discharge, laundry | 237, 161, 0 |
| green | donning, PPE store, low-risk column | 27, 175, 122 |
| service | water, generator, loading, dormitory, burial | 138, 136, 127 |

Labels: **Area** (Surface › Analysis) of each rectangle → Centroid → **Text Tag 3D** (Display › Dimensions) with the
part name, size 1.2.

## N · Checks (the design must prove itself)
*Rule: the layout is only valid if it passes every check.* Show each result in a **Panel**; use **Equality** /
**Larger Than** for pass/fail booleans.

| Check | Native recipe | S1 | S2 | S3 | S4 |
|---|---|---|---|---|---|
| Beds match the brief | **List Length** of the flattened `ward_modules` × `BEDS_PER_MODULE` = `beds_total` (**Equality**) | 216 ✓ | 108 ✓ | 84 ✓ | 84 ✓ |
| Longest staff walk ≤ `MAX_STAFF_WALK` | `x_mod + row_len − (x_red − FENCE_GAP/2 + BAY)` | 30.5 | 30.5 | 24.5 | 24.5 |
| Patient path | Length of K | 124.5 | 103.5 | 97.5 | 97.5 |
| Fenced size | Outer fence → **Deconstruct Rectangle** → X and Y lengths | 77 × 111 | 71 × 90 | 65 × 90 | 65 × 90 |
| No overlaps | **Area** of every clinical rectangle → **Mass Addition** = Area of their **Region Union** (difference < 0.01) | ✓ | ✓ | ✓ | ✓ |
| No red touches green (except via E) | **Offset Curve** the group-G rectangles outward by 0.05 → **Region Intersection** with the red parts (D modules, corridor, morgue, incinerator) → result count = 0 | ✓ | ✓ | ✓ | ✓ |

Try `MAX_PER_ROW` = 8 on S1: the staff-walk check must fail (48.5 > 45). That shows the checks working.

## O · Map placement (optional)
*Rule: the plan faces the nearest road; it is mirrored if needed so the incinerator is downwind.*

Centre = centre of the outer fence. If `mirrored` = 1: **Mirror** (Transform › Euclidean) across the YZ plane through the
centre. Then **Rotate** (Transform › Euclidean) by `rotation_deg` (convert with **Radians**) about the centre. The
rotation and mirror values were computed in Python from the road network (`footprints.geojson` is the GIS result).

## Z · Verification overlay (build this early)
*Rule: the native definition must match the Python reference exactly.*

1. **Read File** `reference_<site>.csv` (build the file name from `site` with **Concatenate**) → **Cull Index** 0 (the header).
2. **Text Split** `,` → **List Item** x (3), y (4), w (5), h (6) → **Rectangle 2Pt** (x, y)–(x+w, y+h).
3. **Custom Preview** in thin black (or a **Curve** param with preview on) to overlay your geometry.
4. Automatic comparison: **Area** centroids of both sets → **Closest Point** (Vector › Point) from reference centroids to
   your centroids → distances → **Bounds**; the max distance should be ≈ 0.
   Also **List Length** of both sets should be equal (S1: 47 parts in total, including dormitory and burial).

---

### Reading order for a reviewer
A (inputs) → B (data) → C (positions) → D/E (wards and staff interface) → F (patient entry) → G (low-risk column) →
H (far end) → I (services) → J (fences) → K (flow) → L (3D) → M (colour) → N (checks) → Z (match with Python).
