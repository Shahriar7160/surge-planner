"""Step 1 — quality checks and a one-page data atlas.

Writes data/DATA_QA.md (numbers) and data/atlas_step1.png (picture).
"""
import json

import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import box, shape

from config import BBOX, OUT, RAW, ROOT

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

INK, INK2, RULE, PAPER = "#141413", "#55534e", "#d9d6cc", "#f7f6f2"
SERIES = {"Gueckedou": "#2a78d6", "Macenta": "#eb6834", "Kissidougou": "#1baf7a"}
NAMES = {"Gueckedou": "Guéckédou", "Macenta": "Macenta", "Kissidougou": "Kissidougou"}
WINDOW = box(*BBOX)

plt.rcParams.update({"font.family": "Inter", "font.size": 9, "axes.edgecolor": RULE, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": PAPER, "axes.facecolor": "white"})


def load(name):
    return json.load(open(OUT / name))["features"]


def main():
    q = []  # markdown lines
    pop = rasterio.open(OUT / "population_hrsl_90m.tif")
    P = pop.read(1)
    slope = rasterio.open(OUT / "slope_pct_x10_90m.tif").read(1) / 10
    dem = rasterio.open(OUT / "elevation_cop30_90m.tif").read(1)

    # population by country and prefecture (window part only)
    adm0, adm2 = load("admin_adm0.geojson"), load("admin_adm2.geojson")
    q.append("## Population (HRSL)\n")
    q.append(f"- Total in study window: **{P.sum():,.0f}** people")
    for f in adm0:
        m = ~geometry_mask([f["geometry"]], P.shape, pop.transform)
        q.append(f"- {f['properties']['name']}: {P[m].sum():,.0f}")
    q.append("\n| Prefecture (GIN) | People in window | Share of prefecture area inside window |\n|---|---|---|")
    pref_pop = {}
    full = {f["properties"]["shapeName"]: shape(f["geometry"])
            for f in json.load(open(RAW / "geoBoundaries-GIN-ADM2.geojson"))["features"]}
    for f in adm2:
        if f["properties"]["iso"] != "GIN":
            continue
        n = f["properties"]["name"]
        m = ~geometry_mask([f["geometry"]], P.shape, pop.transform)
        share = full[n].intersection(WINDOW).area / full[n].area if n in full else float("nan")
        pref_pop[n] = (P[m].sum(), share)
        q.append(f"| {n} | {P[m].sum():,.0f} | {share:.0%} |")

    # settlements
    st = pd.read_csv(OUT / "settlements_population.csv")
    q.append("\n## Settlements (OSM 2014 + HRSL)\n")
    q.append(f"- {len(st):,} settlements; {(st.pop_hrsl > 0).sum():,} received population from HRSL")
    q.append(f"- By type: " + ", ".join(f"{k} {v}" for k, v in st.type.value_counts().items()))
    q.append("- Note: large towns are split into OSM `neighbourhood`/`suburb` points (e.g. Guéckédou), so a "
             "town's population is spread across them. Step 2 merges these into their parent town.")

    # terrain
    q.append("\n## Terrain (Copernicus DEM 30 m → 90 m)\n")
    q.append(f"- Elevation {dem.min()}–{dem.max()} m; median slope {np.median(slope):.1f}%")
    for t in (2, 5, 10):
        q.append(f"- Area with slope < {t}%: {(slope < t).mean():.0%}")

    # roads
    roads = load("osm2014/roads.geojson")
    from collections import defaultdict
    from shapely.ops import transform
    from pyproj import Transformer
    tf = Transformer.from_crs("EPSG:4326", "EPSG:32629", always_xy=True).transform
    km = defaultdict(float)
    for f in roads:
        km[f["properties"].get("type") or "?"] += transform(tf, shape(f["geometry"])).length / 1000
    q.append("\n## Roads (OSM 2014)\n")
    q.append("| Class | km |\n|---|---|")
    for k, v in sorted(km.items(), key=lambda x: -x[1])[:12]:
        q.append(f"| {k} | {v:,.0f} |")

    # cases
    c = pd.read_csv(OUT / "cases_study_area_2014.csv", parse_dates=["date"])
    w = pd.read_csv(OUT / "cases_guinea_who_weekly.csv", parse_dates=["week"])
    q.append("\n## Cases (Guinea MoH sitreps, Aug–Oct 2014)\n")
    q.append("| Prefecture | First sitrep | Last sitrep | Cumulative cases | per 1,000 (window pop) | CTE admissions |"
             "\n|---|---|---|---|---|---|")
    for a in SERIES:
        s = c[c.area == a].sort_values("date")
        f0, f1 = s.iloc[0], s.iloc[-1]
        p = pref_pop.get(a, (np.nan, np.nan))
        q.append(f"| {NAMES[a]} | {f0.date:%d %b}: {f0.cum_cases:.0f} | {f1.date:%d %b}: {f1.cum_cases:.0f} | "
                 f"{f1.cum_cases:.0f} | {1000 * f1.cum_cases / p[0]:.2f}"
                 f"{'*' if p[1] < 0.95 else ''} | {f1.get('cte_admissions', np.nan):.0f} |")
    q.append("\n\\* prefecture only partly inside the window, so the rate is an upper bound.")
    q.append("- CTE admissions exceed cases in Guéckédou because the CTE also admitted suspects and patients "
             "from neighbouring prefectures. Macenta's CTE series drops to 0 on some dates: a reporting gap, "
             "not closures. Treat CTE series as evidence of *where* centres operated, not exact loads.")
    q.append(f"- WHO national weekly series: {len(w)} rows, {w.week.min():%b %Y}–{w.week.max():%b %Y}; "
             "use 'Patient database' rows for calibration (more complete than sitrep rows).")

    # ---------------- atlas figure
    fig = plt.figure(figsize=(16.5, 10.5))
    gs = fig.add_gridspec(2, 3, hspace=.28, wspace=.18, left=.04, right=.98, top=.9, bottom=.07)
    ext = (BBOX[0], BBOX[2], BBOX[1], BBOX[3])
    asp = 1 / np.cos(np.radians((BBOX[1] + BBOX[3]) / 2))

    def outlines(ax, lw=.8):
        for f in adm2:
            g = shape(f["geometry"])
            for poly in getattr(g, "geoms", [g]):
                if poly.geom_type == "Polygon":
                    x, y = poly.exterior.xy
                    ax.plot(x, y, color=INK2, lw=lw)
        for f in adm2:
            if f["properties"]["iso"] == "GIN" and f["properties"]["name"] in SERIES:
                p = shape(f["geometry"]).representative_point()
                ax.text(p.x, p.y, NAMES[f["properties"]["name"]], fontsize=9, weight="bold", color=INK,
                        ha="center", path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="white")])

    import matplotlib.patheffects  # noqa: F401
    ax = fig.add_subplot(gs[0, 0])
    ax.imshow(np.ma.masked_where(P < 0.5, np.log10(1 + P)), extent=ext, cmap="Blues", vmin=-0.3, vmax=2.2,
              aspect=asp, interpolation="nearest")
    outlines(ax)
    ax.set_title("Population · HRSL 90 m cells (darker = denser, log)", loc="left", fontsize=11, weight="bold")
    ax.set_xticks([]); ax.set_yticks([])

    ax = fig.add_subplot(gs[0, 1])
    ax.imshow(dem, extent=ext, cmap="Greys", aspect=asp, alpha=.55)
    flat = np.ma.masked_where(slope >= 5, np.ones_like(slope))
    ax.imshow(flat, extent=ext, cmap=matplotlib.colors.ListedColormap(["#1baf7a"]), aspect=asp, alpha=.75)
    outlines(ax)
    ax.set_title(f"Terrain · green = slope < 5% ({(slope < 5).mean():.0%} of area)", loc="left", fontsize=11, weight="bold")
    ax.set_xticks([]); ax.set_yticks([])

    ax = fig.add_subplot(gs[0, 2])
    major = {"trunk", "primary", "secondary", "tertiary"}
    for f in roads:
        t = f["properties"].get("type")
        g = shape(f["geometry"])
        for ln in getattr(g, "geoms", [g]):
            x, y = ln.xy
            ax.plot(x, y, color=INK if t in major else "#c9c6bc", lw=1 if t in major else .25)
    big = st[st.pop_hrsl > 0]
    ax.scatter(big.lon, big.lat, s=np.clip(big.pop_hrsl / 400, .5, 60), color="#2a78d6", alpha=.6, lw=0)
    outlines(ax, .6)
    ax.set_xlim(BBOX[0], BBOX[2]); ax.set_ylim(BBOX[1], BBOX[3]); ax.set_aspect(asp)
    ax.set_title("Roads + settlements sized by HRSL population", loc="left", fontsize=11, weight="bold")
    ax.set_xticks([]); ax.set_yticks([])

    ax = fig.add_subplot(gs[1, 0])
    for a, col in SERIES.items():
        s = c[c.area == a].sort_values("date")
        ax.plot(s.date, s.cum_cases, color=col, lw=2)
        ax.text(s.date.iloc[-1], s.cum_cases.iloc[-1], f"  {NAMES[a]} {s.cum_cases.iloc[-1]:.0f}", va="center", fontsize=9, color=INK)
    ax.set_title("Cumulative cases by prefecture · MoH sitreps", loc="left", fontsize=11, weight="bold")
    ax.grid(axis="y", color=RULE, lw=.8); ax.set_xlim(right=c.date.max() + pd.Timedelta(days=14))
    ax.tick_params(axis="x", rotation=0); ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))

    ax = fig.add_subplot(gs[1, 1])
    for a, col in SERIES.items():
        s = c[c.area == a].sort_values("date").dropna(subset=["cte_admissions"])
        if s.cte_admissions.max() > 0:
            ax.plot(s.date, s.cte_admissions, color=col, lw=2)
            ax.text(s.date.iloc[-1], s.cte_admissions.iloc[-1], f"  {NAMES[a]} {s.cte_admissions.iloc[-1]:.0f}", va="center", fontsize=9)
    ax.set_title("Cumulative admissions to treatment centres (CTE)", loc="left", fontsize=11, weight="bold")
    ax.grid(axis="y", color=RULE, lw=.8); ax.set_xlim(right=c.date.max() + pd.Timedelta(days=14))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%d %b"))
    ax.text(0.02, 0.92, "No CTE in Kissidougou in this period", transform=ax.transAxes, fontsize=9, color=INK2)

    ax = fig.add_subplot(gs[1, 2])
    ww = w[(w.indicator == "New") & (w.source == "Patient database")].dropna(subset=["value"])
    ax.bar(ww.week, ww.value, width=5, color="#2a78d6")
    ax.set_title("Guinea, new cases per week · WHO patient database", loc="left", fontsize=11, weight="bold")
    ax.grid(axis="y", color=RULE, lw=.8)
    ax.xaxis.set_major_locator(matplotlib.dates.MonthLocator(bymonth=(1, 3, 5, 7, 9, 11)))
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))

    fig.suptitle("S.U.R.G.E. · Step 1 data atlas · Forest Guinea 2014", x=.04, ha="left", fontsize=17, weight="bold")
    fig.text(.04, .925, "Sources: Meta/CIESIN HRSL · Copernicus DEM GLO-30 · geoBoundaries · OpenStreetMap 2014 (ODbL) · "
             "Guinea MoH sitreps via cmrivers/ebola · WHO", fontsize=9, color=INK2)
    fig.savefig(ROOT / "data" / "atlas_step1.png", dpi=110, facecolor=PAPER)

    (ROOT / "data" / "DATA_QA.md").write_text("# Step 1 data QA (auto-generated by pipeline/s1_qa.py)\n\n" + "\n".join(q) + "\n")
    print("\n".join(q))


if __name__ == "__main__":
    main()
