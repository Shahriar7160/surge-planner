"""Figures for the scenario study: small multiples, robustness map, animated GIF."""
import json

import matplotlib
import numpy as np
import pandas as pd

import s2_params as P
from s2_figures import ASP, BLUE, INK, INK2, INK3, ORANGE, PAPER, RED, RULE, base
from s2_network import S2
from s2_scenarios import OUTD, SCENARIOS, demand

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

GREY_RING = "#a8a59b"


def panel(ax, r, base_sites, patches, big=False):
    base(ax, roads=True)
    o = next(s[3] for s in SCENARIOS if s[0] == r["id"])
    d = demand(patches, o.get("plan", P.PLANNING_FROM), o.get("window_d"))
    ax.scatter(patches.lon, patches.lat, s=(4 if not big else 8) + d * (1.2 if not big else 2.4), color=RED,
               alpha=.45, lw=0, zorder=2)
    if r["id"] != "baseline":
        ax.scatter([s["lon"] for s in base_sites], [s["lat"] for s in base_sites], s=260 if big else 120,
                   facecolor="none", edgecolor=GREY_RING, lw=1.4, ls=(0, (2, 2)), zorder=3)
    for s in r["sites"]:
        col = ORANGE if s.get("moved") else BLUE
        ax.scatter(s["lon"], s["lat"], s=(70 if big else 26) + s["modules"] * (28 if big else 11), color=col,
                   edgecolor="white", lw=1, zorder=4)
    fs = 15 if big else 10.5
    ax.set_title(r["title"], loc="left", fontsize=fs, weight="bold", color=INK, pad=18 if big else 14)
    ax.text(0, 1.012, r["what"], transform=ax.transAxes, fontsize=fs - 3, color=INK2, va="bottom")
    moved = "" if r["id"] == "baseline" else f" · {r['sites_moved']} of {len(r['sites'])} sites moved"
    ax.text(.015, .03, f"{len(r['sites'])} sites · {r['coverage']:.0%} covered{moved}", transform=ax.transAxes,
            fontsize=fs - 2, color=INK, weight="bold",
            path_effects=[pe.withStroke(linewidth=3, foreground="white")])


def small_multiples(res, patches):
    fig, axs = plt.subplots(3, 3, figsize=(18, 14.5), facecolor=PAPER,
                            gridspec_kw=dict(hspace=.32, wspace=.04, left=.02, right=.98, top=.88, bottom=.04))
    for ax, r in zip(axs.ravel(), res):
        panel(ax, r, res[0]["sites"], patches)
    fig.text(.02, .955, "Same data, different variables, different sites", fontsize=22, weight="bold", color=INK)
    fig.text(.02, .932, "Each panel changes one variable and reruns the whole algorithm "
             "(MUST filters → SHOULD scores → optimisation). Nothing is placed by hand.", fontsize=12, color=INK2)
    handles = [plt.Line2D([], [], marker="o", ls="", color=BLUE, ms=9, label="site in the same place as baseline"),
               plt.Line2D([], [], marker="o", ls="", color=ORANGE, ms=9, label="site moved (> 2 km from any baseline site)"),
               plt.Line2D([], [], marker="o", ls="", mfc="none", mec=GREY_RING, ms=11, label="baseline site"),
               plt.Line2D([], [], marker="o", ls="", color=RED, alpha=.5, ms=7, label="bed demand (size)")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(.98, .965), ncol=2, frameon=False, fontsize=10.5)
    fig.savefig(OUTD / "fig_5_scenarios.png", dpi=110, facecolor=PAPER)


def robustness(res):
    z = pd.read_csv(OUTD / "monte_carlo_zones.csv")
    mc = json.load(open(OUTD / "monte_carlo_summary.json"))
    fig = plt.figure(figsize=(15, 8), facecolor=PAPER)
    fig.text(.03, .94, "Which sites are robust?", fontsize=20, weight="bold", color=INK)
    fig.text(.03, .905, f"{mc['runs']} runs with random SHOULD weights (score counts strongly, weight 0.6). Colour = share of runs with a site within 5 km. "
             f"Coverage stayed between {mc['coverage_min']:.0%} and {mc['coverage_max']:.0%}.", fontsize=11.5, color=INK2)
    ax = fig.add_axes([.03, .05, .7, .82])
    base(ax)
    z = z.sort_values("zone_share")
    sc = ax.scatter(z.lon, z.lat, c=z.zone_share * 100, cmap="Blues", vmin=0, vmax=100, s=14, zorder=3)
    b = res[0]["sites"]
    ax.scatter([s["lon"] for s in b], [s["lat"] for s in b], s=240, facecolor="none", edgecolor=INK, lw=1.6, zorder=4)
    main = pd.read_csv(S2 / "sites.csv")
    for s in b:
        m = main.iloc[int(np.argmin(np.hypot(main.lon - s["lon"], main.lat - s["lat"])))]
        right = s["lon"] > -9.4
        ax.annotate(f"{m.site_id} · {m.near}", (s["lon"], s["lat"]), xytext=(-12 if right else 12, 10),
                    ha="right" if right else "left", textcoords="offset points",
                    fontsize=10, weight="bold", path_effects=[pe.withStroke(linewidth=3, foreground="white")])
    cax = fig.add_axes([.78, .12, .16, .025])
    cb = fig.colorbar(sc, cax=cax, orientation="horizontal")
    cb.set_label("% of runs with a site within 5 km")
    tx = fig.add_axes([.78, .2, .2, .6]); tx.axis("off")
    tx.text(0, 1, "How to read it", fontsize=13, weight="bold", va="top")
    tx.text(0, .9, "Dark zones get a site whatever the\npriorities: the demand and the road\nnetwork decide them.\n\n"
            "Light zones depend on the weights:\nthere, the designer's priorities\ndecide the location.",
            fontsize=11, va="top", color=INK2, linespacing=1.5)
    fig.savefig(OUTD / "fig_6_robustness.png", dpi=110, facecolor=PAPER)


def gif(res, patches):
    from PIL import Image
    frames = []
    for r in res:
        fig = plt.figure(figsize=(11, 8.2), facecolor=PAPER)
        ax = fig.add_axes([.03, .04, .94, .8])
        panel(ax, r, res[0]["sites"], patches, big=True)
        fig.text(.03, .94, "S.U.R.G.E. · change a variable, the sites follow", fontsize=13, color=INK3, weight="bold")
        p = OUTD / f"_frame_{r['id']}.png"
        fig.savefig(p, dpi=80, facecolor=PAPER)
        plt.close(fig)
        frames.append(Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=128))
    frames[0].save(OUTD / "scenarios.gif", save_all=True, append_images=frames[1:], duration=2200, loop=0, optimize=True)
    for r in res:
        (OUTD / f"_frame_{r['id']}.png").unlink()


if __name__ == "__main__":
    res = json.load(open(OUTD / "scenarios.json"))
    patches = pd.read_csv(S2 / "patches.csv")
    small_multiples(res, patches)
    robustness(res)
    gif(res, patches)
    print("[s2d] scenario figures written")
