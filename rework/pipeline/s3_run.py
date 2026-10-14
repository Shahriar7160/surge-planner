"""Step 3 — from bed demand to a ward brief per site.

Reads data/s2/sites.csv (+ the daily bed demand per patch and the patch→site assignment) and writes
data/s3/: briefs.json (machine-readable, for Grasshopper in step 4), briefs.csv, spaces.csv,
schedule.csv (modules per week), README.md and figures.

    python pipeline/s3_run.py
"""
import json
import math

import numpy as np
import pandas as pd

import s3_params as Q
from config import OUT

S2 = OUT.parent / "s2"
S3 = OUT.parent / "s3"
S3.mkdir(exist_ok=True)
DAY0 = pd.Timestamp(json.load(open(S2 / "calibration.json"))["day0"])


def modules(beds):
    return max(Q.MIN_MODULES_PER_WARD, math.ceil(beds / Q.BEDS_PER_MODULE))


def site_series(site, beds, Y):
    """Daily confirmed-bed demand for one site = patch demand × share of each patch assigned to it."""
    return beds @ Y[:, int(site["col"])]


def brief(site, series):
    plan0 = (pd.Timestamp(Q.PLANNING_FROM) - DAY0).days
    confirmed = float(series[plan0:].max())
    total = confirmed / Q.WARD_SPLIT["confirmed"]["share"]
    wards = []
    for name, w in Q.WARD_SPLIT.items():
        b = confirmed if name == "confirmed" else total * w["share"]
        m = modules(b)
        wards.append({"ward": name, "risk": w["risk"], "beds_needed": round(b, 1), "modules": m,
                      "beds": m * Q.BEDS_PER_MODULE, "note": w["note"]})
    beds_by = {w["ward"]: w["beds"] for w in wards}
    beds_all = sum(beds_by.values())
    n_wards = len(wards)

    staff = {}
    for k, s in Q.STAFF.items():
        b = beds_by["confirmed"] if k == "clinical_confirmed" else \
            beds_by["suspect"] + beds_by["probable"] if k == "clinical_suspect_probable" else beds_all
        staff[k] = math.ceil(s["fixed"] + s["per_bed"] * b)
    staff_total = sum(staff.values())
    on_shift = math.ceil(staff_total / Q.SHIFTS)
    resident = math.ceil(staff_total * Q.STAFF_ON_SITE_DORM_SHARE)
    clinical = staff["clinical_confirmed"] + staff["clinical_suspect_probable"]

    S = Q.SUPPLY
    supplies = {
        "water_l_day": round(S["water_l_per_bed"]["value"] * beds_all + S["water_l_per_staff"]["value"] * staff_total),
        "power_kw": round(S["power_kw_per_bed"]["value"] * beds_all + S["power_kw_base"]["value"]),
        "medical_waste_kg_day": round(S["medical_waste_kg_per_bed"]["value"] * beds_all),
        "ppe_sets_day": round(S["ppe_sets_per_clinical_staff"]["value"] * clinical),
        "chlorine_l_day": round(S["chlorine_l_per_bed"]["value"] * beds_all),
    }

    deaths_90d = confirmed / 10 * 90 * Q.CASE_FATALITY        # admissions/day ≈ beds / LOS(10 d)
    spaces = []
    for name, zone, fixed, per_bed, per_ward, note in Q.SPACES:
        if name.startswith("ward_"):
            area = per_bed * beds_by[name.split("_", 1)[1]]
        elif name == "morgue":
            area = max(2, math.ceil(beds_by["confirmed"] / 10)) * 6
        elif name == "staff_rest":
            area = 1.5 * on_shift
        elif name == "staff_dormitory":
            area = 6 * resident
        elif name == "burial_area":
            area = 3 * deaths_90d
        else:
            area = fixed + per_bed * beds_all + per_ward * n_wards
        spaces.append({"space": name, "zone": zone, "area_m2": round(area, 1), "note": note})
    built = sum(s["area_m2"] for s in spaces if s["zone"] != "service" or s["space"] in ("water_treatment", "generator"))
    gross = built * Q.CIRCULATION_FACTOR
    outdoor = sum(s["area_m2"] for s in spaces if s["space"] in ("loading_zone", "burial_area", "staff_dormitory"))
    plot = gross / Q.SITE_COVERAGE + outdoor
    side = math.sqrt(plot)
    # buildable land available around the site (step 2: share of suitable cells within 300 m)
    available = float(site["s_burial_space"]) * math.pi * 300 ** 2

    return {
        "site_id": site["site_id"], "near": site["near"], "lon": float(site["lon"]), "lat": float(site["lat"]),
        "peak_confirmed_beds": round(confirmed, 1), "isolation_beds_needed": round(total, 1),
        "wards": wards, "modules_total": sum(w["modules"] for w in wards), "beds_total": beds_all,
        "staff": staff, "staff_total": staff_total, "staff_per_shift": on_shift, "staff_resident": resident,
        "supplies": supplies, "spaces": spaces,
        "area": {"built_net_m2": round(built), "built_gross_m2": round(gross), "plot_m2": round(plot),
                 "plot_side_m": round(side), "buildable_within_300m_m2": round(available),
                 "fits": bool(plot <= available)},
        "sequence": ["triage", "ward_suspect", "ward_probable", "ward_confirmed", "morgue|patient_discharge"],
        "rules": {"one_way_routes": True, "fence": f"double, {Q.FENCE_GAP_M} m apart",
                  "red_to_green_only_via": "doffing_decon", "incinerator": "downwind, red zone",
                  "staff_entry": "green → donning → red", "patient_entry": "triage only"},
    }


