"""Step 2c — location: candidate grid -> MUST filters -> SHOULD scores -> optimisation.

Optimisation is a capacitated maximal covering location problem (MILP, solved with HiGHS):
  maximise  sum_ij demand_i * y_ij  +  w * sum_j score_j * x_j
  s.t.      sum_j y_ij <= 1                 each patch served at most once
            y_ij <= x_j                     only by an open site
            y_ij = 0 if time_ij > limit     within the patient travel limit (MUST #3)
            sum_i demand_i * y_ij <= cap * x_j
            sum_j x_j <= K                  number of treatment centres
"""
import json

import numpy as np
import pandas as pd
import rasterio
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape

from config import BBOX, OUT
import s2_params as P
from s2_network import KX, KY, S2, km

LC_TREE, LC_GRASS = 10, 30


def _densify(lines, step_km=0.05):
    pts = []
    for coords in lines:
        a = np.asarray(coords)
        for p, q in zip(a[:-1], a[1:]):
            n = max(1, int(np.hypot((q[0] - p[0]) * KX, (q[1] - p[1]) * KY) / step_km))
            t = np.linspace(0, 1, n, endpoint=False)[:, None]
            pts.append(p + t * (q - p))
        pts.append(a[-1:])
    return np.vstack(pts)


def _lines(path, types=None):
    out = []
    for f in json.load(open(path))["features"]:
        if types and f["properties"].get("type") not in types:
            continue
        g = f["geometry"]
        for part in (g["coordinates"] if g["type"].startswith("Multi") else [g["coordinates"]]):
            if g["type"].endswith("Polygon"):
                part = part[0]
            out.append(part)
    return out


class Rasters:
    def __init__(self):
        self.slope = rasterio.open(OUT / "slope_pct_x10_90m.tif")
        self.S = self.slope.read(1) / 10
        self.LC = rasterio.open(OUT / "landcover_worldcover2021_90m.tif").read(1)
        self.DEM = rasterio.open(OUT / "elevation_cop30_90m.tif").read(1).astype(float)
        self.tr = self.slope.transform
        self.lc_ok = ~np.isin(self.LC, P.MUST["exclude_landcover"])
        if P.MUST["exclude_tree_cover"]:
            self.lc_ok &= self.LC != LC_TREE
        self.ok = (self.S < P.MUST["max_slope_pct"]) & self.lc_ok

    def rc(self, lon, lat):
        r, c = rasterio.transform.rowcol(self.tr, lon, lat)
        r = np.clip(np.asarray(r), 0, self.S.shape[0] - 1)
        c = np.clip(np.asarray(c), 0, self.S.shape[1] - 1)
        return r, c

    def window_mean(self, arr, lon, lat, radius_m):
        k = max(1, int(round(radius_m / 90)))
        from scipy.ndimage import uniform_filter
        f = uniform_filter(arr.astype(float), size=2 * k + 1, mode="nearest")
        r, c = self.rc(lon, lat)
        return f[r, c]


def candidates():
    gin = [shape(f["geometry"]) for f in json.load(open(OUT / "admin_adm0.geojson"))["features"]
           if f["properties"]["iso"] == "GIN"][0]
    dx, dy = P.CANDIDATE_SPACING_M / 1000 / KX, P.CANDIDATE_SPACING_M / 1000 / KY
    xs, ys = np.meshgrid(np.arange(BBOX[0] + dx / 2, BBOX[2], dx), np.arange(BBOX[1] + dy / 2, BBOX[3], dy))
    c = pd.DataFrame({"lon": xs.ravel(), "lat": ys.ravel()})
    from shapely import contains_xy
    c = c[contains_xy(gin, c.lon.values, c.lat.values)].reset_index(drop=True)
    return c


