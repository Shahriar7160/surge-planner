# Step 3 — ward brief per site

Run: `python pipeline/s3_run.py && python pipeline/s3_figures.py`. Ratios are in `pipeline/s3_params.py`.
**They are DRAFT values from general MSF/WHO Ebola guidance, written from memory. Check each `note` and replace it.**

## How the brief is built
1. **Confirmed beds** = peak of the site's own daily demand (step 2 patch demand × the share of each patch assigned to the site).
   This is lower than step 2's figure for some sites, because patch peaks happen on different days.
2. **Suspect and probable wards** are added on top, using the ward split (25% / 15% / 60% of all isolation beds).
3. Every ward is rounded up to whole **12-bed modules**.
4. **Staff, supplies and spaces** follow from the beds through the ratios. Each space has a zone (red = high risk,
   amber = transition, green = low risk, service).
5. **Plot** = net area × circulation 1.3 ÷ site coverage 0.35, plus outdoor areas. It is checked against the buildable
   land within 300 m found in step 2.
6. **Schedule:** confirmed-ward modules needed per week from the opening date (two weeks after planning).

## Result

| Site | Peak confirmed beds | Modules suspect / probable / confirmed | Modules / beds | Staff (per shift) | Water/day | Power | Plot | Fits |
|---|---|---|---|---|---|---|---|---|
| S1 · Fokodoumandou | 120 | 5 / 3 / 10 | 18 / 216 | 668 (223) | 120 m³ | 231 kW | 1.49 ha | yes |
| S2 · Kagbadou | 49 | 2 / 2 / 5 | 9 / 108 | 346 (116) | 60 m³ | 123 kW | 0.81 ha | yes |
| S3 · Kouankan | 40 | 2 / 1 / 4 | 7 / 84 | 276 (92) | 47 m³ | 99 kW | 0.68 ha | yes |
| S4 · N'Zébéla | 37 | 2 / 1 / 4 | 7 / 84 | 276 (92) | 47 m³ | 99 kW | 0.67 ha | yes |

## Outputs (data/s3/)
- `briefs.json`: full machine-readable brief per site (wards, staff, supplies, spaces with zones, area check,
  ward sequence and circulation rules). **This is the input for the Grasshopper ward generator in step 4.**
- `briefs.csv`, `spaces.csv`, `schedule.csv`: the same as tables
- `fig_7_ward_briefs.png`, `fig_8_schedule.png`
