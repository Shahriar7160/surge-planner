"""Step 1b — repair the health-facility layer, then test how much the repair matters.

The MoH list (data/user/structures_de_sante_guinee_vf.csv) has holes: 666 rows without
coordinates, and the Guéckédou prefectural hospital is missing. Three passes fill them,
and every facility records how its location was obtained (`location_source`):

  MoH                    coordinates from the Ministry of Health list
  village_match          name matched to exactly one OSM 2014 place in the same prefecture
  town_centre            prefectural hospital placed at its town's OSM point (approximate)
  synthetic              no match: placed by rule at the largest settlement in the same
                         prefecture with no facility within 5 km (scenario data, not observed)

Then a sensitivity check compares distance-to-care surfaces with and without the repair.

Run:  python pipeline/s1_facilities.py
"""
import json
import re
import unicodedata

import numpy as np
import pandas as pd
import rasterio
import shapefile
from scipy.spatial import cKDTree
from shapely.geometry import Point, shape

from config import BBOX, OUT, RAW, REFS, ROOT
from s1_fetch import _level, _read_text_table, write_raster

STUDY_PREFS = ["GUECKEDOU", "MACENTA", "KISSIDOUGOU", "KEROUANE"]
STOP = {"ps", "psr", "csr", "csu", "csur", "cs", "csa", "cmc", "de", "du", "la", "le", "les", "centre", "clinique",
        "clinic", "cabinet", "cab", "soins", "privee", "prive", "sante", "poste", "hopital", "hp", "h", "ajout",
        "agbef", "petite", "soeur", "guinee", "maternite", "infirmerie", "ong", "dispensaire", "catholic",
        "catholique", "sainte", "marie", "bon", "samaritain", "medical", "medicale", "urbain", "rural"}
# Prefectural hospitals the list should contain (one per prefecture capital in the study area)
REQUIRED_HOSPITALS = {"GUECKEDOU": ("Hôpital Préfectoral de Guéckédou", "Guéckédou"),
                      "MACENTA": ("Hôpital Préfectoral de Macenta", "Macenta"),
                      "KISSIDOUGOU": ("Hôpital Préfectoral de Kissidougou", "Kissidougou")}
SYNTH_GAP_KM = 5.0

LAT0 = (BBOX[1] + BBOX[3]) / 2
KX, KY = 111.32 * np.cos(np.radians(LAT0)), 110.57


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


def words(name):
    return [norm(w) for w in re.split(r"[\s\-'’.,/()]+", str(name)) if norm(w) and norm(w) not in STOP]


def log(msg):
    print(f"[s1b] {msg}", flush=True)


def load_moh():
    src = ROOT / "data" / "user" / "structures_de_sante_guinee_vf.csv"
    df, enc = _read_text_table(src)
    df = df.rename(columns={"Nom": "name", "PREFECTURE": "prefecture", "Latitude": "lat", "Longiture": "lon",
                            "CODE": "code"})
    for c in ("lat", "lon"):
        df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
    df["name"] = df["name"].str.strip()
    df["prefecture"] = df["prefecture"].str.strip().str.upper()
    df["location_source"] = np.where(df[["lat", "lon"]].notna().all(axis=1), "MoH", None)
    log(f"MoH list ({enc}): {len(df)} rows, {df.location_source.isna().sum()} without coordinates")
    return df


def prefecture_shapes():
    feats = json.load(open(RAW / "geoBoundaries-GIN-ADM2.geojson"))["features"]
    return {norm(f["properties"]["shapeName"]).upper(): shape(f["geometry"]) for f in feats}


def osm_places():
    """All 2014 OSM places in Guinea (not just the window), for name matching."""
    r = shapefile.Reader(str(REFS / "places" / "places.shp"), encoding="utf-8", encodingErrors="ignore")
    names = [f[0] for f in r.fields[1:]]
    out = []
    for sr in r.iterShapeRecords():
        p = dict(zip(names, sr.record))
        if sr.shape.points and p.get("name"):
            x, y = sr.shape.points[0]
            out.append({"name": p["name"], "key": norm(p["name"]), "type": p["type"], "x": x, "y": y})
    return pd.DataFrame(out)


