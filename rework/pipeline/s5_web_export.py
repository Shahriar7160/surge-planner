"""Step 5 — export the data the web app needs (web/data/).

    python pipeline/s5_web_export.py

Writes:
  candidates.json   every candidate site that passed all MUST filters: SHOULD scores, hospital time, buildable land,
                    orientation on the map (towards the nearest road, incinerator downwind), nearest settlement
  patches.json      the 90 settlement patches of the outbreak model: population and modelled peak bed demand
  travel.json       road travel time candidate → patch in minutes, dry and rainy season: base64 of a uint8 matrix,
                    row-major (n_candidates × n_patches), 255 = more than 254 min
  layers.json       context for the map: study area, prefectures, main roads, hospitals, the 4 optimised sites
"""
import base64
import json
import math

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from config import OUT
import s2_params as P
import s4_params as G
from s2_network import build_network, km

S2 = OUT.parent / "s2"
WEB = OUT.parent.parent / "web" / "data"
WEB.mkdir(parents=True, exist_ok=True)
LAT0 = 8.615
MX, MY = 111320 * math.cos(math.radians(LAT0)), 110570
SHOULD = list(P.SHOULD)


def orientation(lon, lat, tree, pts):
    """Same rule as s4_run.orientation: road side faces the nearest road, incinerator downwind."""
    d, i = tree.query([lon * MX, lat * MY])
    vx, vy = (pts[i, 0] - lon) * MX, (pts[i, 1] - lat) * MY
    theta = math.atan2(vy, vx) + math.pi / 2
    down = math.radians(90 - (G.WIND_FROM_DEG + 180))
    inc_dir = math.atan2(math.sin(theta) + math.cos(theta), math.cos(theta) - math.sin(theta))
    return theta, math.cos(inc_dir - down) < 0, d


