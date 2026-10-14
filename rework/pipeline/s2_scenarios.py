"""Step 2d — scenario study: same data, different variables, different sites.

Shows that site selection is produced by the algorithm. Each scenario changes ONE variable and reruns
filters → scores → optimisation. A Monte-Carlo run over random SHOULD weights then shows which sites
are robust (chosen whatever the priorities) and which depend on them.

    python pipeline/s2_scenarios.py          (≈ 5 minutes)
Outputs in data/s2/scenarios/.
"""
import copy
import json

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import s2_params as P
from s2_network import S2, build_network, km
from s2_outbreak import DAY0
from s2_siting import evaluate, solve, thin, time_matrix

OUTD = S2 / "scenarios"
OUTD.mkdir(exist_ok=True)
K_BASE = int(json.load(open(S2 / "summary.json"))["sites"])

# id, title, what changes, overrides
SCENARIOS = [
    ("baseline", "Baseline", "the settings in s2_params.py", {}),
    ("fast", "Faster access", "patients must reach a site within 45 min (not 1.5 h)", {"limit_h": 0.75}),
    ("rainy", "Rainy season", "travel times on rainy-season roads (tracks ×0.5, paths ×0.6)", {"rain": True}),
    ("isolation", "Strict isolation", "sites ≥ 2 km from villages (not 500 m)", {"MUST": {"min_settlement_distance_m": 2000}}),
    ("hospital", "Hospital-led", "SHOULD weight on 'near hospital' raised to 0.6", {"SHOULD": {"near_hospital": 0.6}, "score_w": 0.6}),
    ("community", "Community-first", "weights on community acceptance + waste downhill raised", {"SHOULD": {"community_acceptance": 0.35, "waste_downhill": 0.3, "near_hospital": 0.0}, "score_w": 0.6}),
    ("budget", "Tight budget", "only 2 treatment centres", {"K": 2}),
    ("early", "Early warning", "planning on 1 June 2014: demand for Jun–Aug only", {"plan": "2014-06-01", "window_d": 90}),
    ("border", "Cross-border", "weight on 'border flow' raised to 0.5", {"SHOULD": {"border_flow": 0.5}, "score_w": 0.6}),
]


def weights(over):
    w = dict(P.SHOULD)
    w.update(over or {})
    s = sum(w.values())
    return {k: v / s for k, v in w.items()}


def rescore(cand, w):
    c = cand.copy()
    c["score"] = sum(w[k] * c[f"s_{k}"] for k in w)
    return c


def demand(patches, plan=P.PLANNING_FROM, window_d=None):
    beds = np.load(S2 / "beds.npy")
    a = (pd.Timestamp(plan) - DAY0).days
    b = a + window_d if window_d else len(beds)
    return beds[a:b].max(0)


def run_one(net, patches, base_cand, sc):
    sid, title, what, o = sc
    if "MUST" in o:
        saved = copy.deepcopy(P.MUST)
        P.MUST.update(o["MUST"])
        cand = evaluate(net, patches, save=False)
        P.MUST.clear(); P.MUST.update(saved)
    else:
        cand = base_cand
    cand = rescore(cand, weights(o.get("SHOULD")))
    pool = thin(cand)
    T = time_matrix(net, patches, pool, rain=o.get("rain", False))
    d = demand(patches, o.get("plan", P.PLANNING_FROM), o.get("window_d"))
    K = o.get("K", K_BASE)
    limit = o.get("limit_h", P.MUST["max_patient_travel_h"])
    X, Y, status = solve(d, T, pool.score.values, K, limit, P.BEDS_PER_MODULE * P.MAX_MODULES_PER_SITE,
                         score_w=o.get("score_w", P.SCORE_WEIGHT))
    sites = pool[X].copy()
    sites["beds_demand"] = (Y[:, X] * d[:, None]).sum(0)
    sites["modules"] = np.maximum(1, np.ceil(sites.beds_demand / P.BEDS_PER_MODULE)).astype(int)
    cov = float((Y.sum(1) * d).sum() / d.sum())
    return {"id": sid, "title": title, "what": what, "coverage": cov, "K": K, "limit_h": limit,
            "candidates": int(cand.pass_all.sum()),
            "sites": sites[["lon", "lat", "beds_demand", "modules", "score"]].round(5).to_dict("records")}