def repair(df, prefs, places):
    rep = []  # report rows
    # pass 1 — village name match, unique within the facility's prefecture
    for i, r in df[df.location_source.isna() & df.prefecture.isin(STUDY_PREFS)].iterrows():
        poly = prefs.get(norm(r.prefecture).upper())
        hits = []
        for w in words(r["name"]):
            c = places[places.key == w]
            if poly is not None:
                c = c[[poly.contains(Point(x, y)) for x, y in zip(c.x, c.y)]]
            if len(c) == 1:
                hits.append(c.iloc[0])
        if hits:
            h = hits[0]
            df.loc[i, ["lon", "lat", "location_source"]] = [h.x, h.y, "village_match"]
            rep.append((r["name"], r.prefecture, "village_match", f"{h['name']} ({h.type})"))
        else:
            rep.append((r["name"], r.prefecture, "unmatched", ""))

    # drop exact duplicates created by matching onto an existing facility of the same village
    df = df.drop_duplicates(subset=["name", "lat", "lon"])

    # pass 2 — required prefectural hospitals
    for pref, (hname, town) in REQUIRED_HOSPITALS.items():
        have = df[(df.prefecture == pref) & df["name"].map(lambda n: _level(n)[0] == "hospital")
                  & df.lat.notna()]
        if len(have):
            continue
        t = places[(places.key == norm(town)) & places.type.isin(["city", "town"])].iloc[0]
        df.loc[len(df) + 10_000] = {"name": hname, "prefecture": pref, "lat": t.y, "lon": t.x, "code": None,
                                    "location_source": "town_centre"}
        rep.append((hname, pref, "town_centre", f"{town} town point (OSM 2014)"))
    return df, rep


PREF_TOWN = {"GUECKEDOU": "Guéckédou", "MACENTA": "Macenta", "KISSIDOUGOU": "Kissidougou", "KEROUANE": "Kérouané"}
URBAN = {"private_clinic", "other"}


def _is_urban(name):
    kind = _level(name)[0]
    return kind in URBAN or bool(re.match(r"^\s*(csu|cmc)\b", str(name).lower()))


