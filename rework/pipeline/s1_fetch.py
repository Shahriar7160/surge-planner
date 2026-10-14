"""Step 1 — collect, clip and clean every data source into data/processed.

Run:  python pipeline/s1_fetch.py            (all sources)
      python pipeline/s1_fetch.py cases dem  (only some)

Every output is listed in data/SOURCES.md with its origin, date and licence.
"""
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import shapefile
from rasterio.enums import Resampling
from rasterio.merge import merge
from rasterio.windows import from_bounds
from scipy.spatial import cKDTree
from shapely import make_valid
from shapely.geometry import box, mapping, shape

from config import BBOX, OUT, RAW, REFS

RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
WINDOW = box(*BBOX)


def log(msg):
    print(f"[s1] {msg}", flush=True)


def download(url, dest):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    log(f"download {url}")
    with urllib.request.urlopen(url, timeout=300) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def write_raster(path, arr, transform, nodata, dtype="float32"):
    prof = dict(driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype=dtype,
                crs="EPSG:4326", transform=transform, nodata=nodata, compress="deflate",
                predictor=3 if dtype.startswith("float") else 2, zlevel=9, tiled=True)
    with rasterio.open(path, "w", **prof) as dst:
        dst.write(arr.astype(dtype), 1)


def block_reduce(a, k, how):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    b = a[:h, :w].reshape(h // k, k, w // k, k)
    return getattr(np, how)(b, axis=(1, 3))


# ---------------------------------------------------------------- population
def population():
    """Meta/CIESIN High Resolution Settlement Layer, 30 m, clipped and summed to 90 m."""
    src_url = "/vsicurl/https://dataforgood-fb-data.s3.amazonaws.com/hrsl-cogs/hrsl_general/hrsl_general-latest.vrt"
    with rasterio.open(src_url) as src:
        win = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win)
        tr = src.window_transform(win)
    a = np.nan_to_num(a, nan=0.0)
    a90 = block_reduce(a, 3, "sum")
    tr90 = tr * tr.scale(3, 3)
    write_raster(OUT / "population_hrsl_90m.tif", a90, tr90, nodata=None)
    log(f"population: {a.sum():,.0f} people in window; 90 m grid {a90.shape}")
    return a90, tr90


# ---------------------------------------------------------------- elevation
def elevation():
    """Copernicus DEM GLO-30 (AWS open data), mosaicked, clipped, resampled to ~90 m; slope in %."""
    tiles = []
    for lat in (8, 9):
        for lon in (11, 10):
            name = f"Copernicus_DSM_COG_10_N{lat:02d}_00_W{lon:03d}_00_DEM"
            tiles.append(download(f"https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif",
                                  RAW / f"{name}.tif"))
    srcs = [rasterio.open(t) for t in tiles]
    mos, tr = merge(srcs, bounds=BBOX)
    for s in srcs:
        s.close()
    dem = mos[0].astype("float32")
    dem90 = block_reduce(dem, 3, "mean")
    tr90 = tr * tr.scale(3, 3)
    write_raster(OUT / "elevation_cop30_90m.tif", np.round(dem90), tr90, nodata=-9999, dtype="int16")
    # slope (%) on the 90 m grid; pixel size in metres at this latitude
    lat0 = (BBOX[1] + BBOX[3]) / 2
    dx = abs(tr90.a) * 111320 * np.cos(np.radians(lat0))
    dy = abs(tr90.e) * 110570
    gy, gx = np.gradient(dem90, dy, dx)
    slope = np.hypot(gx, gy) * 100
    write_raster(OUT / "slope_pct_x10_90m.tif", np.round(slope * 10), tr90, nodata=0, dtype="uint16")  # slope % × 10
    log(f"elevation: {dem90.min():.0f}–{dem90.max():.0f} m; slope median {np.median(slope):.1f}%")


# ---------------------------------------------------------------- land cover
WORLDCOVER = {10: "tree", 20: "shrub", 30: "grass", 40: "crop", 50: "built", 60: "bare",
              70: "snow", 80: "water", 90: "wetland", 95: "mangrove", 100: "moss"}


