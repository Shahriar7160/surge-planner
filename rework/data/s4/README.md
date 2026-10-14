# Step 4 — automatic ward design

Run: `python pipeline/s4_run.py`. The kit of parts and rules are in `pipeline/s4_params.py`; the generator is `pipeline/s4_layout.py`.

## Kit of parts
- **Ward module:** 6 × 18 m (one bay wide, three bays deep), 12 beds, 9 m² per bed. It is the 2015 origami tent folded
  along its long axis (eave 2.8 m, ridge 4.6 m).
- **Service bay:** 6 × 6 m on the same frame; every support space is a whole number of bays.

## Layout rules (a rule-based generator, not a drawing)
1. Triage at the road side is the only patient entrance. Patients move one way: suspect → probable → confirmed →
   discharge or morgue, along a single patient corridor.
2. Every ward row starts with donning (green), a PPE store and doffing/decontamination (amber). Staff go green →
   donning → red → doffing.
3. The low-risk column (admin, lab, pharmacy, stores, staff rest) sits behind a 1 m double fence. No red space may
   touch a green space except through donning or doffing.
4. Rows hold at most `MAX_MODULES_PER_ROW` modules, which keeps staff walks short.
5. Morgue and incinerator are at the far end. On the map, the plan is rotated to face the nearest road and mirrored
   if needed so the incinerator is downwind (south-west rainy-season wind).
6. **Automatic checks:** bed count matches the brief, no red/green contact, no overlaps, staff walk ≤ 45 m. The
   checker caught a real bug while this was being built: with 3 modules per row, the laundry overlapped the morgue.
   It is now fixed.

## Result

| Site | Beds | Fenced | Patient path | Longest staff walk | Checks | Map rotation |
|---|---|---|---|---|---|---|
| S1 | 216 | 77 × 111 m | 124 m | 30 m | passed | 37.0° |
| S2 | 108 | 71 × 90 m | 104 m | 30 m | passed | -25.1° |
| S3 | 84 | 65 × 90 m | 98 m | 24 m | passed | 132.1° (mirrored) |
| S4 | 84 | 65 × 90 m | 98 m | 24 m | passed | 236.1° (mirrored) |

## Outputs (data/s4/)
- `layouts.json`: every part (name, zone, kind, x, y, w, h) per site, in local metres. **Read by Grasshopper.**
- `footprints.geojson`: the same parts placed on the map (rotated and mirrored), for the web map
- `checks.json`: rule checks
- `fig_9_plans.png` (4 plans, same scale), `fig_10_axonometric.png` (S1 3D), `fig_11_variants.png` (one variable, three layouts)

## In Rhino / Grasshopper (see `grasshopper/README.md`)
- **Quick:** `grasshopper/surge_draw_layouts.py` in a Grasshopper Python 3 component draws any site from `layouts.json`.
- **Live:** `grasshopper/surge_hops_server.py` runs the generator as a Hops component. Change Site / MaxPerRow / Bay
  in Grasshopper and the layout regenerates.
