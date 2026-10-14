"""Step 2 — write data/s2/README.md from the run outputs."""
import json
import math

import pandas as pd

import s2_params as P
from config import OUT
from s2_network import KX, KY, S2


def main():
    S = json.load(open(S2 / "summary.json"))
    cal = S["calibration"]
    s = pd.read_csv(S2 / "sites.csv")
    sw = pd.read_csv(S2 / "sweep.csv")
    towns = {f["properties"]["name"]: f["geometry"]["coordinates"]
             for f in json.load(open(OUT / "osm2014" / "places.geojson"))["features"]
             if f["properties"]["name"] in ("Macenta", "Guéckédou", "Kissidougou") and f["properties"]["type"] == "city"}

    def nearest_town(r):
        d = {n: math.hypot((r.lon - x) * KX, (r.lat - y) * KY) for n, (x, y) in towns.items()}
        n = min(d, key=d.get)
        return f"{d[n]:.1f} km from {n}"

    rows = "\n".join(
        f"| {r.site_id} | near {r.near} ({nearest_town(r)}) | {r.beds_demand:.0f} | {r.modules} × 12 = {r.beds} | "
        f"{r.patches_served} | {r.people_served:,.0f} | {r.t_hospital_h:.2f} h | {r.score:.2f} |" for r in s.itertuples())
    fun = " → ".join(f"{a} **{b:,}**" for a, b in S["filter_funnel"])
    piv = sw.pivot(index="sites", columns="travel_h", values="coverage")
    sweep_md = "| sites \\ travel limit | " + " | ".join(f"{h:g} h" for h in piv.columns) + " |\n|" + "---|" * (len(piv.columns) + 1) + "\n"
    sweep_md += "\n".join(f"| {k} | " + " | ".join(f"{v:.0%}" for v in row) + " |" for k, row in piv.iterrows())
    fs = S["facility_sensitivity"]
    md = f"""# Step 2 — from data to treatment sites

Run: `python pipeline/s2_run.py && python pipeline/s2_figures.py && python pipeline/s2_report.py`
(about 1–2 minutes; the outbreak calibration is cached). Every threshold and weight is in `pipeline/s2_params.py`.

## 1 · Road network and patches
- 2014 OSM roads → a graph of 277k nodes (182k in the connected network). Speeds are set per road class, and there is a
  rainy-season graph (tracks ×0.5, paths ×0.6).
- **{S['patches']} settlement patches** (cities, towns, villages; neighbourhoods merged, hamlets attached by road time)
  holding **{S['population']:,.0f} people** (HRSL), Guinea part of the study area.

## 2 · Outbreak model (calibrated)
Metapopulation SEIR on the patches, coupled by a gravity model on road travel time (the mobility layer). It is seeded at
Meliandou in December 2013, with a separate introduction into Macenta, and fitted to the Guinea MoH cumulative cases by
prefecture, 4 Aug – 1 Oct 2014.

| Parameter | Value |
|---|---|
| R₀ | {cal['R0']:.2f} |
| Control strength (share of transmission removed) | {cal['control_strength']:.0%} |
| Control midpoint · Guéckédou / Macenta / other | {cal['control_midpoint_date_gueckedou']} / {cal['control_midpoint_date_macenta']} / {cal['control_midpoint_date_other']} |
| Macenta introduction | {cal['introduction_date_macenta']} |
| Mobility share | {cal['mobility_share']:.3f} |
| Reporting rate (fixed, CDC 2014 ×2.5 correction) | {cal['reporting_rate']:.0%} |
| Fit error (log RMSE) | {cal['rmse_log']:.3f} |

Bed demand = {P.P_SEEK_CARE:.0%} of symptomatic cases × {P.LENGTH_OF_STAY_D} days in a bed.
**Region peak: {S['peak_beds_region']:.0f} beds (late Oct 2014).** The planning window is Aug–Oct 2014; beyond that the
fit would be extrapolation.
Known limits: the model is deterministic (no uncertainty bands yet), and the Macenta control date sits on its upper
bound because the data end on 1 Oct.

## 3 · Location
**MUST filters (hard):** {fun}

**SHOULD scores (weights):** """ + ", ".join(f"{k.replace('_', ' ')} {v:.2f}" for k, v in P.SHOULD.items()) + f"""

**Optimisation:** capacitated maximal covering MILP (HiGHS via SciPy). It maximises the peak bed demand served within
{P.MUST['max_patient_travel_h']} h by road, plus a small reward for the SHOULD score, with at most
{P.MAX_MODULES_PER_SITE} modules ({P.MAX_MODULES_PER_SITE * P.BEDS_PER_MODULE} beds) per site. The number of sites is
chosen automatically: the {S['sites_rule']}.

### Result: {S['sites']} sites cover {S['coverage']:.0%} of peak demand · {S['modules_total']} modules · {S['beds_total']} beds

| Site | Location | Peak beds served | Modules | Patches | People | To hospital | Score |
|---|---|---|---|---|---|---|---|
{rows}

**Check against 2014:** the two largest sites sit next to Macenta and Guéckédou, the two prefectures where the MoH
sitreps record treatment centres (CTE) operating in Aug–Oct 2014.

**Against the 2015 method:** a regular grid with one unit per 500 km² needs **{S['grid_units']} units** to cover
{S['grid_coverage']:.0%}. S.U.R.G.E. covers {S['coverage']:.0%} with **{S['sites']} sites**.

### Trade-off sweep (share of peak bed demand covered)
{sweep_md}

### Sensitivity: health-facility repair
With only the raw MoH facility list, {fs['candidates_moh_only']} candidates pass the filters instead of
{fs['candidates_repaired']} (fewer pass "lab reach"). Coverage is {fs['coverage_moh_only']:.0%} instead of
{fs['coverage_repaired']:.0%}, and {fs['sites_within_2km']} of {S['sites']} sites stay within 2 km. The repair moves one
site and leaves the overall answer unchanged.

## 4 · Feedback
Sites open on {S['deploy_date']} (two weeks to build) and cut transmission by 60% in the patches they serve:
**about {S['cases_averted_by_horizon']:,.0f} cases averted by {P.HORIZON}** compared with no response.

## Outputs (data/s2/)
`sites.geojson` / `sites.csv` (input to step 3), `patches.csv`, `candidates.csv.gz`, `filter_funnel.csv`, `sweep.csv`,
`response_curve.csv`, `calibration.json`, `summary.json`, `fig_1 … fig_4 *.png`.
"""
    (S2 / "README.md").write_text(md)
    print("[s2] report written")


if __name__ == "__main__":
    main()