def landcover():
    """ESA WorldCover 2021 v200 (10 m), majority-resampled to the 90 m grid. Fills the sparse 2014 OSM forest layer."""
    from rasterio.vrt import WarpedVRT  # noqa: F401
    ref = rasterio.open(OUT / "population_hrsl_90m.tif")
    out = np.zeros((ref.height, ref.width), "uint8")
    for tile in ("N06W012", "N09W012"):
        url = f"/vsicurl/https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{tile}_Map.tif"
        with rasterio.open(url) as src:
            from rasterio.warp import reproject
            tmp = np.zeros_like(out)
            reproject(rasterio.band(src, 1), tmp, src_transform=src.transform, src_crs=src.crs,
                      dst_transform=ref.transform, dst_crs=ref.crs, resampling=Resampling.mode)
            out = np.where(out == 0, tmp, out)
    write_raster(OUT / "landcover_worldcover2021_90m.tif", out, ref.transform, nodata=0, dtype="uint8")
    vals, n = np.unique(out[out > 0], return_counts=True)
    log("landcover: " + ", ".join(f"{WORLDCOVER.get(v, v)} {c / n.sum():.0%}" for v, c in zip(vals, n)))


# ---------------------------------------------------------------- admin boundaries
def admin():
    """geoBoundaries gbOpen ADM0 + ADM2 for Guinea, Sierra Leone, Liberia, clipped to the window."""
    base = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen"
    for level in ("ADM0", "ADM2"):
        feats = []
        for iso in ("GIN", "SLE", "LBR"):
            p = download(f"{base}/{iso}/{level}/geoBoundaries-{iso}-{level}.geojson",
                         RAW / f"geoBoundaries-{iso}-{level}.geojson")
            for f in json.load(open(p))["features"]:
                g = shape(f["geometry"])
                if g.intersects(WINDOW):
                    feats.append({"type": "Feature",
                                  "properties": {"iso": iso, "name": f["properties"].get("shapeName"),
                                                 "level": level},
                                  "geometry": mapping(g.intersection(WINDOW).simplify(0.0005))})
        json.dump({"type": "FeatureCollection", "features": feats},
                  open(OUT / f"admin_{level.lower()}.geojson", "w"))
        log(f"admin {level}: {len(feats)} units -> {[f['properties']['name'] for f in feats]}")


# ---------------------------------------------------------------- cases
EBOLA_REPO = "https://github.com/cmrivers/ebola.git"


def cases():
    """Guinea MoH daily sitreps by prefecture (Aug–Oct 2014) + WHO national weekly series."""
    repo = RAW / "cmrivers_ebola"
    if not repo.exists():
        subprocess.run(["git", "clone", "-q", "--depth", "1", EBOLA_REPO, str(repo)], check=True)
    rows = []
    for f in sorted((repo / "guinea_data").glob("2014-*.csv")):
        df = pd.read_csv(f, dtype=str)
        df = df.rename(columns={"Mzerekore": "Nzerekore"})
        long = df.melt(id_vars=["Date", "Description"], var_name="area", value_name="value")
        rows.append(long)
    d = pd.concat(rows)
    d["value"] = pd.to_numeric(d["value"].str.replace("%", "", regex=False), errors="coerce")
    d = d.dropna(subset=["value"])
    d["date"] = pd.to_datetime(d["Date"])
    d = d.rename(columns={"Description": "metric"})[["date", "area", "metric", "value"]]
    d = d.sort_values(["date", "area", "metric"])
    d.to_csv(OUT / "cases_guinea_moh_by_prefecture_2014.csv", index=False)

    # Compact table for the study area: cumulative cases and CTE (treatment centre) use
    keep = {"Cumulative (confirmed + probable + suspects)": "cum_cases",
            "Total cases of confirmed": "cum_confirmed",
            "Total deaths (confirmed + probables + suspects)": "cum_deaths",
            "Total number of hospitalized cases in CTE": "in_cte",
            "Total number of admissions to CTE": "cte_admissions"}
    s = d[d.metric.isin(keep) & d.area.isin(["Gueckedou", "Macenta", "Kissidougou", "Totals"])]
    s = s.assign(metric=s.metric.map(keep)).pivot_table(index=["date", "area"], columns="metric",
                                                        values="value", aggfunc="first").reset_index()
    s.to_csv(OUT / "cases_study_area_2014.csv", index=False)

    w = pd.read_csv(repo / "who_data" / "guinea.csv")
    w = w.rename(columns={"Epi week": "epi_week", "Ebola data source": "source",
                          "Case definition": "case_def", "Indicator type": "indicator", "Numeric": "value"})
    w["week"] = pd.to_datetime(w["epi_week"], format="%d %B %Y")
    w = w[["week", "source", "case_def", "indicator", "value"]].sort_values(["source", "week"])
    w.to_csv(OUT / "cases_guinea_who_weekly.csv", index=False)
    last = s[s.area != "Totals"].sort_values("date").groupby("area").last()
    log(f"cases: {d.date.nunique()} sitrep dates {d.date.min():%Y-%m-%d}..{d.date.max():%Y-%m-%d}; "
        f"latest cumulative in study area: {last['cum_cases'].to_dict()}")
    cte = d[(d.metric == "Total number of admissions to CTE") & (d.value > 0) & (d.area != "Totals")]
    log(f"prefectures with CTE admissions in sitreps: {sorted(cte.area.unique())}")


