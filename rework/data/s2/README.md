# Step 2 — from data to treatment sites

Run: `python pipeline/s2_run.py && python pipeline/s2_figures.py && python pipeline/s2_report.py`
(about 1–2 minutes; the outbreak calibration is cached). Every threshold and weight is in `pipeline/s2_params.py`.

## 1 · Road network and patches
- 2014 OSM roads → a graph of 277k nodes (182k in the connected network). Speeds are set per road class, and there is a
  rainy-season graph (tracks ×0.5, paths ×0.6).
- **90 settlement patches** (cities, towns, villages; neighbourhoods merged, hamlets attached by road time)
  holding **908,417 people** (HRSL), Guinea part of the study area.

## 2 · Outbreak model (calibrated)
Metapopulation SEIR on the patches, coupled by a gravity model on road travel time (the mobility layer). It is seeded at
Meliandou in December 2013, with a separate introduction into Macenta, and fitted to the Guinea MoH cumulative cases by
prefecture, 4 Aug – 1 Oct 2014.

| Parameter | Value |
|---|---|
| R₀ | 1.56 |
| Control strength (share of transmission removed) | 49% |
| Control midpoint · Guéckédou / Macenta / other | 2014-05-04 / 2014-10-16 / 2014-03-02 |
| Macenta introduction | 2014-08-04 |
| Mobility share | 0.005 |
| Reporting rate (fixed, CDC 2014 ×2.5 correction) | 40% |
| Fit error (log RMSE) | 0.096 |

Bed demand = 70% of symptomatic cases × 10 days in a bed.
**Region peak: 252 beds (late Oct 2014).** The planning window is Aug–Oct 2014; beyond that the
fit would be extrapolation.
Known limits: the model is deterministic (no uncertainty bands yet), and the Macenta control date sits on its upper
bound because the data end on 1 Oct.

## 3 · Location
**MUST filters (hard):** candidates (500 m grid, Guinea) **68,885** → slope **20,473** → land cover (water, wetland, forest) **8,958** → flood (near river) **8,217** → isolation from settlements **7,694** → truck access **4,135** → water supply **1,694** → lab reach **1,031** → buildable area **936**

**SHOULD scores (weights):** cell coverage 0.10, near hospital 0.20, helipad space 0.10, rainy access 0.15, border flow 0.10, waste downhill 0.10, burial space 0.05, community acceptance 0.10, fuel supply 0.10

**Optimisation:** capacitated maximal covering MILP (HiGHS via SciPy). It maximises the peak bed demand served within
1.5 h by road, plus a small reward for the SHOULD score, with at most
10 modules (120 beds) per site. The number of sites is
chosen automatically: the smallest K with ≥95% coverage.

### Result: 4 sites cover 97% of peak demand · 24 modules · 288 beds

| Site | Location | Peak beds served | Modules | Patches | People | To hospital | Score |
|---|---|---|---|---|---|---|---|
| S1 | near Fokodoumandou (2.6 km from Macenta) | 120 | 10 × 12 = 120 | 11 | 126,587 | 0.17 h | 0.82 |
| S2 | near Kagbadou (4.1 km from Guéckédou) | 62 | 6 × 12 = 72 | 13 | 272,940 | 0.27 h | 0.94 |
| S3 | near Kouankan (41.5 km from Macenta) | 40 | 4 × 12 = 48 | 13 | 42,973 | 1.51 h | 0.53 |
| S4 | near N'Zébéla (62.1 km from Macenta) | 37 | 4 × 12 = 48 | 22 | 56,467 | 1.58 h | 0.43 |

**Check against 2014:** the two largest sites sit next to Macenta and Guéckédou, the two prefectures where the MoH
sitreps record treatment centres (CTE) operating in Aug–Oct 2014.

**Against the 2015 method:** a regular grid with one unit per 500 km² needs **33 units** to cover
100%. S.U.R.G.E. covers 97% with **4 sites**.

### Trade-off sweep (share of peak bed demand covered)
| sites \ travel limit | 0.75 h | 1 h | 1.5 h | 2 h | 3 h |
|---|---|---|---|---|---|
| 2 | 68% | 73% | 88% | 91% | 91% |
| 3 | 77% | 82% | 93% | 99% | 100% |
| 4 | 82% | 87% | 97% | 99% | 100% |
| 5 | 88% | 92% | 98% | 99% | 100% |
| 6 | 91% | 96% | 98% | 99% | 100% |
| 8 | 94% | 96% | 98% | 99% | 100% |
| 10 | 96% | 96% | 98% | 99% | 100% |

### Sensitivity: health-facility repair
With only the raw MoH facility list, 542 candidates pass the filters instead of
936 (fewer pass "lab reach"). Coverage is 98% instead of
97%, and 3 of 4 sites stay within 2 km. The repair moves one
site and leaves the overall answer unchanged.

## 4 · Feedback
Sites open on 2014-08-15 (two weeks to build) and cut transmission by 60% in the patches they serve:
**about 1,572 cases averted by 2014-10-31** compared with no response.

## Outputs (data/s2/)
`sites.geojson` / `sites.csv` (input to step 3), `patches.csv`, `candidates.csv.gz`, `filter_funnel.csv`, `sweep.csv`,
`response_curve.csv`, `calibration.json`, `summary.json`, `fig_1 … fig_4 *.png`.