def evaluate(net, patches, facilities_file="health_facilities.geojson", save=True):
    R = Rasters()
    c = candidates()
    n0 = len(c)
    r, cc = R.rc(c.lon.values, c.lat.values)
    pts = km(c.lon, c.lat)

    # ---------------- MUST filters
    rivers = _densify(_lines(OUT / "osm2014" / "waterways.geojson", {"river", "stream"}))
    d_water = cKDTree(km(rivers[:, 0], rivers[:, 1])).query(pts)[0]
    st = pd.read_csv(S2 / "settlements_patches.csv")
    big = st[st.type.isin(["city", "town", "village", "suburb", "neighbourhood"])]
    small = st[~st.index.isin(big.index)]
    d_big = cKDTree(km(big.lon, big.lat)).query(pts)[0]
    d_small = cKDTree(km(small.lon, small.lat)).query(pts)[0]
    resid = _densify(_lines(OUT / "osm2014" / "landuse.geojson", {"residential"}), 0.1)
    d_resid = cKDTree(km(resid[:, 0], resid[:, 1])).query(pts)[0]
    truck_nodes = np.intersect1d(np.where(net.truck)[0], net.main)
    d_road = cKDTree(km(net.xy[truck_nodes, 0], net.xy[truck_nodes, 1])).query(pts)[0]
    c["node"], c["walk_h"] = net.snap(c.lon, c.lat)

    fac = json.load(open(OUT / facilities_file))["features"]
    hos = [f["geometry"]["coordinates"] for f in fac if f["properties"].get("kind") == "hospital"]
    hn, hw = net.snap([h[0] for h in hos], [h[1] for h in hos])
    t_hos, _ = net.nearest(hn, hw)
    c["t_hospital_h"] = t_hos[c.node.values] + c.walk_h
    buildable = R.window_mean(R.ok, c.lon.values, c.lat.values, 150) * (2 * 2 + 1) ** 2

    M = P.MUST
    tests = {
        "slope": R.S[r, cc] < M["max_slope_pct"],
        "land cover (water, wetland, forest)": R.lc_ok[r, cc],
        "flood (near river)": d_water * 1000 >= M["min_river_distance_m"],
        "isolation from settlements": (d_big * 1000 >= M["min_settlement_distance_m"])
                                      & (d_small * 1000 >= M["min_settlement_distance_m"] / 2)
                                      & (d_resid * 1000 >= M["min_settlement_distance_m"] / 2),
        "truck access": d_road * 1000 <= M["max_road_distance_m"],
        "water supply": d_water * 1000 <= M["max_water_distance_m"],
        "lab reach": c.t_hospital_h.values <= M["max_lab_travel_h"],
        "buildable area": buildable >= M["min_buildable_cells"],
    }
    funnel, keep = [("candidates (500 m grid, Guinea)", n0)], np.ones(n0, bool)
    for k, v in tests.items():
        keep &= v
        funnel.append((k, int(keep.sum())))
        c[f"pass_{k.split(' ')[0]}"] = v
    c["pass_all"] = keep

    # ---------------- SHOULD scores (0..1)
    towers = np.array([f["geometry"]["coordinates"] for f in
                       json.load(open(OUT / "osm2014" / "cell_towers.geojson"))["features"]])
    d_tower = cKDTree(km(towers[:, 0], towers[:, 1])).query(pts)[0] if len(towers) else np.full(n0, 99)
    border = [shape(f["geometry"]).boundary for f in json.load(open(OUT / "admin_adm0.geojson"))["features"]
              if f["properties"]["iso"] in ("SLE", "LBR")]
    bpts = np.vstack([np.asarray(b.coords) if b.geom_type == "LineString"
                      else np.vstack([np.asarray(g.coords) for g in b.geoms]) for b in border])
    d_border = cKDTree(km(bpts[:, 0], bpts[:, 1])).query(pts)[0]
    town_nodes = patches[patches.type.isin(["city", "town"])]
    t_town, _ = net.nearest(town_nodes.node.values, town_nodes.walk_h.values)
    t_town_r, _ = net.nearest(town_nodes.node.values, town_nodes.walk_h.values, rain=True)
    tt, ttr = t_town[c.node.values] + c.walk_h, t_town_r[c.node.values] + c.walk_h
    grass_flat = (R.LC == LC_GRASS) & (R.S < 3)
    elev = R.DEM[r, cc]
    se = R.DEM[R.rc(st.lon.values, st.lat.values)]
    stree = cKDTree(km(st.lon, st.lat))
    near = stree.query_ball_point(pts, 3.0)
    up = np.array([np.mean(se[i]) - e if len(i) else 0 for i, e in zip(near, elev)])
    clip = lambda a: np.clip(a, 0, 1)
    S = {
        "cell_coverage": clip(1 - d_tower / 15),
        "near_hospital": clip(1 - (c.t_hospital_h.values - 0.25) / 1.75),
        "helipad_space": clip(R.window_mean(grass_flat, c.lon.values, c.lat.values, 300) / 0.5),
        "rainy_access": clip(tt / np.maximum(ttr, 1e-6)),
        "border_flow": clip(1 - d_border / 30),
        "waste_downhill": clip(0.5 + up / 40),
        "burial_space": clip(R.window_mean(R.ok, c.lon.values, c.lat.values, 300)),
        "community_acceptance": clip(1 - R.window_mean(R.LC == LC_TREE, c.lon.values, c.lat.values, 300)),
        "fuel_supply": clip(1 - tt / 1.5),
    }
    for k, v in S.items():
        c[f"s_{k}"] = np.nan_to_num(v)
    c["score"] = sum(P.SHOULD[k] * c[f"s_{k}"] for k in P.SHOULD)
    if not save:
        return c
    out = c.copy()
    num = out.select_dtypes("float").columns
    out[num] = out[num].round(4)
    out[["lon", "lat"]] = c[["lon", "lat"]].round(5)
    out.to_csv(S2 / "candidates.csv.gz", index=False)
    pd.DataFrame(funnel, columns=["filter", "remaining"]).to_csv(S2 / "filter_funnel.csv", index=False)
    print("[s2c] MUST filter funnel: " + " → ".join(f"{k} {v:,}" for k, v in funnel))

    return c