def _ring(x, y, key, r_min=0.5, r_max=1.8):
    """Deterministic point 0.5–1.8 km from a town centre, angle and radius taken from the name."""
    h = int.from_bytes(key.encode()[:8].ljust(8, b"_"), "little") * 2654435761 % 2**32
    ang = (h % 3600) / 3600 * 2 * np.pi
    rad = r_min + (h // 3600 % 1000) / 1000 * (r_max - r_min)
    return x + rad * np.cos(ang) / KX, y + rad * np.sin(ang) / KY


def synthesise(df, rep, places):
    """Pass 3 — scenario placement for facilities that could not be located.

    Urban facilities (clinics, NGOs, CSU/CMC urban centres) go 0.5–1.8 km from the prefecture town.
    Rural ones (PS, CSR) go to the largest settlement in their prefecture with no facility within 5 km.
    A prefecture only partly inside the window gets that share of its missing facilities placed.
    """
    from shapely.geometry import box
    st = pd.read_csv(OUT / "settlements_population.csv")
    prefs = prefecture_shapes()
    window = box(*BBOX)
    st["pref"] = None
    share = {}
    for k, poly in prefs.items():
        if k in STUDY_PREFS:
            inside = [poly.contains(Point(x, y)) for x, y in zip(st.lon, st.lat)]
            st.loc[inside, "pref"] = k
            share[k] = poly.intersection(window).area / poly.area
    missing = df[df.location_source.isna() & df.prefecture.isin(STUDY_PREFS)]
    for pref, grp in missing.groupby("prefecture"):
        n_place = int(round(share[pref] * len(grp)))
        town = places[(places.key == norm(PREF_TOWN[pref])) & places.type.isin(["city", "town"])].iloc[0]
        town_in = window.contains(Point(town.x, town.y))
        # urban first (they belong to the town), then rural; keep list order otherwise
        grp = grp.assign(urban=grp["name"].map(_is_urban)).sort_values("urban", ascending=False, kind="stable")
        placed = 0
        for i, r in grp.iterrows():
            if placed >= n_place:
                rep.append((r["name"], pref, "not placed", f"outside window share ({share[pref]:.0%} of prefecture inside)"))
                continue
            if r.urban and town_in:
                x, y = _ring(town.x, town.y, r["name"])
                df.loc[i, ["lon", "lat", "location_source"]] = [x, y, "synthetic"]
                rep.append((r["name"], pref, "synthetic", f"urban: near {PREF_TOWN[pref]} town centre"))
                placed += 1
                continue
            have = df[df.lat.notna()]
            tree = cKDTree(np.c_[have.lon * KX, have.lat * KY])
            cand = st[st.pref == pref].copy()
            d, _ = tree.query(np.c_[cand.lon * KX, cand.lat * KY])
            cand = cand[d > SYNTH_GAP_KM].sort_values("pop_hrsl", ascending=False)
            if cand.empty:
                rep.append((r["name"], pref, "not placed", "no under-served settlement left"))
                continue
            c = cand.iloc[0]
            label = c["name"] if isinstance(c["name"], str) and c["name"] else f"unnamed {c.type}"
            df.loc[i, ["lon", "lat", "location_source"]] = [c.lon, c.lat, "synthetic"]
            rep.append((r["name"], pref, "synthetic", f"rural: at {label} ({c.pop_hrsl:,.0f} people, no facility within 5 km)"))
            placed += 1
    return df, rep


def distance_surface(points, ref):
    rows, cols = np.indices((ref.height, ref.width))
    xs, ys = rasterio.transform.xy(ref.transform, rows.ravel(), cols.ravel())
    d, _ = cKDTree(np.c_[np.array(points)[:, 0] * KX, np.array(points)[:, 1] * KY]).query(
        np.c_[np.array(xs) * KX, np.array(ys) * KY])
    return d.reshape(ref.height, ref.width).astype("float32")


def sensitivity(before, after):
    from rasterio.features import geometry_mask
    ref = rasterio.open(OUT / "population_hrsl_90m.tif")
    gin = [f["geometry"] for f in json.load(open(OUT / "admin_adm0.geojson"))["features"] if f["properties"]["iso"] == "GIN"]
    P = ref.read(1) * ~geometry_mask(gin, (ref.height, ref.width), ref.transform)  # Guinea population only
    res = {}
    for label, sel in (("any facility", lambda d: d), ("hospital", lambda d: d[d.kind == "hospital"])):
        a = distance_surface(sel(before)[["lon", "lat"]].values, ref)
        b = distance_surface(sel(after)[["lon", "lat"]].values, ref)
        w = lambda s: float((s * P).sum() / P.sum())
        res[label] = {"before_km": w(a), "after_km": w(b),
                      "pop_closer_2km": float(P[(a - b) > 2].sum()), "pop_total": float(P.sum()),
                      "surface": b}
    write_raster(OUT / "dist_facility_km_90m.tif", res["any facility"]["surface"], ref.transform, nodata=None)
    write_raster(OUT / "dist_hospital_km_90m.tif", res["hospital"]["surface"], ref.transform, nodata=None)
    return res


def main():
    df = load_moh()
    prefs, places = prefecture_shapes(), osm_places()
    before = df[df.location_source == "MoH"].copy()
    df, rep = repair(df, prefs, places)
    df, rep = synthesise(df, rep, places)

    df = df[df.lat.notna()]
    df["kind"], df["level"] = zip(*df["name"].map(_level))
    win = df[df.lon.between(BBOX[0], BBOX[2]) & df.lat.between(BBOX[1], BBOX[3])].copy()
    before_w = before[before.lon.between(BBOX[0], BBOX[2]) & before.lat.between(BBOX[1], BBOX[3])].copy()
    before_w["kind"] = before_w["name"].map(lambda n: _level(n)[0])

    feats = [{"type": "Feature",
              "properties": {"name": r["name"], "kind": r.kind, "level": int(r.level), "prefecture": r.prefecture,
                             "code": r.code if isinstance(r.code, str) else None,
                             "location_source": r.location_source},
              "geometry": {"type": "Point", "coordinates": [round(float(r.lon), 6), round(float(r.lat), 6)]}}
             for _, r in win.iterrows()]
    json.dump({"type": "FeatureCollection", "features": feats}, open(OUT / "health_facilities.geojson", "w"),
              ensure_ascii=False)
    pd.DataFrame(rep, columns=["name", "prefecture", "result", "detail"]).to_csv(
        ROOT / "data" / "facility_repair_report.csv", index=False)

    s = sensitivity(before_w, win)
    counts = win.location_source.value_counts().to_dict()
    log(f"facilities in window: {len(win)} {counts}; kinds {win.kind.value_counts().to_dict()}")
    for k, v in s.items():
        log(f"distance to {k}: {v['before_km']:.2f} km -> {v['after_km']:.2f} km (population-weighted); "
            f"{v['pop_closer_2km']:,.0f} people now >2 km closer")
    with open(ROOT / "data" / "DATA_QA.md", "a") as f:
        f.write("\n## Health facilities after repair (pipeline/s1_facilities.py)\n\n")
        f.write(f"- In window: **{len(win)}** facilities. Location source: "
                + ", ".join(f"{k} {v}" for k, v in counts.items()) + "\n")
        f.write("- By kind: " + ", ".join(f"{k} {v}" for k, v in win.kind.value_counts().items()) + "\n")
        f.write("- Full list of what was matched, placed or dropped: `data/facility_repair_report.csv`\n\n")
        f.write("| Distance to (Guinea population only) | Before repair (km, pop-weighted) | After repair | People now > 2 km closer |\n|---|---|---|---|\n")
        for k, v in s.items():
            f.write(f"| {k} | {v['before_km']:.2f} | {v['after_km']:.2f} | {v['pop_closer_2km']:,.0f} "
                    f"({v['pop_closer_2km'] / v['pop_total']:.0%}) |\n")
    figure(win, s)
    return win, before_w, s


def figure(win, s):
    """Presentation panel: where each facility location came from, and what the repair changed."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    PAPER, INK, INK2, RULE = "#f7f6f2", "#141413", "#55534e", "#d9d6cc"
    style = {"MoH": ("#8a887f", "o", 16, "MoH list (observed)"),
             "village_match": ("#2a78d6", "o", 34, "matched to village name"),
             "synthetic": ("#eb6834", "D", 30, "placed by rule (scenario)"),
             "town_centre": ("#e34948", "*", 260, "hospital at town centre")}
    fig = plt.figure(figsize=(16, 7.2), facecolor=PAPER)
    ax = fig.add_axes([0.03, 0.08, 0.6, 0.78])
    asp = 1 / np.cos(np.radians(LAT0))
    for f in json.load(open(OUT / "admin_adm2.geojson"))["features"]:
        g = shape(f["geometry"])
        for poly in getattr(g, "geoms", [g]):
            if poly.geom_type == "Polygon":
                ax.plot(*poly.exterior.xy, color=RULE, lw=1)
    for f in json.load(open(OUT / "osm2014" / "roads.geojson"))["features"]:
        if f["properties"].get("type") in ("trunk", "primary", "secondary", "tertiary"):
            g = shape(f["geometry"])
            for ln in getattr(g, "geoms", [g]):
                ax.plot(*ln.xy, color="#c9c6bc", lw=.8)
    for src, (c, m, sz, lab) in style.items():
        d = win[win.location_source == src]
        ax.scatter(d.lon, d.lat, s=sz, c=c, marker=m, lw=.6, edgecolor="white", zorder=3,
                   label=f"{lab} · {len(d)}")
    hos = win[win.kind == "hospital"]
    for _, r in hos.iterrows():
        ax.annotate(f"Hospital · {PREF_TOWN.get(r.prefecture, r.prefecture.title())}",
                    (r.lon, r.lat), xytext=(8, 6), textcoords="offset points", fontsize=9, weight="bold", color=INK)
    ax.set_xlim(BBOX[0], BBOX[2]); ax.set_ylim(BBOX[1], BBOX[3]); ax.set_aspect(asp)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor=RULE, fontsize=9.5)
    fig.text(0.03, 0.93, "Data repair · health facilities", fontsize=18, weight="bold", color=INK)
    fig.text(0.03, 0.895, f"{len(win)} facilities in the study area; every point records where its location came from",
             fontsize=10.5, color=INK2)

    bx = fig.add_axes([0.69, 0.24, 0.28, 0.56])
    labels = ["any facility", "hospital"]
    y = np.arange(len(labels))
    b = [s[k]["before_km"] for k in labels]
    a = [s[k]["after_km"] for k in labels]
    bx.barh(y - .18, b, height=.34, color="#c9c6bc", label="before repair")
    bx.barh(y + .18, a, height=.34, color="#2a78d6", label="after repair")
    for yi, v in zip(y - .18, b):
        bx.text(v + .6, yi, f"{v:.1f} km", va="center", fontsize=10, color=INK2)
    for yi, v in zip(y + .18, a):
        bx.text(v + .6, yi, f"{v:.1f} km", va="center", fontsize=10, color=INK, weight="bold")
    bx.set_yticks(y, ["Distance to\nany facility", "Distance to\na hospital"])
    bx.invert_yaxis(); bx.set_xlim(0, max(b) * 1.25)
    bx.set_xlabel("population-weighted straight-line distance, Guinea part of study area", color=INK2)
    bx.legend(loc="upper left", frameon=False, bbox_to_anchor=(0, -0.14), ncol=2)
    bx.set_title("What the repair changes", loc="left", fontsize=12, weight="bold", pad=12)
    fig.savefig(ROOT / "data" / "facility_repair.png", dpi=120, facecolor=PAPER)


if __name__ == "__main__":
    main()
