"""Step 2b — outbreak model, calibrated to 2014, turned into bed demand per patch.

Metapopulation SEIR on the patches. Patches are coupled by a gravity model on road travel time
(the mobility layer). Transmission can fall over time as behaviour changes and control starts:
    beta(t) = beta0 * (1 - c / (1 + exp(-(t - t_c) / 10)))
Fitted to the Guinea MoH cumulative cases by prefecture (Aug–Oct 2014) through a reporting rate rho.
"""
import json

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from config import OUT
import s2_params as P
from s2_network import S2

PREF_OBS = {"Gueckedou": "Gueckedou", "Macenta": "Macenta", "Kissidougou": "Kissidougou"}
DAY0 = pd.Timestamp(P.START_DATE)


def travel_matrix(net, patches):
    T = net.times(patches.node.values, limit=12)[:, patches.node.values]
    T = T + patches.walk_h.values[:, None] + patches.walk_h.values[None, :]
    np.fill_diagonal(T, 0)
    return T


def mobility(T, pop, m):
    W = pop[None, :] * np.exp(-T / P.MOBILITY_DECAY_H)
    np.fill_diagonal(W, 0)
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-12)
    return (1 - m) * np.eye(len(pop)) + m * W


def simulate(theta, T, pop, seed_idx, days, cut=None, cut_from=None, pref_idx=None, intro_idx=None):
    """Daily SEIR. Returns new symptomatic cases per day per patch, shape (days, n).

    theta = R0, c, t_c(Guéckédou), m, rho, t_c(Macenta), t_c(Kissidougou + rest), intro day (Macenta)
    pref_idx: 0 Guéckédou, 1 Macenta, 2 other (per patch). intro_idx: Macenta town patch.
    """
    R0, c, _, m = theta[:4]
    tcs = np.array([theta[2], theta[5], theta[6]])
    tc = tcs[pref_idx] if pref_idx is not None else np.full(len(pop), theta[2])
    intro_day = int(round(theta[7])) if len(theta) > 7 else None
    sig, gam = 1 / P.INCUBATION_D, 1 / P.INFECTIOUS_D
    M = mobility(T, pop, m)
    Neff = np.maximum(M.T @ pop, 1)
    S, E, I = pop.astype(float).copy(), np.zeros(len(pop)), np.zeros(len(pop))
    E[seed_idx] = 2.0
    out = np.zeros((days, len(pop)))
    for d in range(days):
        if intro_day is not None and d == intro_day and intro_idx is not None:
            E[intro_idx] += 2.0          # separate introduction (Macenta, spring 2014)
        bp = R0 * gam * (1 - c / (1 + np.exp(-(d - tc) / 10)))
        if cut is not None and d >= cut_from:
            bp = bp * cut
        lam = M @ ((M.T @ (I * bp)) / Neff)
        newE = np.minimum(S * lam, S)
        newI = sig * E
        S, E, I = S - newE, E + newE - newI, I + newI - gam * I
        out[d] = newI
    return out


def observations():
    c = pd.read_csv(OUT / "cases_study_area_2014.csv", parse_dates=["date"])
    c = c[c.area.isin(PREF_OBS)].dropna(subset=["cum_cases"])
    c["day"] = (c.date - DAY0).dt.days
    return c


def calibrate(T, patches, seed_idx):
    obs = observations()
    days = int(obs.day.max()) + 1
    pref = patches.prefecture.values
    pop = patches["pop"].values

    pidx, intro = _groups(patches)

    def resid(x):
        inc = simulate(x, T, pop, seed_idx, days, pref_idx=pidx, intro_idx=intro)
        cum = np.cumsum(inc, axis=0)
        r = []
        for area, g in obs.groupby("area"):
            model = x[4] * cum[g.day.values][:, pref == PREF_OBS[area]].sum(1)
            r.append(np.log1p(model) - np.log1p(g.cum_cases.values))
        return np.concatenate(r)

    #      R0    c    tcG  m      rho  tcM  tcK  introM
    lo = [1.05, 0.0, 60, P.MIN_MOBILITY_SHARE, P.REPORTING_RATE - 1e-6, 60, 60, 30]
    hi = [3.5, 0.98, 320, 0.3, P.REPORTING_RATE + 1e-6, 320, 320, 270]   # rho fixed (literature)
    starts = ([1.8, 0.6, 180, 0.02, P.REPORTING_RATE, 300, 300, 120], [2.2, 0.8, 150, 0.01, P.REPORTING_RATE, 310, 280, 90],
              [1.6, 0.5, 220, 0.05, P.REPORTING_RATE, 280, 320, 160])
    best = None
    for start in starts:
        f = least_squares(resid, start, bounds=(lo, hi), x_scale=[0.3, 0.2, 30, 0.02, 0.2, 30, 30, 30],
                          diff_step=0.02, max_nfev=600)
        if best is None or f.cost < best.cost:
            best = f
    rmse = float(np.sqrt(np.mean(best.fun ** 2)))
    names = ["R0", "control_strength", "control_midpoint_day_gueckedou", "mobility_share", "reporting_rate",
             "control_midpoint_day_macenta", "control_midpoint_day_other", "introduction_day_macenta"]
    fit = dict(zip(names, map(float, best.x)))
    for k in [k for k in fit if k.startswith(("control_midpoint_day", "introduction_day"))]:
        fit[k.replace("_day", "_date")] = str((DAY0 + pd.Timedelta(days=fit[k])).date())
    fit["rmse_log"] = rmse
    print(f"[s2b] calibrated: " + ", ".join(f"{k}={v:.3g}" if isinstance(v, float) else f"{k}={v}" for k, v in fit.items()))
    return best.x, fit, obs