# ---------------------------------------------------------------- OSM 2014 (from the 2015 project)
def _read(layer, keep=lambda r: True):
    shp = REFS / layer
    r = shapefile.Reader(str(shp), encoding="utf-8", encodingErrors="ignore")
    names = [f[0] for f in r.fields[1:]]
    for sr in r.iterShapeRecords():
        props = dict(zip(names, sr.record))
        if not keep(props) or not sr.shape.points:
            continue
        g = shape(sr.shape.__geo_interface__)
        if not g.is_valid:
            g = make_valid(g)
        if g.intersects(WINDOW):
            yield props, g.intersection(WINDOW) if g.geom_type != "Point" else g


def osm():
    """Convert the 2014 OSM shapefiles to clipped GeoJSON (readable by Python and Grasshopper)."""
    layers = {
        "places": ("places/places.shp", ("name", "type", "population")),
        "roads": ("roads/roads.shp", ("name", "type", "oneway", "bridge")),
        "waterways": ("waterways/waterways.shp", ("name", "type")),
        "landuse": ("landuse/Guinea_landuse.shp", ("name", "type")),
        "natural": ("Guinea natural areas/Guinea_natural_areas.shp", ("name", "type")),
        "cell_towers": ("Guinea Cellular Coverage/Guinea_Cellular_Coverage.shp",
                        ("PROVIDER", "WHAT", "CITY_VILLA", "PREFECTURE")),
    }
    d = OUT / "osm2014"
    d.mkdir(exist_ok=True)
    for name, (path, fields) in layers.items():
        feats = []
        for props, g in _read(path):
            if g.is_empty:
                continue
            g = g.simplify(0.00002) if g.geom_type != "Point" else g
            feats.append({"type": "Feature", "properties": {k: props.get(k) for k in fields if k in props},
                          "geometry": json.loads(json.dumps(mapping(g)), parse_float=lambda x: round(float(x), 6))})
        json.dump({"type": "FeatureCollection", "features": feats}, open(d / f"{name}.geojson", "w"),
                  separators=(",", ":"))
        log(f"osm2014 {name}: {len(feats)} features")


# ---------------------------------------------------------------- settlements + population
POP_TYPES = {"city", "town", "suburb", "village", "neighbourhood", "hamlet", "locality", "isolated_dwellin"}


def settlements():
    """Give every OSM settlement a real population: HRSL people assigned to the nearest settlement (≤ 5 km)."""
    pop = rasterio.open(OUT / "population_hrsl_90m.tif")
    a = pop.read(1)
    rows, cols = np.nonzero(a > 0)
    xs, ys = rasterio.transform.xy(pop.transform, rows, cols)
    people = a[rows, cols]
    pl = [(p, g) for p, g in _read("places/places.shp") if p.get("type") in POP_TYPES]
    lat0 = (BBOX[1] + BBOX[3]) / 2
    kx, ky = 111.32 * np.cos(np.radians(lat0)), 110.57
    P = np.array([[g.x * kx, g.y * ky] for _, g in pl])
    C = np.column_stack([np.array(xs) * kx, np.array(ys) * ky])
    dist, idx = cKDTree(P).query(C, distance_upper_bound=5.0)
    ok = np.isfinite(dist)
    total = np.bincount(idx[ok], weights=people[ok], minlength=len(pl))
    df = pd.DataFrame({
        "osm_id": [p.get("osm_id") for p, _ in pl], "name": [p.get("name") for p, _ in pl],
        "type": [p.get("type") for p, _ in pl], "lon": [g.x for _, g in pl], "lat": [g.y for _, g in pl],
        "pop_hrsl": total.round(0), "pop_osm_tag": [p.get("population") or None for p, _ in pl]})
    df.to_csv(OUT / "settlements_population.csv", index=False)
    unassigned = people[~ok].sum()
    log(f"settlements: {len(df)}; {people[ok].sum():,.0f} people assigned, {unassigned:,.0f} beyond 5 km; "
        f"top: {df.nlargest(5, 'pop_hrsl')[['name', 'pop_hrsl']].values.tolist()}")


