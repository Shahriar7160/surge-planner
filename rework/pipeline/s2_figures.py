"""Step 2 — presentation figures (data/s2/fig_*.png)."""
import json

import matplotlib
import numpy as np
import pandas as pd
from shapely.geometry import shape

from config import BBOX, OUT
import s2_params as P
from s2_network import S2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402

INK, INK2, INK3, RULE, PAPER = "#141413", "#55534e", "#8a887f", "#d9d6cc", "#f7f6f2"
BLUE, ORANGE, AQUA, RED = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
PREF_COL = {"Gueckedou": BLUE, "Macenta": ORANGE, "Kissidougou": AQUA}
PREF_NAME = {"Gueckedou": "Guéckédou", "Macenta": "Macenta", "Kissidougou": "Kissidougou"}
ASP = 1 / np.cos(np.radians((BBOX[1] + BBOX[3]) / 2))
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": RULE, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK2})


def base(ax, roads=True):
    for f in json.load(open(OUT / "admin_adm2.geojson"))["features"]:
        g = shape(f["geometry"])
        for poly in getattr(g, "geoms", [g]):
            if poly.geom_type == "Polygon":
                ax.plot(*poly.exterior.xy, color=RULE, lw=.9, zorder=1)
    if roads:
        for f in json.load(open(OUT / "osm2014" / "roads.geojson"))["features"]:
            if f["properties"].get("type") in ("trunk", "primary", "secondary", "tertiary"):
                g = shape(f["geometry"])
                for ln in getattr(g, "geoms", [g]):
                    ax.plot(*ln.xy, color="#c9c6bc", lw=.8, zorder=1)
    ax.set_xlim(BBOX[0], BBOX[2]); ax.set_ylim(BBOX[1], BBOX[3]); ax.set_aspect(ASP)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def title(fig, t, sub):
    fig.text(.03, .94, t, fontsize=18, weight="bold", color=INK)
    fig.text(.03, .905, sub, fontsize=10.5, color=INK2)


