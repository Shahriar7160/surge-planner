"""Step 2 — run everything: network, outbreak, location, sweeps, feedback. Writes data/s2/.

    python pipeline/s2_run.py
"""
import json

import numpy as np
import pandas as pd

import s2_params as P
from s2_network import S2, build_network, build_patches, km
from s2_outbreak import DAY0, _groups, bed_demand, run as run_outbreak, simulate
from s2_siting import evaluate, grid_baseline, place, thin, time_matrix


def to_geojson(df, path, props):
    feats = [{"type": "Feature", "properties": {k: (None if pd.isna(r[k]) else (r[k].item() if hasattr(r[k], "item") else r[k]))
                                                for k in props},
              "geometry": {"type": "Point", "coordinates": [round(r.lon, 6), round(r.lat, 6)]}} for _, r in df.iterrows()]
    json.dump({"type": "FeatureCollection", "features": feats}, open(path, "w"), ensure_ascii=False, indent=0)


def main():
    net = build_network()
    patches, _ = build_patches(net)
    patches, theta, Tp, seed_idx, obs = run_outbreak(net, patches)

    cand = evaluate(net, patches)
    T = time_matrix(net, patches, thin(cand))

    # ---------------- sweeps: number of sites × travel limit
    rows = []
    for K in P.SWEEP_SITES:
        for h in P.SWEEP_TRAVEL_H:
            s, _, c, _, _, _ = place(net, patches, cand, K=K, limit_h=h, T=T)
            rows.append({"sites": K, "travel_h": h, "coverage": c, "modules": int(s.modules.sum())})
    sweep = pd.DataFrame(rows)
    sweep.to_csv(S2 / "sweep.csv", index=False)
    print("[s2] sweep:\n" + sweep.pivot(index="sites", columns="travel_h", values="coverage").round(2).to_string())

    K = P.MAX_SITES
    if P.AUTO_SITES:
        ok = sweep[(sweep.travel_h == P.MUST["max_patient_travel_h"]) & (sweep.coverage >= P.TARGET_COVERAGE)
                   & (sweep.sites <= P.MAX_SITES)]
        K = int(ok.sites.min()) if len(ok) else P.MAX_SITES
        print(f"[s2] auto: smallest number of sites reaching {P.TARGET_COVERAGE:.0%} coverage = {K}")
    sites, Y, cov, status, pool, T = place(net, patches, cand, K=K, T=T)
    sites["col"] = np.arange(len(sites))
    print(f"[s2] optimiser {status}: {len(sites)} sites cover {cov:.0%} of peak bed demand within "
          f"{P.MUST['max_patient_travel_h']} h; modules {sites.modules.tolist()}")
    grid, grid_cov = grid_baseline(net, patches, P.MUST["max_patient_travel_h"])
    print(f"[s2] 2015 grid baseline: {len(grid)} units cover {grid_cov:.0%}")

    # nearest named settlement for each site (for labels)
    st = pd.read_csv(S2 / "settlements_patches.csv")
    named = st[st.name.notna() & st.type.isin(["city", "town", "village", "hamlet"])]
    from scipy.spatial import cKDTree
    d, j = cKDTree(km(named.lon, named.lat)).query(km(sites.lon, sites.lat))
    sites["near"] = named.name.values[j]
    sites["near_km"] = d.round(1)
    sites["site_id"] = [f"S{i + 1}" for i in range(len(sites))]
    sites = sites.sort_values("beds_demand", ascending=False)
    sites["site_id"] = [f"S{i + 1}" for i in range(len(sites))]
    score_cols = [c for c in sites.columns if c.startswith("s_")]
    to_geojson(sites, S2 / "sites.geojson",
               ["site_id", "near", "near_km", "beds_demand", "modules", "beds", "patches_served", "people_served",
                "t_hospital_h", "score"] + score_cols)
    assign = pd.DataFrame(Y, columns=list(sites.sort_index().index))
    np.save(S2 / "assignment.npy", Y)
    sites.to_csv(S2 / "sites.csv", index=False)

    # ---------------- sensitivity: facility repair (MoH-only facilities vs repaired)
    cand_moh = evaluate(net, patches, facilities_file="health_facilities_moh.geojson", save=False)
    s_moh, _, cov_moh, _, _, _ = place(net, patches, cand_moh, K=K)
    dshift = cKDTree(km(s_moh.lon, s_moh.lat)).query(km(sites.lon, sites.lat))[0]
    sens = {"coverage_repaired": cov, "coverage_moh_only": cov_moh,
            "candidates_repaired": int(cand.pass_all.sum()), "candidates_moh_only": int(cand_moh.pass_all.sum()),
            "site_shift_km": dshift.round(1).tolist(), "sites_within_2km": int((dshift <= 2).sum())}
    print(f"[s2] facility-repair sensitivity: coverage {cov:.0%} vs {cov_moh:.0%} (MoH only); "
          f"{sens['sites_within_2km']}/{len(sites)} sites within 2 km of the MoH-only solution")

    # ---------------- feedback: what the sites do to the outbreak
    covered = Y.sum(1) > 0.01
    deploy = (pd.Timestamp(P.PLANNING_FROM) - DAY0).days + 14       # two weeks to build
    days = (pd.Timestamp(P.HORIZON) - DAY0).days + 1
    pidx, intro = _groups(patches)
    base = simulate(theta, Tp, patches["pop"].values, seed_idx, days, pref_idx=pidx, intro_idx=intro)
    resp = simulate(theta, Tp, patches["pop"].values, seed_idx, days, cut=np.where(covered, 0.4, 1.0),
                    cut_from=deploy, pref_idx=pidx, intro_idx=intro)
    _, b_beds = bed_demand(base)
    _, r_beds = bed_demand(resp)
    curve = pd.DataFrame({"date": pd.date_range(DAY0, periods=days), "beds_no_response": b_beds.sum(1),
                          "beds_with_surge": r_beds.sum(1), "cases_no_response": base.sum(1).cumsum(),
                          "cases_with_surge": resp.sum(1).cumsum()})
    curve.to_csv(S2 / "response_curve.csv", index=False)
    plan0 = (pd.Timestamp(P.PLANNING_FROM) - DAY0).days
    averted = float(base[plan0:].sum() - resp[plan0:].sum())

    summary = {
        "patches": len(patches), "population": float(patches["pop"].sum()),
        "calibration": json.load(open(S2 / "calibration.json")),
        "peak_beds_region": float(b_beds.sum(1).max()),
        "filter_funnel": pd.read_csv(S2 / "filter_funnel.csv").values.tolist(),
        "sites": len(sites), "sites_rule": f"smallest K with ≥{P.TARGET_COVERAGE:.0%} coverage" if P.AUTO_SITES else "fixed",
        "coverage": cov, "status": status,
        "modules_total": int(sites.modules.sum()), "beds_total": int(sites.beds.sum()),
        "grid_units": len(grid), "grid_coverage": grid_cov,
        "facility_sensitivity": sens,
        "cases_averted_by_horizon": averted, "deploy_date": str((DAY0 + pd.Timedelta(days=deploy)).date()),
        "params": {"MUST": P.MUST, "SHOULD": P.SHOULD, "MAX_SITES": P.MAX_SITES,
                   "BEDS_PER_MODULE": P.BEDS_PER_MODULE},
    }
    json.dump(summary, open(S2 / "summary.json", "w"), indent=2, default=float)
    grid.to_csv(S2 / "grid_2015.csv", index=False)
    print(f"[s2] feedback: {averted:,.0f} cases averted by {P.HORIZON}; deploy {summary['deploy_date']}")
    return summary


if __name__ == "__main__":
    main()