def main():
    cand = pd.read_csv(S2 / "candidates.csv.gz")
    cand = cand[cand.pass_all].reset_index(drop=True)
    patches = pd.read_csv(S2 / "patches.csv")
    sites = pd.read_csv(S2 / "sites.csv")
    settl = pd.read_csv(S2 / "settlements_patches.csv")
    named = settl[settl.type.isin(["city", "town", "village"]) & settl.name.notna()].reset_index(drop=True)

    # ---- travel times candidate → patch (minutes), dry and rainy
    net = build_network()
    nodes = cand.node.values
    out = {}
    for rain in (False, True):
        D = net.times(nodes, rain=rain, limit=4.3)[:, patches.node.values]
        T = (D + cand.walk_h.values[:, None] + patches.walk_h.values[None, :]) * 60
        T = np.where(np.isfinite(T), np.minimum(np.round(T), 255), 255).astype(np.uint8)
        out[rain] = T
    json.dump({"shape": list(out[False].shape), "unit": "minutes, 255 = more than 254",
               "dry": base64.b64encode(out[False].tobytes()).decode(), "rain": base64.b64encode(out[True].tobytes()).decode()},
              open(WEB / "travel.json", "w"))
    print(f"[s5] travel matrices {out[False].shape}, median to nearest patch "
          f"{np.median(out[False].min(axis=1)):.0f} min")

    # ---- orientation and nearest settlement
    roads = json.load(open(OUT / "osm2014" / "roads.geojson"))["features"]
    pts = np.vstack([np.asarray(f["geometry"]["coordinates"] if f["geometry"]["type"] == "LineString"
                                else f["geometry"]["coordinates"][0])
                     for f in roads if f["properties"].get("type") not in ("path", "footway", "pedestrian")])
    rtree = cKDTree(np.c_[pts[:, 0] * MX, pts[:, 1] * MY])
    ntree = cKDTree(km(named.lon, named.lat))
    dn, jn = ntree.query(km(cand.lon, cand.lat))
    stree = cKDTree(km(sites.lon, sites.lat))
    ds, js = stree.query(km(cand.lon, cand.lat))

    C = []
    for i, c in cand.iterrows():
        theta, mirror, road = orientation(c.lon, c.lat, rtree, pts)
        C.append({
            "id": i, "lon": round(c.lon, 5), "lat": round(c.lat, 5), "score": round(c.score, 3),
            "should": [round(float(c[f"s_{k}"]), 2) for k in SHOULD],
            "t_hospital_h": round(c.t_hospital_h, 2),
            "buildable_m2": round(float(c.s_burial_space) * math.pi * 300 ** 2),
            "rotation_deg": round(math.degrees(theta), 1), "mirrored": bool(mirror), "road_m": round(road),
            "near": named.name[jn[i]], "near_km": round(float(dn[i]), 1),
            "surge": sites.site_id[js[i]] if ds[i] < 0.3 else None,
        })
    # make sure each optimised site is exactly one candidate (the closest)
    for k, s in sites.iterrows():
        j = int(np.argmin(np.hypot((cand.lon - s.lon) * MX, (cand.lat - s.lat) * MY)))
        for c in C:
            if c["surge"] == s.site_id and c["id"] != j:
                c["surge"] = None
        C[j]["surge"] = s.site_id
        C[j]["near"] = s.near
    meta = {"should": SHOULD, "weights": [P.SHOULD[k] for k in SHOULD], "funnel": pd.read_csv(S2 / "filter_funnel.csv").to_dict("records"),
            "must": P.MUST, "max_modules_per_site": P.MAX_MODULES_PER_SITE}
    json.dump({"meta": meta, "candidates": C}, open(WEB / "candidates.json", "w"), separators=(",", ":"), allow_nan=False)

    Pt = [{"id": int(p.pid), "name": p["name"] if isinstance(p["name"], str) else f"unnamed {p.type}", "type": p.type, "lon": round(p.lon, 4), "lat": round(p.lat, 4),
           "pop": int(round(p["pop"])), "peak_beds": round(float(p.peak_beds), 1), "prefecture": p.prefecture if isinstance(p.prefecture, str) else None}
          for _, p in patches.iterrows()]
    json.dump(Pt, open(WEB / "patches.json", "w"), separators=(",", ":"), allow_nan=False)

    # ---- context layers
    adm = json.load(open(OUT / "admin_adm2.geojson"))
    adm["features"] = [f for f in adm["features"] if f["properties"]["iso"] == "GIN"]
    main_types = {"trunk", "primary", "secondary", "tertiary", "unclassified", "road"}

    def rnd(coords):
        return [[round(x, 4), round(y, 4)] for x, y in coords]
    rd = [{"type": "Feature", "properties": {"t": f["properties"].get("type")},
           "geometry": {"type": "LineString", "coordinates": rnd(f["geometry"]["coordinates"])}}
          for f in roads if f["properties"].get("type") in main_types and f["geometry"]["type"] == "LineString"]
    hf = json.load(open(OUT / "health_facilities.geojson"))
    hosp = [f for f in hf["features"] if f["properties"].get("level", 9) >= 3 or "hospital" in str(f["properties"].get("kind"))]
    briefs = {b["site_id"]: b for b in json.load(open(S2.parent / "s3" / "briefs.json"))["sites"]}
    S = [{"site_id": s.site_id, "near": s.near, "lon": s.lon, "lat": s.lat, "beds": int(s.beds),
          "peak_confirmed_beds": briefs[s.site_id]["peak_confirmed_beds"]} for _, s in sites.iterrows()]
    json.dump({"prefectures": adm, "roads": {"type": "FeatureCollection", "features": rd},
               "hospitals": {"type": "FeatureCollection", "features": hosp}, "sites": S},
              open(WEB / "layers.json", "w"), separators=(",", ":"))
    print(f"[s5] wrote {WEB}: {len(C)} candidates, {len(Pt)} patches, {len(rd)} road lines, {len(hosp)} hospitals")


if __name__ == "__main__":
    main()