def fig_calibration():
    cal = json.load(open(S2 / "calibration.json"))
    inc = np.load(S2 / "incidence.npy")
    patches = pd.read_csv(S2 / "patches.csv")
    obs = pd.read_csv(OUT / "cases_study_area_2014.csv", parse_dates=["date"])
    day0 = pd.Timestamp(cal["day0"])
    dates = pd.date_range(day0, periods=len(inc))
    fig = plt.figure(figsize=(15, 6.6), facecolor=PAPER)
    title(fig, "Outbreak model · calibrated to 2014",
          f"Metapopulation SEIR on {len(patches)} settlement patches, coupled by road-time mobility. "
          f"R₀ = {cal['R0']:.2f}, reporting rate {cal['reporting_rate']:.0%}, fit error (log RMSE) {cal['rmse_log']:.3f}")
    ax = fig.add_axes([.05, .12, .55, .7])
    cum = np.cumsum(inc, 0) * cal["reporting_rate"]
    for a, col in PREF_COL.items():
        m = cum[:, patches.prefecture.values == a].sum(1)
        ax.plot(dates, m, color=col, lw=2)
        o = obs[obs.area == a]
        ax.scatter(o.date, o.cum_cases, color=col, s=26, edgecolor="white", lw=.8, zorder=3)
        ax.text(dates[-1], m[-1], f"  {PREF_NAME[a]}", va="center", fontsize=10, color=INK)
    ax.axvspan(pd.Timestamp(P.PLANNING_FROM), dates[-1], color="#f0eee6", zorder=0)
    ax.text(pd.Timestamp(P.PLANNING_FROM), ax.get_ylim()[1] * .95, "  planning window", color=INK2, fontsize=9)
    ax.set_ylabel("cumulative reported cases")
    ax.grid(axis="y", color=RULE, lw=.8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_xlim(pd.Timestamp("2014-03-01"), dates[-1] + pd.Timedelta(days=25))
    ax.text(.01, .97, "lines = model   ·   dots = Guinea MoH sitreps", transform=ax.transAxes, fontsize=9, color=INK2, va="top")

    bx = fig.add_axes([.68, .12, .29, .7])
    beds = np.load(S2 / "beds.npy").sum(1)
    bx.fill_between(dates, beds, color=BLUE, alpha=.2, lw=0)
    bx.plot(dates, beds, color=BLUE, lw=2)
    i = int(beds.argmax())
    bx.annotate(f"peak {beds[i]:,.0f} beds\n{dates[i]:%d %b %Y}", (dates[i], beds[i]), xytext=(-110, -10),
                textcoords="offset points", fontsize=10, color=INK, arrowprops=dict(arrowstyle="-", color=INK3))
    bx.set_title("Isolation beds needed, whole study area", loc="left", fontsize=11, weight="bold")
    bx.grid(axis="y", color=RULE, lw=.8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    bx.set_xlim(pd.Timestamp("2014-05-01"), dates[-1])
    fig.savefig(S2 / "fig_1_calibration.png", dpi=120, facecolor=PAPER)


def fig_filters():
    c = pd.read_csv(S2 / "candidates.csv.gz")
    funnel = pd.read_csv(S2 / "filter_funnel.csv")
    fig = plt.figure(figsize=(16, 8.4), facecolor=PAPER)
    title(fig, "Location · MUST filters and SHOULD scores",
          f"{funnel.remaining.iloc[0]:,} candidate points every {P.CANDIDATE_SPACING_M} m → "
          f"{funnel.remaining.iloc[-1]:,} pass all hard filters, then ranked by the weighted score")
    ax = fig.add_axes([.02, .07, .5, .78])
    base(ax)
    fail = c[~c.pass_all]
    ax.scatter(fail.lon, fail.lat, s=.4, color="#e6e3da", zorder=1)
    ok = c[c.pass_all]
    sc = ax.scatter(ok.lon, ok.lat, s=7, c=ok.score, cmap="Blues", vmin=.2, vmax=.95, zorder=3)
    cb = fig.colorbar(sc, ax=ax, shrink=.5, pad=.01)
    cb.set_label("SHOULD score (0–1)")
    ax.text(.01, .02, "grey = removed by a MUST filter", transform=ax.transAxes, fontsize=9, color=INK2)
    bx = fig.add_axes([.62, .5, .35, .36])
    f = funnel.iloc[1:]
    y = np.arange(len(f))
    bx.barh(y, f.remaining, color=BLUE, height=.6)
    bx.set_yticks(y, [s.split(" (")[0] for s in f["filter"]])
    bx.invert_yaxis()
    for yi, v in zip(y, f.remaining):
        bx.text(v + 300, yi, f"{v:,}", va="center", fontsize=9, color=INK)
    bx.set_title("Candidates left after each MUST filter (cumulative)", loc="left", fontsize=11, weight="bold")
    bx.set_xlim(0, f.remaining.max() * 1.18)
    cx = fig.add_axes([.62, .08, .35, .32])
    w = pd.Series(P.SHOULD).sort_values()
    cx.barh(range(len(w)), w.values, color=INK3, height=.6)
    cx.set_yticks(range(len(w)), [k.replace("_", " ") for k in w.index])
    for yi, v in enumerate(w.values):
        cx.text(v + .004, yi, f"{v:.2f}", va="center", fontsize=9)
    cx.set_title("SHOULD weights (edit in s2_params.py)", loc="left", fontsize=11, weight="bold")
    fig.savefig(S2 / "fig_2_filters_scores.png", dpi=120, facecolor=PAPER)


def fig_sites():
    sites = pd.read_csv(S2 / "sites.csv")
    patches = pd.read_csv(S2 / "patches.csv")
    grid = pd.read_csv(S2 / "grid_2015.csv")
    Y = np.load(S2 / "assignment.npy")
    summ = json.load(open(S2 / "summary.json"))
    fig = plt.figure(figsize=(16, 7.6), facecolor=PAPER)
    title(fig, "Location · the optimised treatment sites",
          f"{summ['sites']} sites cover {summ['coverage']:.0%} of peak bed demand within {P.MUST['max_patient_travel_h']} h by road "
          f"· the 2015 grid needed {summ['grid_units']} units to cover {summ['grid_coverage']:.0%}")
    ax = fig.add_axes([.02, .06, .47, .8]); base(ax)
    ax.scatter(grid.lon, grid.lat, marker="s", s=22, color=INK, zorder=3)
    ax.scatter(patches.lon, patches.lat, s=6 + patches.peak_beds * 2, color=RED, alpha=.5, lw=0, zorder=2)
    ax.set_title(f"2015 method · one unit per 500 km² · {len(grid)} units", loc="left", fontsize=11, weight="bold")
    bx = fig.add_axes([.51, .06, .47, .8]); base(bx)
    for i in range(Y.shape[0]):
        j = int(Y[i].argmax())
        if Y[i, j] > .01:
            st = sites[sites.col == j].iloc[0]
            bx.plot([patches.lon[i], st.lon], [patches.lat[i], st.lat], color=BLUE, lw=.7, alpha=.45, zorder=2)
    bx.scatter(patches.lon, patches.lat, s=6 + patches.peak_beds * 2, color=RED, alpha=.5, lw=0, zorder=2,
               label="patch demand (peak beds)")
    bx.scatter(sites.lon, sites.lat, s=60 + sites.modules * 40, color=BLUE, edgecolor="white", lw=1.2, zorder=4,
               label="treatment site (size = modules)")
    for _, s in sites.iterrows():
        right = s.lon > BBOX[0] + 0.75 * (BBOX[2] - BBOX[0])
        bx.annotate(f"{s.site_id} · {s.near}\n{s.modules}×12 beds", (s.lon, s.lat), xytext=(-10 if right else 10, 4),
                    ha="right" if right else "left",
                    textcoords="offset points", fontsize=8.5, color=INK, weight="bold",
                    path_effects=[matplotlib.patheffects.withStroke(linewidth=3, foreground="white")])
    bx.legend(loc="lower left", frameon=True, facecolor="white", edgecolor=RULE, fontsize=9)
    bx.set_title("S.U.R.G.E. · optimised sites", loc="left", fontsize=11, weight="bold")
    fig.savefig(S2 / "fig_3_sites.png", dpi=120, facecolor=PAPER)


def fig_tradeoffs():
    sw = pd.read_csv(S2 / "sweep.csv")
    curve = pd.read_csv(S2 / "response_curve.csv", parse_dates=["date"])
    summ = json.load(open(S2 / "summary.json"))
    fig = plt.figure(figsize=(16, 6.4), facecolor=PAPER)
    title(fig, "Trade-offs and feedback",
          "How coverage responds to the number of sites and the travel limit, and what opening the sites does to the outbreak")
    ax = fig.add_axes([.05, .13, .4, .68])
    cols = {0.75: "#9ec5f4", 1.0: "#5598e7", 1.5: BLUE, 2.0: "#1c5cab", 3.0: "#0d366b"}
    for h, g in sw.groupby("travel_h"):
        ax.plot(g.sites, g.coverage * 100, color=cols.get(h, INK), lw=2, marker="o", ms=4, label=f"≤ {h:g} h by road")
    ax.legend(loc="lower right", frameon=False, title="travel limit", fontsize=9, title_fontsize=9)
    ax.set_xlabel("number of treatment sites"); ax.set_ylabel("% of peak bed demand covered")
    ax.set_ylim(0, 103); ax.grid(axis="y", color=RULE, lw=.8)
    ax.axvline(summ["sites"], color=INK3, ls="--", lw=1)
    ax.axhline(P.TARGET_COVERAGE * 100, color=INK3, ls=":", lw=1)
    ax.text(summ["sites"], 4, f" chosen: {summ['sites']} sites (smallest reaching {P.TARGET_COVERAGE:.0%} at {P.MUST['max_patient_travel_h']} h)",
            fontsize=9, color=INK2)
    ax.set_title("Coverage by sites and travel limit", loc="left", fontsize=11, weight="bold")
    bx = fig.add_axes([.55, .13, .42, .68])
    c = curve[curve.date >= "2014-06-01"]
    bx.plot(c.date, c.beds_no_response, color=RED, lw=2)
    bx.plot(c.date, c.beds_with_surge, color=BLUE, lw=2)
    bx.text(c.date.iloc[-1], c.beds_no_response.iloc[-1], "  no response", va="center", fontsize=10)
    bx.text(c.date.iloc[-1], c.beds_with_surge.iloc[-1], "  with S.U.R.G.E.", va="center", fontsize=10)
    bx.axvline(pd.Timestamp(summ["deploy_date"]), color=INK3, ls="--", lw=1)
    bx.text(pd.Timestamp(summ["deploy_date"]), bx.get_ylim()[1] * .92, " sites open", fontsize=9, color=INK2)
    bx.set_ylabel("isolation beds in use"); bx.grid(axis="y", color=RULE, lw=.8)
    bx.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    bx.set_xlim(c.date.iloc[0], c.date.iloc[-1] + pd.Timedelta(days=28))
    bx.set_title(f"Feedback · about {summ['cases_averted_by_horizon']:,.0f} cases averted by {P.HORIZON}", loc="left",
                 fontsize=11, weight="bold")
    fig.savefig(S2 / "fig_4_tradeoffs_feedback.png", dpi=120, facecolor=PAPER)


if __name__ == "__main__":
    import matplotlib.patheffects  # noqa: F401
    fig_calibration(); fig_filters(); fig_sites(); fig_tradeoffs()
    print("[s2] figures written")