def schedule(site, series):
    """Confirmed-ward modules needed per week from the deployment date."""
    d0 = (pd.Timestamp(Q.PLANNING_FROM) - DAY0).days + Q.DEPLOY_DAYS
    s = pd.Series(series[d0:], index=pd.date_range(DAY0 + pd.Timedelta(days=d0), periods=len(series) - d0))
    w = s.resample("W-MON").max()
    return pd.DataFrame({"site_id": site["site_id"], "week": w.index, "confirmed_beds": w.values.round(1),
                         "confirmed_modules": [modules(b) for b in w.values]})


def main():
    sites = pd.read_csv(S2 / "sites.csv")
    beds = np.load(S2 / "beds.npy")
    Y = np.load(S2 / "assignment.npy")
    briefs, sched = [], []
    for _, site in sites.iterrows():
        ser = site_series(site, beds, Y)
        briefs.append(brief(site, ser))
        sched.append(schedule(site, ser))
    meta = {"generated_by": "pipeline/s3_run.py", "ratios": "pipeline/s3_params.py (DRAFT, to verify)",
            "beds_per_module": Q.BEDS_PER_MODULE}
    json.dump({"meta": meta, "sites": briefs}, open(S3 / "briefs.json", "w"), indent=1, ensure_ascii=False)
    rows = []
    for b in briefs:
        r = {"site_id": b["site_id"], "near": b["near"], "peak_confirmed_beds": b["peak_confirmed_beds"]}
        r.update({f"modules_{w['ward']}": w["modules"] for w in b["wards"]})
        r.update({"modules_total": b["modules_total"], "beds_total": b["beds_total"], "staff_total": b["staff_total"],
                  "staff_per_shift": b["staff_per_shift"], **b["supplies"], **b["area"]})
        rows.append(r)
    pd.DataFrame(rows).to_csv(S3 / "briefs.csv", index=False)
    pd.DataFrame([{"site_id": b["site_id"], **s} for b in briefs for s in b["spaces"]]).to_csv(S3 / "spaces.csv", index=False)
    pd.concat(sched).to_csv(S3 / "schedule.csv", index=False)
    for b in briefs:
        print(f"[s3] {b['site_id']} {b['near']:<14} wards " +
              " / ".join(f"{w['ward'][:4]} {w['modules']}" for w in b["wards"]) +
              f" = {b['modules_total']} modules, {b['beds_total']} beds · staff {b['staff_total']} · "
              f"water {b['supplies']['water_l_day']:,} L/d · plot {b['area']['plot_m2']:,} m² "
              f"({'fits' if b['area']['fits'] else 'DOES NOT FIT'} in {b['area']['buildable_within_300m_m2']:,} m²)")
    return briefs


if __name__ == "__main__":
    main()
