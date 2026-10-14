"""Prototype computations for the mockup. Everything here is ILLUSTRATIVE:
population is a proxy by settlement type, the outbreak model is uncalibrated,
and road speeds are assumptions. The mockup marks each of these as a TODO.

Outputs build/out.json consumed by render.py.
"""
import heapq
import json
import math
from collections import defaultdict

import numpy as np

from geo import BBOX, load_all

R_EARTH = 6371.0
LAT0 = (BBOX[1] + BBOX[3]) / 2
KX = math.cos(math.radians(LAT0)) * 111.32  # km per degree lon
KY = 110.57                                  # km per degree lat

SPEED = {  # km/h assumptions, 2014 rainy-season-ish
    "trunk": 50, "primary": 45, "secondary": 35, "tertiary": 28, "road": 20,
    "unclassified": 20, "residential": 15, "service": 12, "track": 10,
    "path": 4, "footway": 4, "steps": 2,
}
WALK = 4.0
POP_PROXY = {"city": 60000, "town": 8000, "suburb": 3000, "village": 1200,
             "neighbourhood": 1500, "hamlet": 180, "locality": 150,
             "isolated_dwellin": 20}


def km(a, b):
    return math.hypot((a[0] - b[0]) * KX, (a[1] - b[1]) * KY)


def build_graph(roads):
    nid, coords, adj = {}, [], defaultdict(list)

    def node(p):
        k = (round(p[0], 4), round(p[1], 4))  # ~11 m snap so segments join
        if k not in nid:
            nid[k] = len(coords)
            coords.append(k)
        return nid[k]

    for row, parts in roads:
        v = SPEED.get(row.get("type", ""), 8)
        for part in parts:
            prev = None
            for p in part:
                n = node(p)
                if prev is not None and prev != n:
                    h = km(coords[prev], coords[n]) / v
                    adj[prev].append((n, h))
                    adj[n].append((prev, h))
                prev = n
    return np.array(coords), adj


def main_component(adj, n):
    best = set()
    seen = set()
    for s in range(n):
        if s in seen or not adj[s]:
            continue
        comp, stack = {s}, [s]
        while stack:
            u = stack.pop()
            for v, _ in adj[u]:
                if v not in comp:
                    comp.add(v)
                    stack.append(v)
        seen |= comp
        if len(comp) > len(best):
            best = comp
    return best


def snap(coords, pts, allowed=None):
    """Nearest graph node (in the connected network) for each point via a grid hash."""
    cell = 0.02
    grid = defaultdict(list)
    for i, (x, y) in enumerate(coords):
        if allowed is None or i in allowed:
            grid[(int(x / cell), int(y / cell))].append(i)
    out = []
    for x, y in pts:
        gx, gy = int(x / cell), int(y / cell)
        best, bd = None, 1e9
        r = 1
        while best is None or r <= 2:
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for i in grid.get((gx + dx, gy + dy), ()):
                        d = km(coords[i], (x, y))
                        if d < bd:
                            best, bd = i, d
            r += 1
            if r > 25:
                break
        out.append((best, bd / WALK))
    return out


def dijkstra(adj, sources, cutoff=1e9):
    """sources: list of (node, start_time, label). Returns dist, label arrays (dicts)."""
    dist, lab = {}, {}
    pq = [(t, n, l) for n, t, l in sources]
    heapq.heapify(pq)
    while pq:
        t, n, l = heapq.heappop(pq)
        if n in dist or t > cutoff:
            continue
        dist[n], lab[n] = t, l
        for m, h in adj[n]:
            if m not in dist:
                heapq.heappush(pq, (t + h, m, l))
    return dist, lab