def _groups(patches):
    pidx = np.where(patches.prefecture.values == "Gueckedou", 0,
                    np.where(patches.prefecture.values == "Macenta", 1, 2))
    intro = int(patches["pop"].where(patches.prefecture == "Macenta").idxmax())
    return pidx, intro


def bed_demand(inc):
    """Beds occupied per day per patch from daily symptomatic onsets."""
    adm = P.P_SEEK_CARE * inc
    k = np.ones(P.LENGTH_OF_STAY_D)
    beds = np.apply_along_axis(lambda a: np.convolve(a, k)[: len(a)], 0, adm)
    return adm, beds


def run(net, patches, reuse=True):
    T = travel_matrix(net, patches)
    seed_idx = int(np.argmin(np.hypot(patches.lon - -10.0645, patches.lat - 8.6224)))
    seed_idx = int(patches.pid[patches.settlement_idx == patches.settlement_idx.iloc[seed_idx]].iloc[0])
    st = pd.read_csv(S2 / "settlements_patches.csv")
    m = st[st.name == P.SEED_PLACE]
    if len(m):
        seed_idx = int(m.pid.iloc[0])
    print(f"[s2b] seed patch: {patches.name.iloc[seed_idx]} (contains {P.SEED_PLACE})")
    cache = S2 / "calibration.json"
    key = {k: getattr(P, k) for k in ("START_DATE", "INCUBATION_D", "INFECTIOUS_D", "MOBILITY_DECAY_H",
                                       "REPORTING_RATE", "MIN_MOBILITY_SHARE")}
    if reuse and cache.exists() and json.load(open(cache)).get("key") == key:
        c = json.load(open(cache))
        x, fit, obs = np.array(c["theta"]), c, observations()
        print("[s2b] reusing calibration (parameters unchanged)")
    else:
        x, fit, obs = calibrate(T, patches, seed_idx)
    days = (pd.Timestamp(P.HORIZON) - DAY0).days + 1
    pidx, intro = _groups(patches)
    inc = simulate(x, T, patches["pop"].values, seed_idx, days, pref_idx=pidx, intro_idx=intro)
    adm, beds = bed_demand(inc)
    plan0 = (pd.Timestamp(P.PLANNING_FROM) - DAY0).days
    patches = patches.copy()
    patches["peak_beds"] = beds[plan0:].max(0)
    patches["peak_day"] = beds[plan0:].argmax(0) + plan0
    patches["cases_after_planning"] = inc[plan0:].sum(0)
    np.save(S2 / "incidence.npy", inc)
    np.save(S2 / "beds.npy", beds)
    np.save(S2 / "travel_patches.npy", T)
    patches.to_csv(S2 / "patches.csv", index=False)
    fit = {k: v for k, v in fit.items() if k not in ("theta", "key", "seed_patch", "seed_idx", "day0")}
    json.dump({**fit, "seed_patch": patches.name.iloc[seed_idx], "seed_idx": seed_idx,
               "theta": list(map(float, x)), "day0": P.START_DATE, "key": key},
              open(S2 / "calibration.json", "w"), indent=2)
    tot = beds.sum(1)
    print(f"[s2b] region bed demand peaks at {tot.max():,.0f} on {(DAY0 + pd.Timedelta(days=int(tot.argmax()))).date()}; "
          f"top patches: {patches.nlargest(5, 'peak_beds')[['name', 'peak_beds']].round(0).values.tolist()}")
    return patches, x, T, seed_idx, obs


if __name__ == "__main__":
    from s2_network import build_network
    net = build_network()
    patches = pd.read_csv(S2 / "patches.csv")
    run(net, patches)