# ---------------------------------------------------------------- files downloaded by the author
USER = OUT.parent / "user"


def _col(cols, *keys):
    for c in cols:
        lc = str(c).lower().replace(" ", "")
        if any(k in lc for k in keys):
            return c
    return None


def _read_text_table(path):
    """CSV with unknown separator and encoding (UTF-8, Windows or Mac Excel exports)."""
    raw = Path(path).read_bytes()
    try:
        raw.decode("utf-8")
        enc = "utf-8"
    except UnicodeDecodeError:
        # Mac Excel puts é/è at 0x8E/0x8F, which are unused in Windows cp1252
        enc = "mac_roman" if raw.count(b"\x8e") + raw.count(b"\x8f") > 0 else "cp1252"
    df = pd.read_csv(path, sep=None, engine="python", encoding=enc, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df, enc


# Facility level from the name prefix used by the Guinea MoH list
LEVELS = [(r"^(h[oô]pital|h\b|chu|chr|hp\b|hr\b)", "hospital", 4),
          (r"^(cmc|csur|csu|csr|csa|cs\b|centre)", "health_centre", 3),
          (r"^(ps|psr|poste)\b", "health_post", 2),
          (r"^(clinique|cabinet|cab\b|infirm|maternit)", "private_clinic", 2),
          (r"", "other", 1)]


def _level(name):
    import re
    n = str(name or "").strip().lower()
    for pat, kind, lvl in LEVELS:
        if re.match(pat, n):
            return kind, lvl
    return "other", 1


def user():
    """Process files dropped into data/user/: health facilities and CHIRPS rainfall."""
    import gzip
    import zipfile

    # health facilities -> health_facilities.geojson (study window only)
    hf = next((USER / f for f in ("health_facilities.xlsx", "health_facilities.csv", "health_facilities.geojson",
                                   "structures_de_sante_guinee_vf.csv")
               if (USER / f).exists()), None)
    if hf is None:
        log("user: no health_facilities file yet")
    else:
        if hf.suffix == ".geojson":
            feats = [f for f in json.load(open(hf))["features"] if shape(f["geometry"]).intersects(WINDOW)]
        else:
            if hf.suffix == ".xlsx":
                df, enc = pd.read_excel(hf, dtype=str), "xlsx"
            else:
                df, enc = _read_text_table(hf)
            n_all = len(df)
            cc = _col(df.columns, "country")
            if cc is not None:
                df = df[df[cc].astype(str).str.contains("Guin", case=False) & ~df[cc].astype(str).str.contains("Bissau|Equatorial", case=False)]
            lat, lon = _col(df.columns, "lat", "y_coord"), _col(df.columns, "long", "lon", "x_coord")
            df[lat] = pd.to_numeric(df[lat].astype(str).str.replace(",", "."), errors="coerce")
            df[lon] = pd.to_numeric(df[lon].astype(str).str.replace(",", "."), errors="coerce")
            n_missing = int(df[[lat, lon]].isna().any(axis=1).sum())
            df = df.dropna(subset=[lat, lon])
            df = df[(df[lon].between(BBOX[0], BBOX[2])) & (df[lat].between(BBOX[1], BBOX[3]))]
            df = df.drop_duplicates(subset=[lat, lon])
            name = _col(df.columns, "facilityname", "name", "nom", "structure", "etablissement")
            ftype = _col(df.columns, "facilitytype", "type", "amenity", "categorie", "catégorie", "nature")
            pref = _col(df.columns, "prefecture", "admin2", "district")
            code = _col(df.columns, "code")
            feats = []
            for r in df.to_dict("records"):
                kind, lvl = _level(r.get(name))
                feats.append({"type": "Feature",
                              "properties": {"name": (r.get(name) or "").strip(), "source_type": r.get(ftype),
                                             "kind": kind, "level": lvl, "prefecture": r.get(pref),
                                             "code": r.get(code)},
                              "geometry": {"type": "Point", "coordinates": [float(r[lon]), float(r[lat])]}})
            log(f"user: {hf.name} read as {enc}: {n_all} rows, {n_missing} without coordinates")
        json.dump({"type": "FeatureCollection", "features": feats}, open(OUT / "health_facilities_moh.geojson", "w"))
        from collections import Counter
        log(f"user: {len(feats)} health facilities in window: "
            f"{Counter(str(f['properties'].get('kind')) for f in feats).most_common(6)}")

    # rainfall -> rain_2014_monthly_mm.tif (12 bands) [+ rain_climatology_monthly_mm.tif]
    ch = USER / "chirps"
    files = sorted(ch.glob("chirps-v2.0.*.tif*")) if ch.exists() else []
    wc = sorted(ch.glob("wc2.1_*prec*.zip")) if ch.exists() else []
    if not files and not wc:
        log("user: no rainfall files yet")
        return
    ref = rasterio.open(OUT / "population_hrsl_90m.tif")

    def clip(path):
        import shutil
        path = Path(path)
        if path.is_dir():                      # some unzip tools make a folder named *.tif
            path = next(path.glob("*.tif"))
        if path.suffix == ".gz":
            tmp = RAW / path.name[:-3]
            if not tmp.exists():
                with gzip.open(path) as fi, open(tmp, "wb") as fo:
                    shutil.copyfileobj(fi, fo)
            path = tmp
        src = rasterio.open(path)
        win = from_bounds(*BBOX, src.transform).round_offsets().round_lengths()
        a = src.read(1, window=win, boundless=True, fill_value=-9999).astype("float32")
        return a, src.window_transform(win)

    def save(name, months):
        stack = np.stack([months[m] for m in range(1, 13)])
        a0, tr = months["_tr"]
        prof = dict(driver="GTiff", height=stack.shape[1], width=stack.shape[2], count=12, dtype="float32",
                    crs="EPSG:4326", transform=tr, nodata=-9999, compress="deflate")
        with rasterio.open(OUT / name, "w", **prof) as dst:
            dst.write(stack)
        m = np.where(stack < 0, np.nan, stack)
        log(f"user: {name}: mean mm/month " + " ".join(f"{np.nanmean(m[i]):.0f}" for i in range(12)))

    if files:
        by = {}
        for f in files:
            import re
            m = re.search(r"(\d{4})\.(\d{2})\.tif", f.name)
            if not m:
                continue
            yr, mo = m.groups()
            a, tr = clip(f)
            if int(mo) in by.get(int(yr), {}):
                continue                       # same month already read (gz + extracted copy)
            by.setdefault(int(yr), {})[int(mo)] = a
            by[int(yr)]["_tr"] = (a, tr)
        if 2014 in by and all(m in by[2014] for m in range(1, 13)):
            save("rain_2014_monthly_mm.tif", by[2014])
        yrs = [y for y in by if all(m in by[y] for m in range(1, 13))]
        if len(yrs) > 1:
            clim = {m: np.mean([by[y][m] for y in yrs], axis=0) for m in range(1, 13)}
            clim["_tr"] = by[yrs[0]]["_tr"]
            save("rain_climatology_monthly_mm.tif", clim)
    elif wc:
        z = zipfile.ZipFile(wc[0])
        months = {}
        for n in sorted(z.namelist()):
            if n.endswith(".tif"):
                mo = int(n.rsplit("_", 1)[1][:2])
                p = RAW / n
                p.write_bytes(z.read(n))
                a, tr = clip(p)
                months[mo] = a
                months["_tr"] = (a, tr)
        save("rain_climatology_monthly_mm.tif", months)


STEPS = {"population": population, "dem": elevation, "landcover": landcover, "admin": admin, "cases": cases,
         "osm": osm, "settlements": settlements, "user": user}

if __name__ == "__main__":
    for k in sys.argv[1:] or STEPS:
        STEPS[k]()