def main():
    L = load_all()
    print("graph...")
    coords, adj = build_graph(L["roads"])
    comp = main_component(adj, len(coords))
    print(" nodes", len(coords), "main component", len(comp))

    places = [(r, p[0][0]) for r, p in L["places"]
              if r["type"] in POP_PROXY]
    pts = [p for _, p in places]
    pop = np.array([float(r["population"]) if r["population"].isdigit()
                    and r["type"] in ("city", "town") else POP_PROXY[r["type"]]
                    for r, _ in places])
    snaps = snap(coords, pts, comp)

    # ---- 1. catchments: 3 cities, Euclidean (2015) vs network time (rework)
    cities = [i for i, (r, _) in enumerate(places) if r["type"] == "city"]
    city_names = [places[i][0]["name"] for i in cities]
    eu = [min(range(len(cities)), key=lambda c: km(p, pts[cities[c]])) for p in pts]
    dist, lab = dijkstra(adj, [(snaps[c][0], snaps[c][1], k) for k, c in enumerate(cities)])
    nw, tt = [], []
    for (n, w) in snaps:
        nw.append(lab.get(n, -1))
        tt.append(dist.get(n, float("nan")) + w)
    moved = sum(1 for a, b in zip(eu, nw) if b >= 0 and a != b)
    unreached = sum(1 for b in nw if b < 0)
    print(" reassigned", moved, "of", len(pts), "unreached", unreached)

    # ---- 2. patches (towns/villages/cities) for the outbreak model
    pidx = [i for i, (r, _) in enumerate(places)
            if r["type"] in ("city", "town", "village", "suburb")]
    print(" patches", len(pidx))
    d_p, l_p = dijkstra(adj, [(snaps[i][0], snaps[i][1], k) for k, i in enumerate(pidx)])
    member = [l_p.get(n, -1) for n, _ in snaps]
    P = np.zeros(len(pidx))
    for i, m in enumerate(member):
        if m >= 0:
            P[m] += pop[i]
    # travel time matrix between patches (cutoff 10h)
    T = np.full((len(pidx), len(pidx)), np.inf)
    node_of = [snaps[i][0] for i in pidx]
    for a, i in enumerate(pidx):
        d, _ = dijkstra(adj, [(snaps[i][0], snaps[i][1], 0)], cutoff=10)
        for b, n in enumerate(node_of):
            if n in d:
                T[a, b] = d[n] + snaps[pidx[b]][1]
    np.fill_diagonal(T, 0)

    # gravity mobility: w_ij ~ P_j * exp(-t/2h); 92% of contact stays home
    W = P[None, :] * np.exp(-T / 2.0)
    np.fill_diagonal(W, 0)
    W = W / np.maximum(W.sum(1, keepdims=True), 1e-9)
    M = 0.92 * np.eye(len(P)) + 0.08 * W

    # SEIR, daily, R0 = 1.7 (lit. 1.5-2.0), incubation 9.4 d, infectious 7.4 d
    R0, sig, gam = 1.7, 1 / 9.4, 1 / 7.4
    gk = min(range(len(pidx)), key=lambda k: abs(pts[pidx[k]][0] + 10.13) + abs(pts[pidx[k]][1] - 8.56))
    seed_name = places[pidx[gk]][0]["name"]
    weeks = 52

    def seir(cut=None):
        """cut: per-patch transmission multiplier applied from week 10 (response)."""
        S, E, I = P.copy(), np.zeros_like(P), np.zeros_like(P)
        I[gk] = 3
        out = []
        for day in range(weeks * 7):
            b = R0 * gam * (cut if (cut is not None and day >= 70) else 1.0)
            Ieff = M.T @ (I * b)
            Neff = np.maximum(M.T @ P, 1)
            newE = S * (M @ (Ieff / Neff))
            newI, newR = sig * E, gam * I
            S, E, I = S - newE, E + newE - newI, I + newI - newR
            if day % 7 == 6:
                out.append(I.copy())
        return np.array(out)

    prev_w = seir()
    beds = 0.6 * prev_w.sum(1)            # assume 60% of infectious seek a bed
    print(" seed", seed_name, "peak beds", beds.max(), "week", beds.argmax())

    # ---- 3. siting: greedy max-coverage on patch nodes until 95% of demand covered
    peak = 0.6 * prev_w.max(0)            # bed demand per patch at its own peak
    cover_h, cap_mod = 1.5, 8
    covered = np.zeros(len(pidx), bool)
    sites = []
    while peak[covered].sum() < 0.95 * peak.sum() and len(sites) < 20:
        best = max(range(len(pidx)), key=lambda c: peak[(T[c] <= cover_h) & ~covered].sum())
        reach = (T[best] <= cover_h) & ~covered
        covered |= reach
        sites.append({"patch": int(best), "demand": float(peak[reach].sum()),
                      "reach": [int(k) for k in np.where(reach)[0]]})
    k_sites = len(sites)
    opt_cov = peak[covered].sum() / peak.sum()
    t_opt = T[[s_["patch"] for s_ in sites]].min(0)

    # response scenario: patches within reach of a site get isolation (-60% transmission)
    cut = np.where(covered, 0.4, 1.0)
    prev_r = seir(cut)
    beds_r = 0.6 * prev_r.sum(1)
    for s_ in sites:  # size each site from its catchment's peak bed demand under response
        s_["beds"] = float(0.6 * prev_r[:, s_["reach"]].sum(1).max())
        s_["modules"] = int(max(1, math.ceil(s_["beds"] / 12)))
    print(" modules per site", [(places[pidx[s_['patch']]][0]['name'], s_['modules']) for s_ in sites])

    # 2015 baseline: regular grid, one module per 500 km^2 (~22.4 km spacing)
    sp = math.sqrt(500)
    gx = np.arange(BBOX[0] + sp / KX / 2, BBOX[2], sp / KX)
    gy = np.arange(BBOX[1] + sp / KY / 2, BBOX[3], sp / KY)
    grid_pts = [(x, y) for x in gx for y in gy]
    gs = snap(coords, grid_pts, comp)
    dg, _ = dijkstra(adj, [(n, w, 0) for n, w in gs], cutoff=12)
    t_grid = np.array([dg.get(snaps[i][0], np.inf) + snaps[i][1] for i in pidx])
    grid_cov = peak[t_grid <= cover_h].sum() / peak.sum()
    wmean = lambda t: float((np.minimum(t, 12) * peak).sum() / peak.sum())
    print(f" coverage opt {opt_cov:.2f} with {k_sites} sites (mean {wmean(t_opt):.2f}h);"
          f" grid {grid_cov:.2f} with {len(grid_pts)} units (mean {wmean(t_grid):.2f}h)")
    print(" peak beds unmitigated", beds.max(), "with response", beds_r.max())

    out = {
        "bbox": BBOX, "kx": KX, "ky": KY,
        "roads": [[r.get("type", ""), [[round(x, 4), round(y, 4)] for x, y in part]]
                  for r, parts in L["roads"] for part in parts],
        "water": [[r.get("type", ""), [[round(x, 4), round(y, 4)] for x, y in part]]
                  for r, parts in L["waterways"] for part in parts],
        "forest": [[[round(x, 3), round(y, 3)] for x, y in part[::2]]
                   for r, parts in L["natural"] if r.get("type") == "forest" for part in parts],
        "resid": [[[round(x, 4), round(y, 4)] for x, y in part]
                  for r, parts in L["landuse"] if r.get("type") == "residential" for part in parts],
        "cell": [p[0][0] for _, p in L["cell"]],
        "places": [{"n": r["name"], "t": r["type"], "x": p[0], "y": p[1], "pop": float(pop[i]),
                    "eu": eu[i], "nw": nw[i], "tt": tt[i] if tt[i] == tt[i] else None,
                    "patch": member[i]}
                   for i, (r, p) in enumerate(places)],
        "cities": city_names,
        "moved": moved, "n_places": len(pts),
        "patches": [{"n": places[i][0]["name"], "x": pts[i][0], "y": pts[i][1], "P": float(P[k]),
                     "peak": float(peak[k])} for k, i in enumerate(pidx)],
        "prev": prev_w.round(2).tolist(), "beds": beds.round(1).tolist(),
        "beds_r": beds_r.round(1).tolist(), "t_opt_mean": wmean(t_opt), "t_grid_mean": wmean(t_grid),
        "seed": seed_name,
        "sites": sites, "opt_cov": opt_cov, "grid_cov": grid_cov,
        "grid_pts": grid_pts, "n_grid": len(grid_pts), "k_sites": k_sites, "cover_h": cover_h,
    }
    with open("out.json", "w") as f:
        json.dump(out, f)


if __name__ == "__main__":
    main()
