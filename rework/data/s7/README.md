# Step 7 — after the outbreak: ward → community centre

Run: `python pipeline/s7_community.py`. Ratios: `pipeline/s7_params.py` (**DRAFT**, check the notes).

The 2015 project ended with a community centre on the same site (learning centre, workshops, counselling). Here it is generated: the outbreak model gives the people in each site's catchment, those numbers size the programme, and the step 4 generator lays it out with the same kit and rules.

| Site | Cases | Survivors | Children who lost a parent | Households | Modules needed | From the ward | New |
|---|---|---|---|---|---|---|---|
| S1 · Fokodoumandou | 982 | 393 | 884 | 655 | 23 | 18 | 5 |
| S2 · Kagbadou | 1,250 | 500 | 1,125 | 833 | 28 | 9 | 19 |
| S3 · Kouankan | 323 | 129 | 290 | 215 | 11 | 7 | 4 |
| S4 · N'Zébéla | 300 | 120 | 270 | 200 | 10 | 7 | 3 |

**Finding:** bed need and community need do not match. S2 near Guéckédou, where the outbreak began in December 2013, needed few beds in Aug–Oct 2014 but has the most survivors and bereaved families.

## What becomes what
- ward modules → clinic, counselling, workshops, hall (two modules joined), kitchen, classrooms
- triage → reception · patient corridor → covered street · morgue + incinerator → memorial garden
- donning / doffing → washrooms · staff rest → library · loading zone → market square
- the red fence comes down; the cladding is swapped: **ward**: sealed twin-wall PP panels, washable with 0.5% chlorine; negative-pressure end wall; **community**: lower 1.2 m: timber louvre panels (cross-ventilation); upper: translucent PP diamonds; end walls: open doors to the covered street

## Outputs (data/s7/)
- `community.json` programme and layout per site (**used by the web planner**)
- `community.csv`, `fig_16_ward_to_community.png`, `fig_17_needs.png`
