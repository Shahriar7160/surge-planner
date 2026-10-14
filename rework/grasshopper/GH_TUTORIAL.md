# Build the S.U.R.G.E. ward generator in Grasshopper — step by step

This is a hands-on tutorial. Each lesson builds **one small piece you can see** in Rhino, and ends with a check against
the numbers for site **S1**. Do the lessons in order; each takes 10–20 minutes.
The finished definition is `SURGE_wards.gh` / `SURGE_wards.ghx` in this folder. Open it next to this tutorial to compare.
(`GH_BUILD_GUIDE.md` is the compact technical spec of the same thing. You don't need it for this tutorial.)

---

## Part 1 — Where the numbers come from

Before drawing anything, this is the chain that produces every number you will feed into Grasshopper:

```
outbreak model (step 2)  →  peak confirmed beds at the site      S1: 120 beds
ward split (step 3)      →  suspect / probable / confirmed beds  50 / 30 / 120
round up to 12-bed modules                                       5 / 3 / 10 modules = 216 beds
ratios (step 3)          →  area of every support space          triage 116.4 m², lab 40 m², …
```

**What drives the areas: the number of beds.** Every space in `pipeline/s3_params.py` has one line with three numbers:

```
area  =  fixed  +  per_bed × beds  +  per_ward × number_of_wards
```

| Space | fixed | per_bed | S1 calculation (216 beds) | Area |
|---|---|---|---|---|
| triage | 30 | 0.4 | 30 + 0.4 × 216 | **116.4** |
| laundry | 20 | 0.4 | 20 + 0.4 × 216 | **106.4** |
| pharmacy | 20 | 0.3 | 20 + 0.3 × 216 | **84.8** |
| stores | 30 | 0.5 | 30 + 0.5 × 216 | **138** |
| admin | 20 | 0.1 | 20 + 0.1 × 216 | **41.6** |
| incinerator | 25 | 0.1 | 25 + 0.1 × 216 | **46.6** |
| lab, family visiting, water, generator, loading | 40, 30, 40, 25, 150 | 0 | fixed size | **40, 30, 40, 25, 150** |

Four spaces are driven by something other than beds:

| Space | Driven by | S1 calculation | Area |
|---|---|---|---|
| morgue | confirmed beds: 1 place per 10 beds, 6 m² each | 120 ÷ 10 = 12 places × 6 | **72** |
| staff rest | staff on shift × 1.5 m² | 223 people × 1.5 | **334.5** |
| staff dormitory | staff living on site (30%) × 6 m² | 201 × 6 | **1,206** |
| burial area | expected deaths in 90 days × 3 m² | 12 admissions/day × 90 × 60% fatality = 648 × 3 | **1,944** |

Staff numbers come from beds too (e.g. 2 clinical staff per confirmed bed), which is why staff rest grows with the wards.

So: **change the outbreak → beds change → every area changes → the layout changes.** The CSV file
`data/s4/gh/briefs_gh.csv` simply carries these results into Grasshopper. To change a ratio, edit
`pipeline/s3_params.py` and rerun `python pipeline/s3_run.py`, then `python pipeline/s4_run.py` and
`python pipeline/s4_gh_export.py`.

*(Lesson 12 shows how to compute these areas inside Grasshopper instead, so the ratios become sliders.)*

---

## Part 2 — Grasshopper basics you will use

- **Add a component:** double-click on empty canvas, type its name (e.g. `Rectangle 2Pt`) and press Enter.
  That is faster than hunting through tabs.
- **See a value:** connect any output to a **Panel** (type `Panel`). Do this all the time while building.
- **Number Slider:** type `Number Slider`. Double-click its name to set name, min, max and value.
  Right-click → *Integers* for whole numbers.
- **Expression:** type `Expression`. It computes a formula. Zoom in until you see ⊕ / ⊖ on the left side to add inputs.
  Right-click an input → rename it (e.g. `W`). Double-click the component to type the formula, e.g. `x + W`.
  Expression is a native component (it is not a script).
- **Group:** select components → Ctrl+G. Right-click the group to name it. One group per lesson.
- **Lists:** most components accept lists. If you give a component a list of 5 numbers, it runs 5 times
  and outputs 5 results. This replaces the "for loop" of Python.

**Coordinates:** everything is drawn flat on the XY plane in metres.
**(0, 0) is the bottom-left corner of the low-risk column**, the road is at the bottom and patients walk upward (+Y).
The finished target is `data/s4/gh/fig_12_groups.png` and `data/s4/fig_9_plans.png` (S1).

---

## Lesson 1 — One ward module (the kit of parts)
**Goal:** a single 6 × 18 m rectangle = one 12-bed ward module.

1. Two **Number Sliders**: `W` = 6, `D` = 18.
2. **Construct Point** with X = 0, Y = 0 → corner A.
3. **Construct Point** with X ← `W`, Y ← `D` → corner B.
4. **Rectangle 2Pt**: connect A and B. Leave Plane empty (it defaults to World XY).

✅ **Check:** one rectangle 6 wide and 18 tall at the origin. Move `W`: it gets wider.

## Lesson 2 — A row of modules
**Goal:** 5 modules side by side.

1. Slider `n` = 5 (integer).
2. **Series**: Start 0, Step 1, Count ← `n` → outputs `0, 1, 2, 3, 4` (call this `j`).
3. **Expression** `j * W` (inputs `j`, `W`) → x positions `0, 6, 12, 18, 24`.
4. **Construct Point** (X ← x, Y = 0) → corners A. **Expression** `j * W + W` → **Construct Point** (X, Y ← `D`) → corners B.
5. **Rectangle 2Pt** (A, B) → 5 rectangles.

✅ **Check:** 5 touching rectangles, 30 m long in total.

## Lesson 3 — Rows that wrap (the key trick)
**Goal:** 10 modules arranged in rows of at most 5. This replaces a loop with arithmetic.

Each module has an index `j` = 0…9. For each one:
- **column** = `j mod per_row` (the remainder: 0,1,2,3,4,0,1,2,3,4)
- **row** = `j ÷ per_row` rounded down (0,0,0,0,0,1,1,1,1,1)

1. Slider `per_row` = 5 (integer), set `n` = 10.
2. **Modulus** (type `Modulus`): A ← `j`, B ← `per_row` → `col`.
3. **Integer Division** (type `Integer Division`): A ← `j`, B ← `per_row` → `row`.
4. Slider `GAP` = 3 (the corridor between rows).
5. **Expression** `col * W` → x. **Expression** `row * (D + GAP)` → y (inputs `row`, `D`, `GAP`).
6. Corners: A = (x, y), B = (x + W, y + D) → **Rectangle 2Pt**.

✅ **Check:** two rows of 5, the second row starting at y = 21. Set `per_row` = 3: you get rows of 3, 3, 3, 1.

## Lesson 4 — Read the site's brief from the CSV
**Goal:** replace hand-typed numbers with the data.

1. **File Path** (type `File Path`) → right-click → *Select one existing file* → `rework\data\s4\gh\briefs_gh.csv`.
2. **Read File** ← File Path → a list of lines (line 0 = column names, line 1 = S1 …).
3. **Value List** (type `Value List`): double-click it and edit the items to
   `S1 = 1`, `S2 = 2`, `S3 = 3`, `S4 = 4`. Name it `site`.
4. **List Item**: L ← lines, i ← `site` → the S1 line.
5. **Text Split**: T ← the line, C = `,` → 25 values.
6. One **List Item** per value you need (i = field number), each into a **Number** param that you name:

| Name | i | S1 |
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
| `a_admin` · `a_lab` · `a_pharmacy` · `a_stores` · `a_rest` | 11 · 12 · 13 · 14 · 15 | 41.6 · 40 · 84.8 · 138 · 334.5 |
| `a_water` · `a_generator` · `a_loading` | 16 · 17 · 18 | 40 · 25 · 150 |
| `a_dorm` · `a_burial` | 19 · 20 | 1206 · 1944 |

✅ **Check:** a Panel on `n_confirmed` shows 10. Switch `site` to S3: it shows 4.

⚠️ **Off-by-one trap.** The index depends on what the List Item reads. Read File gives the header at 0, so S1 = 1.
If you instead feed the List Item only the four site lines (e.g. from List Item outputs +1…+4), S1 is at **0**, so the
Value List must be `S1 = 0 … S4 = 3`. If the confirmed modules read 5 when you expect 10, you are on S2.

**Tip:** whenever a value is used in many places, put a **Number** param (or a **Relay**) after it and name it
(`BAY`, `x_red`, `yt` …). Then you wire from one clearly named node and never wire to an old copy by mistake.


## Lesson 5 — The three wards in their places
**Goal:** suspect rows, then probable rows, then confirmed rows, starting at the right place in the plan.

**Positions of the main columns.** Add sliders `BAY` = 6, `FENCE_GAP` = 1, `GREEN_COL_BAYS` = 2 (integer), `MAX_PER_ROW` = 5,
then one **Expression** (or Addition / Multiplication) for each:

| Name | Expression | S1 |
|---|---|---|
| `green_w` | `GREEN_COL_BAYS * BAY` | 12 |
| `x_red` | `green_w + FENCE_GAP` | 13 |
| `x_mod` | `x_red + BAY` (modules start after the staff column) | 19 |
| `per_row` | `Min(MAX_PER_ROW, Max(n_suspect, Max(n_probable, n_confirmed)))` | 5 |
| `Y0` | `BAY + GAP` (first row sits above triage) | 9 |
| `pitch` | `D + GAP` | 21 |

⚠️ From now on **`per_row` means this Expression**, not the Lesson 3 slider. Delete the Lesson 3 `per_row` slider so
nothing can stay wired to it (that was the most common bug: the corridor moved with MAX_PER_ROW but the wards did not).

**Rows per ward**, using **Division** `n / per_row` → **Round** → *Ceiling* output (rounds up):

| | n | rows | starts at row |
|---|---|---|---|
| suspect | 5 | 1 | 0 |
| probable | 3 | 1 | rows_s = 1 |
| confirmed | 10 | 2 | rows_s + rows_p = 2 |
| **total rows** (Mass Addition of the three) | | **4** | |

**Build each ward by copying Lesson 3's group three times** (Ctrl+C / Ctrl+V).
In Lesson 3 the rows started at the origin. In the real plan they must sit **right of the low-risk column and staff
rooms** (x_mod) and **above triage** (Y0), and each ward must start **above the rows of the wards before it**
(start_row). So in each copy you replace the two Expressions that make **corner A** (the bottom-left corner of each
module rectangle):

```
x = x_mod + col * W                    (was: col * W)
y = Y0 + (start_row + row) * pitch     (was: row * (D + GAP))
```
Corner B stays (x + W, y + D). In each copy change three things:

| Copy | Series Count `n` ← | `start_row` (extra input on the y Expression) | rows at y = |
|---|---|---|---|
| Suspect | `n_suspect` (5) | 0 | 9 |
| Probable | `n_probable` (3) | `rows_s` (1) | 30 |
| Confirmed | `n_confirmed` (10) | `rows_s + rows_p` (2) | 51, 72 |

**What is `n`?** It goes into the **Count** input of **Series** (Start 0, Step 1). Series then gives one index `j` per
module: suspect 0…4, probable 0…2, confirmed 0…9. Each copy's `j` goes into its own **Modulus** (→ col) and
**Integer Division** (→ row), both with B ← `per_row`.

Worked example, confirmed module no. 7 (j = 6): col = 6 mod 5 = 1, row = 6 ÷ 5 = 1 →
x = 19 + 1 × 6 = 25, y = 9 + (2 + 1) × 21 = 72 → rectangle (25, 72)–(31, 90) = `confirmed_M7` in `reference_S1.csv`.

✅ **Check S1:** suspect row at y = 9 (5 modules), probable at y = 30 (3), confirmed at y = 51 and y = 72 (5 + 5).
First module of every row starts at x = 19. The last module (col 4) starts at x = 43 and ends at x = 43 + 6 = 49.

*Shortcut used in `SURGE_wards.gh`:* instead of three copies, one **Series** whose Count input is **grafted** and fed
the three `n` values gives three branches (one per ward); `start_row` comes from a **Merge** of 0 / rows_s /
rows_s + rows_p, also grafted, so each branch gets its own start row.

## Lesson 6 — Staff entry/exit at the start of every row
**Goal:** staff never walk into a ward directly; every row starts with **donning** (dress), a **PPE store**, and **doffing**
(undress and shower).

1. **Series** start 0, step 1, count ← total rows (4) → `r`.
2. **Expression** `Y0 + r * pitch` → **`y_r` = 9, 30, 51, 72** (the bottom of each ward row). Put a Number param after it
   named `y_r`: Lesson 11 uses it again.
3. Three squares of `BAY × BAY` at x = `x_red`:
   - donning: from (x_red, y_r) to (x_red + BAY, y_r + BAY)
   - PPE store: from (x_red, y_r + BAY) to (x_red + BAY, y_r + 2·BAY)
   - doffing: from (x_red, y_r + 2·BAY) to (x_red + BAY, y_r + 3·BAY)

✅ **Check:** 12 small squares in a column at x = 13 to 19, each set of three as tall as a module row.
Set MAX_PER_ROW = 3: `y_r` becomes 7 values (9 … 135). If it stays at 4, the Series Count is not wired to total rows.

## Lesson 7 — How patients enter and move
**Goal:** one entrance (triage), the family visiting room beside it, and one one-way corridor.

```
 y=90  ┌────────── module rows (Lesson 5) ──────────┐┌──┐
       │ confirmed  y=72                             ││  │
       │ confirmed  y=51                             ││co│  patient corridor
       │ probable   y=30                             ││rr│  x 49→52, y 6→90
       │ suspect    y=9                              ││  │
 y=6   └─────────────────────────────────────────────┘└──┘
 y=0   │ triage 13→37        │family 37→43│
       x=13                  x=37         x=43      x=49 x=52
```
A patient comes in from the road at the bottom, enters triage, walks right along the triage front to the corridor,
goes up it, and turns into their ward row. Each row opens onto the corridor at its right end, which is why the corridor
sits at x = 49, where the rows end.

### Step 0: the "whole bays" rule
The kit is built from 6 m bays, so a room can't be 19.4 m wide. Its width must be a whole number of bays:
```
width = Max(1, Ceiling(a / d / BAY)) * BAY
```
- `a / d` = area ÷ depth = the width the room would need if any width were allowed.
- `/ BAY` = how many bays that is.
- `Ceiling` rounds **up**, so the room is never smaller than its brief.
- `* BAY` turns bays back into metres. `Max(1, …)`: at least one bay.

Build it once as an **Expression** with inputs `a`, `d`, `BAY`, test it, and copy it for every room in Lessons 7–10.
Wire `d` ← **BAY** (not a separate slider), so changing the bay changes everything.

### Step 1: Triage
Area 116.4 m² (CSV field 6), depth one bay (6):
- 116.4 ÷ 6 = 19.4 m → ÷ 6 = 3.2 bays → round up → 4 bays → **24 m**.
- `w_t = Max(bays(a_triage), 2 * BAY)` = Max(24, 12) = 24. The second term means triage is never narrower than 2 bays.
  (If you build `2 * BAY` with a Multiplication, make sure **both** inputs are set: A = BAY, B = 2. An empty input is
  silently ignored and you get just BAY.)
- Rectangle from (x_red, 0) = (13, 0) to (x_red + w_t, BAY) = (37, 6).

### Step 2: Family visiting
A rectangle needs **how big** (width × depth) and **where** (its bottom-left corner).
1. **Depth is fixed:** every room in the bottom strip is one bay deep = **6 m** (the first 6 in `30 / 6 / 6`).
2. **Width from the area:** the brief says **30 m²** (field 7). Area = width × depth, so width = 30 ÷ 6 = **5 m**.
3. **Snap to whole bays:** 5 ÷ 6 = 0.83 bays (the second 6 is the bay size) → round up → 1 bay = **6 m**.
   So `30 / 6 / 6` means `area ÷ depth ÷ bay`. The room is 36 m², a bit more than asked, never less.
4. **Where:** right next to triage, which runs from 13 to 37 → x = `x_red + w_t` = **37**, y = **0**.
5. **Draw:** corner A = (37, 0), corner B = (37 + 6, 0 + 6) = (43, 6).

In Grasshopper: List Item (i = 7) → bays Expression (a ← a_family, d ← BAY) → `w_f`; Expression `x_red + w_t` → `x_f`;
Construct Point (x_f, 0) and (x_f + w_f, BAY) → Rectangle 2Pt.
Test: put 40 in a Panel instead of `a_family` → 40 / 6 / 6 = 1.1 → 2 bays → the room jumps to 12 m (37 → 49).

### Step 3: Patient corridor
New slider `PC` = 3 (corridor width).
- `x_corr = x_mod + per_row * W` = 19 + 5 × 6 = **49** (the right edge of the module rows).
- `yt = Y0 + total_rows * pitch` = 9 + 4 × 21 = **93** (just above the last row; Lesson 9 starts here).
- Rectangle from (x_corr, BAY) = (49, 6) to (x_corr + PC, yt − GAP) = (52, 90).

✅ **Check** against `reference_S1.csv`: triage (13, 0, 24 × 6), family (37, 0, 6 × 6), corridor (49, 6, 3 × 84).
Set MAX_PER_ROW = 3: `x_corr` moves to 37 and the corridor follows the rows.

## Lesson 8 — The low-risk column (stacked rooms)
**Goal:** admin, lab, pharmacy, stores and staff rest stacked **on top of each other** in one column on the far left.
This is the green zone: staff are here without PPE, so it sits outside the red fence (the 1 m gap at x = 12–13).

```
 y=66 ┌────────────┐
      │ staff rest │  30
 y=36 ├────────────┤
      │ stores     │  12
 y=24 ├────────────┤
      │ pharmacy   │  12
 y=12 ├────────────┤
      │ lab        │  6
 y=6  ├────────────┤
      │ admin      │  6
 y=0  └────────────┘
      x=0        x=12 | x=13 → red zone
```
In Lesson 7 rooms sat **side by side**, so area decided **width**. Here they stack, so the column width is fixed and the
area decides each room's **height**.

1. **Width is fixed:** `green_w` = 2 bays = **12 m** (from Lesson 5).
2. **Height:** the same bays Expression, but with `d` = **12** (the fixed side):

| room | field | area | ÷ 12 | ÷ 6 | round up | height |
|---|---|---|---|---|---|---|
| admin | 11 | 41.6 | 3.5 | 0.58 | 1 | **6** |
| lab | 12 | 40 | 3.3 | 0.56 | 1 | **6** |
| pharmacy | 13 | 84.8 | 7.1 | 1.18 | 2 | **12** |
| stores | 14 | 138 | 11.5 | 1.92 | 2 | **12** |
| staff rest | 15 | 334.5 | 27.9 | 4.65 | 5 | **30** |

   Put the five areas in one list (one List Item with a Panel of indices `11, 12, 13, 14, 15`, or a **Merge**); one
   Expression then runs five times and returns five heights.
3. **Where: each room starts where the one below ends.** Bottom y = sum of the heights below it (0, 6, 12, 24, 36).
   **Mass Addition** → *Partial Results* gives running totals **6, 12, 24, 36, 66**, which include the room itself, so
   they are the **tops**. **Subtraction** tops − heights = **bottoms** 0, 6, 12, 24, 36. *Result* (66) = column height.
4. **Draw:** Construct Point (0, bottoms) → corner A; Construct Point (green_w, tops) → corner B; Rectangle 2Pt.

✅ **Check:** admin (0, 0, 12 × 6), lab (0, 6, 12 × 6), pharmacy (0, 12, 12 × 12), stores (0, 24, 12 × 12),
staff_rest (0, 36, 12 × 30). Test: put 200 for pharmacy → 3 bays = 18 m; stores and staff rest move up by 6, total 72.

## Lesson 9 — The far end: discharge, laundry, morgue, incinerator
**Goal:** the strip across the top where patients **leave**: recovered patients through discharge, the dead to the
morgue, linen to the laundry, waste to the incinerator.

```
 y=99 ┌──────┬──────────────────┐   ┌────────────┐ ┌────────────┐
      │disch.│ laundry          │   │ morgue     │ │ incinerator│
 y=93 └──────┴──────────────────┘   └────────────┘ └────────────┘
      x=13   19                37   40      49┌─┐52 53         65
                                              │c│  ← top of the patient corridor
```
All rooms are one bay deep, from y = `yt` (93) to `yt + BAY` (99).

**Widths** (bays rule, d = BAY):

| room | field | area | ÷ 6 | ÷ 6 | round up | width |
|---|---|---|---|---|---|---|
| discharge | — | — | | | fixed | **6** |
| laundry | 8 | 106.4 | 17.7 | 2.96 | 3 | **18** |
| morgue | 9 | 72 | 12 | 2.0 | 2 | **12** |
| incinerator | 10 | 46.6 | 7.8 | 1.29 | 2 | **12** |

**Positions:**
- **Discharge** x = `x_red` = 13.
- **Laundry** x = `x_red + BAY` = 19 (ends at 37).
- **Morgue** has two wishes. **A:** sit at the top of the patient corridor, right edge aligned with the corridor:
  `x_corr + PC − w_m` = 49 + 3 − 12 = **40**. **B:** never overlap the laundry; start after it plus a 1 m fence gap
  (morgue is red, laundry amber): `x_red + BAY + w_l + FG` = 13 + 6 + 18 + 1 = **38**.
  Take the one further right: `Max(40, 38)` = **40**. With MAX_PER_ROW = 3 the corridor moves to 37, wish A drops to
  28 and wish B (38) wins: the Max stops the morgue landing on the laundry.
  ⚠️ The 6th input is the laundry **width** `w_l` (18), not its start `x_l` (19).
- **Incinerator** goes right of the corridor **and** the morgue, plus a fence gap:
  `Max(x_corr + PC, x_morgue + w_m) + FG` = Max(52, 52) + 1 = **53**.
- **Top of the plan:** `top = Max(yt + BAY, column height)` = Max(99, 66) = **99**.

### In Grasshopper
**Part A — widths.** Copy the bays Expression three times: `a` ← `a_laundry` / `a_morgue` / `a_incinerator`,
`d` ← BAY → Number params `w_l` = 18, `w_m` = 12, `w_i` = 12. (Shortcut: one Expression on a list of the three areas,
then one **List Item** i = 0 whose outputs i / +1 / +2 are w_l / w_m / w_i.)

**Part B — x positions.**
1. Laundry: Expression `x_red + BAY` → `x_l` = 19.
2. Morgue: Expression with 7 inputs `x_corr, PC, w_m, x_red, BAY, w_l, FG` and
   `Max(x_corr + PC - w_m, x_red + BAY + w_l + FG)` → `x_m` = 40.
3. Incinerator: Expression with 5 inputs `x_corr, PC, x_m, w_m, FG` and `Max(x_corr + PC, x_m + w_m) + FG` → `x_i` = 53.

**Part C — the four rectangles.** For each room: Construct Point (x, yt) → corner A; Expression `x + w` and
Construct Point (x + w, `y_top`) → corner B, where `y_top` = `yt + BAY` = 99 (make it once); Rectangle 2Pt.
Build discharge, group it, then copy for laundry (x_l, w_l), morgue (x_m, w_m), incinerator (x_i, w_i).

**Part D — top.** Expression `Max(a, b)` with a = `y_top`, b = Mass Addition *Result* from Lesson 8 → `top` = 99.

✅ **Check:** discharge (13, 93)–(19, 99), laundry (19, 93)–(37, 99), morgue (40, 93)–(52, 99),
incinerator (53, 93)–(65, 99). MAX_PER_ROW = 3 → `x_m` = 38, `yt` = 156.

Common mistakes: an Expression turns orange → an input name in the formula doesn't match (`x_corr` ≠ `X_corr`);
morgue at 38 with 5 per row → `PC` or `x_corr` not wired; rooms at y = 0 → corner A's Y not wired to `yt`.

## Lesson 10 — Services and fences
**Goal:** services along the road outside the fence, the outer fence around the clinic, and the inner red fence around
the high-risk zone.

```
 y=105 ┌─────────────────────────── outer fence ───────────────────────┐
 y=99  │ ┌green┐ ┌─────────────── red fence ─────────────────────────┐ │
       │ │col. │ │ far end · wards · corridor                        │ │
 y=7.5 │ │     │ └───────────────────────────────────────────────────┘ │
 y=0   │ └─────┘   triage   family                                     │
 y=−6  └───────────────────────────────────────────────────────────────┘
 y=−12   [water ]   [gen]   ┌──loading──┐            ← road side
 y=−18                      └───────────┘
       x=−6  0   12 18 24  30          48                         65  71
```

### Part A: services
Slider `OM` = 6 (outer margin). Services sit one margin plus one bay below the clinic: `sy = −OM − BAY` = **−12**.

| room | field | area | depth | width | x |
|---|---|---|---|---|---|
| water | 16 | 40 | 6 | 2 bays = **12** | 0 |
| generator | 17 | 25 | 6 | 1 bay = **6** | `w_wa + BAY` = 18 |
| loading | 18 | 150 | **12** (truck yard) | 3 bays = **18** | `x_g + w_g + BAY` = 30 |

One empty bay between each for access. Water and generator: y from `sy` to `sy + BAY`; loading is two bays deep, so its
corner A is at `sy − BAY` = −18.
⚠️ Each bays Expression must read **its own** area: generator `a` ← field 17, not 16 (wrong wiring gives 12 m).

✅ water (0, −12)–(12, −6), generator (18, −12)–(24, −6), loading (30, −18)–(48, −6).

### Part B: outer fence
The fence is not calculated from a formula: it **wraps whatever is inside**, so it follows the rooms automatically.
1. **Merge** the Rectangle 2Pt outputs of Lessons 5–9 (wards, donning/PPE/doffing, triage, family, corridor, green
   column, far end). **Not** the services.
2. **Bounding Box** ← Merge. Right-click → tick **Union Box** (otherwise you get one box per rectangle).
3. **Box Corners** → A = {0, 0, 0} (bottom-left), G = {65, 99, 0} (top-right).
4. Either **Rectangle 2Pt** (A, G) → **Offset Curve** by `OM`, corners Sharp (if it shrinks, use −OM), or
   **Deconstruct Point** on A and G → Expressions `x0 − OM`, `y0 − OM`, `x1 + OM`, `y1 + OM` → Rectangle 2Pt.

✅ 77 × 111 m, from (−6, −6) to (71, 105), running between the triage strip and the services.

### Part C: inner red fence
Around the high-risk zone only (staff column, wards, corridor, far end). Each edge sits in the middle of a gap:

| edge | rule | S1 |
|---|---|---|
| left | `x_red − FENCE_GAP / 2` | 12.5 |
| bottom | `BAY + GAP / 2` | 7.5 |
| right | `bx1 + FENCE_GAP / 2` (bx1 = X of corner G) | 65.5 |
| top | `top` (Lesson 9) | 99 |

✅ (12.5, 7.5)–(65.5, 99), touching no room.

### Part D (optional): dormitory and burial
Outside the compound at x = 65 + 2·OM = 77: dormitory 1206 m², depth 12 → 17 bays = 102 m wide at y = 0; burial
1944 m², depth 18 → 18 bays = 108 m wide at y = top − 18 = 81.

Test: MAX_PER_ROW = 3 → the plan gets narrower and taller and both fences follow.

## Lesson 11 — 3D, colours and the patient route

### Part A: folded tents
A tent is a 5-point end wall pushed 18 m along the module:

| point | x | y | z |
|---|---|---|---|
| p1 | x | y | 0 |
| p2 | x | y | 2.8 (`EAVE`) |
| p3 | x + 3 | y | 4.6 (`RIDGE`) |
| p4 | x + 6 | y | 2.8 |
| p5 | x + 6 | y | 0 |

1. Sliders `EAVE` = 2.8, `RIDGE` = 4.6.
2. **Merge** the corner A points of the ward modules → **Deconstruct Point** → `mx`, `my`.
3. Expressions `mx + W / 2` and `mx + W`.
4. Five **Construct Points** p1…p5 as in the table.
5. **Merge** p1 → p5 with **Graft** on each input (or graft the Construct Point outputs). Graft gives every module its
   own list of 5 points; without it all points end up in one list and the polyline zigzags.
6. **PolyLine** (Closed = True) → **Boundary Surfaces** → **Extrude** along **Unit Y** with F = `D` (18).
7. To colour by ward: keep the three wards as separate branches (in `SURGE_wards.gh`: **Shift Paths** −1 →
   **Explode Tree** → one output per ward).

### Part B: boxes
For each colour group: **Merge** its rectangles → **Boundary Surfaces** → **Extrude** along **Unit Z** (F = `H` = 3).
The patient corridor is a path: give it its own Extrude with F = 0.2. Leave fences as lines.

### Part C: colours (one Custom Preview + Colour Swatch each)

| Preview | geometry | RGB |
|---|---|---|
| suspect | suspect tents | 246, 185, 178 |
| probable | probable tents | 238, 139, 129 |
| confirmed | confirmed tents | 184, 48, 47 |
| red zone | corridor, morgue, incinerator | 227, 73, 72 |
| amber zone | doffing, triage, family, discharge, laundry | 237, 161, 0 |
| green zone | donning, PPE store, green column | 27, 175, 122 |
| service | water, generator, loading | 138, 136, 127 |

Green = safe, amber = transition (undressing, waiting, leaving), red = infected; tents darken from suspect to
confirmed. Turn off the default preview of everything else (select → Ctrl+Q).

### Part D: patient route

| point | x | y |
|---|---|---|
| start (inside triage) | `x_red + BAY` = 19 | `BAY / 2` = 3 |
| turn (middle of corridor) | `x_corr + PC / 2` = 50.5 | 3 |
| one per row | 50.5 | `y_r + D / 2` = 18, 39, 60, 81 |
| end (far end) | 50.5 | `yt + BAY / 2` = 96 |

`y_r` is the row-bottom list from Lesson 6 (9, 30, 51, 72). (Alternative used in `SURGE_wards.gh`: flatten the module
y values and **Create Set** to keep the unique ones.) **Merge** start, turn, rows, end (no graft) → **PolyLine**
(open) → **Length** = **124.5 m** (31.5 across + 93 up). Move it up 0.3 m and preview it blue (42, 120, 214).

✅ 18 tents in rows of 5 / 3 / 5 / 5, coloured light → dark; compare with `data/s4/fig_10_axonometric.png`.

## Lesson 12 — Checks, and computing the areas in Grasshopper
**Checks** (Panels so they are visible):
- beds = number of ward rectangles × 12 = `beds_total` (216) → **Equality** → True
- longest staff walk = `per_row * W + FENCE_GAP / 2` = 30.5 → **Smaller Than** 45 → True
- patient route length = 124.5 m
- Set `MAX_PER_ROW` = 8: the walk becomes 48.5 and the check turns False. The rule is working.

**Compare with the Python result:** read `data/s4/gh/reference_S1.csv` the same way as in Lesson 4. Each line is one
rectangle: x = field 3, y = 4, w = 5, h = 6. Draw them as thin outlines on top of yours. They should sit exactly on top.

**Optional: let Grasshopper compute the areas (Part 1) itself.**
Instead of reading the areas from the CSV, read only `beds_total` and add sliders for the ratios. For example:
triage = `30 + 0.4 * beds_total`, stores = `30 + 0.5 * beds_total`, pharmacy = `20 + 0.3 * beds_total`.
Then dragging a ratio slider resizes the room and the whole plan rearranges. That shows the full chain
*data → beds → areas → layout* live on the canvas.

---

## Final tests for the whole definition
| Test | Expected |
|---|---|
| S1, MAX_PER_ROW 5 | everything matches `reference_S1.csv`; fence 77 × 111; route 124.5 m |
| S1, MAX_PER_ROW 3 | 7 rows, corridor at x = 37, morgue at x = 38 (laundry wins), `yt` = 156 |
| S3 | 2 / 1 / 4 modules, shorter plan, fence shrinks |

## Bugs found while reviewing the build (and their fixes)
| Symptom | Cause | Fix |
|---|---|---|
| Corridor moves with MAX_PER_ROW but wards don't rewrap | Modulus / Integer Division still on the Lesson 3 `per_row` slider | Wire B to the Lesson 5 `per_row` (Minimum) and delete the slider |
| `x_m` stays 40 when MAX_PER_ROW = 3 | `x_corr` wired to the old slider, and `x_l` used instead of `w_l` | Wire `x_corr` from Lesson 5's `per_row`; 6th input = `w_l` (18) |
| Values belong to S2 when S1 is selected | Value List 1…4 on a list without the header | Use 0…3 (or read the header line too and keep 1…4) |
| Generator 12 m wide, loading pushed to x = 36 | Generator Expression reads the water area | `a` ← generator area (field 17), `d` ← BAY |
| Triage can be 1 bay | `2 × BAY` Multiplication with an empty input | Set both inputs |
| `y_r` missing | Lesson 6 Expression not named | Number param `y_r` after `Y0 + r * pitch` |