def compare(res):
    base = res[0]["sites"]
    B = km([s["lon"] for s in base], [s["lat"] for s in base])
    for r in res:
        S = km([s["lon"] for s in r["sites"]], [s["lat"] for s in r["sites"]])
        d = cKDTree(B).query(S)[0]
        for s, di in zip(r["sites"], d):
            s["shift_km"] = round(float(di), 1)
            s["moved"] = bool(di > 2.0)
        r["sites_moved"] = int(sum(s["moved"] for s in r["sites"]))
    return res


def monte_carlo(net, patches, cand, n=200, seed=7):
    """Random SHOULD weights (Dirichlet) with a strong score weight; record where sites land."""
    rng = np.random.default_rng(seed)
    passing = cand[cand.pass_all].copy()
    T_all = time_matrix(net, patches, passing)
    col = {idx: k for k, idx in enumerate(passing.index)}
    d = demand(patches)
    keys = list(P.SHOULD)
    hits, covs, runs = np.zeros(len(passing)), [], []
    for run in range(n):
        w = dict(zip(keys, rng.dirichlet(np.ones(len(keys)))))
        pool = thin(rescore(cand, w))
        T = T_all[:, [col[i] for i in pool.index]]
        X, Y, _ = solve(d, T, pool.score.values, K_BASE, P.MUST["max_patient_travel_h"],
                        P.BEDS_PER_MODULE * P.MAX_MODULES_PER_SITE, score_w=0.6)
        for i in pool.index[X]:
            hits[col[i]] += 1
            runs.append((run, pool.at[i, "lon"], pool.at[i, "lat"]))
        covs.append(float((Y.sum(1) * d).sum() / d.sum()))
    pd.DataFrame(runs, columns=["run", "lon", "lat"]).to_csv(OUTD / "monte_carlo_runs.csv", index=False)
    # robustness zone: share of runs with a chosen site within 5 km of each candidate
    R = pd.DataFrame(runs, columns=["run", "lon", "lat"])
    tree = cKDTree(km(R.lon, R.lat))
    near = tree.query_ball_point(km(passing.lon, passing.lat), 5.0)
    passing["zone_share"] = [len(set(R.run.values[ix])) / n for ix in near]
    passing[["lon", "lat", "zone_share"]].to_csv(OUTD / "monte_carlo_zones.csv", index=False)
    passing["share_of_runs"] = hits / n
    out = passing[passing.share_of_runs > 0][["lon", "lat", "share_of_runs"]]
    out.to_csv(OUTD / "monte_carlo_sites.csv", index=False)
    json.dump({"runs": n, "coverage_min": min(covs), "coverage_median": float(np.median(covs)),
               "coverage_max": max(covs)}, open(OUTD / "monte_carlo_summary.json", "w"), indent=2)
    print(f"[s2d] Monte Carlo {n} runs: coverage {min(covs):.0%}–{max(covs):.0%}; zones with a site in ≥90% of runs: "
          f"{(passing.zone_share >= .9).sum()} candidate points")
    return out


def main():
    net = build_network()
    patches = pd.read_csv(S2 / "patches.csv")
    cand = pd.read_csv(S2 / "candidates.csv.gz")
    res = []
    for sc in SCENARIOS:
        r = run_one(net, patches, cand, sc)
        res.append(r)
        print(f"[s2d] {r['title']:<18} {len(r['sites'])} sites, coverage {r['coverage']:.0%}, candidates {r['candidates']}")
    res = compare(res)
    json.dump(res, open(OUTD / "scenarios.json", "w"), indent=1, ensure_ascii=False)
    for r in res:
        print(f"      {r['title']:<18} moved {r['sites_moved']}/{len(r['sites'])}")
    monte_carlo(net, patches, cand)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["mc"]:
        monte_carlo(build_network(), pd.read_csv(S2 / "patches.csv"), pd.read_csv(S2 / "candidates.csv.gz"))
    else:
        main()