def thin(c, cell_km=2.0):
    """Keep the best-scoring passing candidate per 2 km cell (sites need spacing anyway)."""
    p = c[c.pass_all].copy()
    p["cell"] = list(zip((p.lon * KX // cell_km).astype(int), (p.lat * KY // cell_km).astype(int)))
    return p.sort_values("score", ascending=False).groupby("cell").head(1)


def time_matrix(net, patches, cand, limit=4.0, rain=False):
    D = net.times(patches.node.values, rain=rain, limit=limit)[:, cand.node.values]
    return D + patches.walk_h.values[:, None] + cand.walk_h.values[None, :]


def solve(demand, T, score, K, limit_h, cap_beds, score_w=P.SCORE_WEIGHT):
    """Capacitated maximal covering MILP, solved with HiGHS through scipy.optimize.milp."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import coo_matrix
    I, J = T.shape
    ii, jj = np.where((T <= limit_h) & (demand[:, None] > 0))
    nP = len(ii)
    nv = J + nP                                   # [x_0..x_J-1, y_0..y_nP-1]
    scale = demand.sum() / max(K, 1)
    c = -np.r_[score_w * scale * score, demand[ii]]
    rows, cols, vals, lo, hi = [], [], [], [], []
    r = 0
    for i in np.unique(ii):                       # each patch served at most once
        k = np.where(ii == i)[0]
        rows += [r] * len(k); cols += list(J + k); vals += [1] * len(k); lo.append(-np.inf); hi.append(1); r += 1
    for k in range(nP):                           # y_ij <= x_j
        rows += [r, r]; cols += [J + k, jj[k]]; vals += [1, -1]; lo.append(-np.inf); hi.append(0); r += 1
    for j in np.unique(jj):                       # capacity
        k = np.where(jj == j)[0]
        rows += [r] * (len(k) + 1); cols += list(J + k) + [j]; vals += list(demand[ii[k]]) + [-cap_beds]
        lo.append(-np.inf); hi.append(0); r += 1
    rows += [r] * J; cols += list(range(J)); vals += [1] * J; lo.append(-np.inf); hi.append(K); r += 1
    A = coo_matrix((vals, (rows, cols)), shape=(r, nv)).tocsr()
    integrality = np.r_[np.ones(J), np.zeros(nP)]
    res = milp(c, constraints=LinearConstraint(A, lo, hi), integrality=integrality,
               bounds=Bounds(0, 1), options={"time_limit": 120, "mip_rel_gap": 1e-3})
    X = res.x[:J] > 0.5 if res.x is not None else np.zeros(J, bool)
    Y = np.zeros((I, J))
    if res.x is not None:
        Y[ii, jj] = res.x[J:]
    return X, Y, res.message.split(".")[0]


def place(net, patches, cand, K=P.MAX_SITES, limit_h=P.MUST["max_patient_travel_h"], T=None):
    pool = thin(cand)
    T = time_matrix(net, patches, pool) if T is None else T
    d = patches.peak_beds.values
    cap = P.BEDS_PER_MODULE * P.MAX_MODULES_PER_SITE
    X, Y, status = solve(d, T, pool.score.values, K, limit_h, cap)
    sites = pool[X].copy()
    served = (Y[:, X] * d[:, None])
    sites["beds_demand"] = served.sum(0)
    sites["modules"] = np.maximum(1, np.ceil(sites.beds_demand / P.BEDS_PER_MODULE)).astype(int)
    sites["beds"] = sites.modules * P.BEDS_PER_MODULE
    sites["patches_served"] = (Y[:, X] > 0.01).sum(0)
    sites["people_served"] = (Y[:, X] * patches["pop"].values[:, None]).sum(0)
    cov = float((Y.sum(1) * d).sum() / d.sum())
    return sites, Y[:, X], cov, status, pool, T


def grid_baseline(net, patches, limit_h):
    """The 2015 method: one unit per 500 km² cell on a regular grid."""
    sp = np.sqrt(500)
    gx = np.arange(BBOX[0] + sp / KX / 2, BBOX[2], sp / KX)
    gy = np.arange(BBOX[1] + sp / KY / 2, BBOX[3], sp / KY)
    g = pd.DataFrame([(x, y) for x in gx for y in gy], columns=["lon", "lat"])
    from shapely import contains_xy
    gin = [shape(f["geometry"]) for f in json.load(open(OUT / "admin_adm0.geojson"))["features"]
           if f["properties"]["iso"] == "GIN"][0]
    g = g[contains_xy(gin, g.lon.values, g.lat.values)].reset_index(drop=True)
    g["node"], g["walk_h"] = net.snap(g.lon, g.lat)
    t, _ = net.nearest(g.node.values, g.walk_h.values)
    tp = t[patches.node.values] + patches.walk_h.values
    d = patches.peak_beds.values
    return g, float(d[tp <= limit_h].sum() / d.sum())
