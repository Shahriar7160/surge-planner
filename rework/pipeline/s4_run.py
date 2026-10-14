"""Step 4 — generate ward layouts for every site, check them, place them on the map, draw them.

    python pipeline/s4_run.py
Outputs in data/s4/: layouts.json (for Grasshopper), checks.json, footprints.geojson (on the map),
fig_9_plans.png, fig_10_axonometric.png, README.md
"""
import json
import math

import matplotlib
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

import s4_params as G
from config import BBOX, OUT
from s4_layout import check, layout

matplotlib.use("Agg")
import matplotlib.patches as mp  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402

S3 = OUT.parent / "s3"
S4 = OUT.parent / "s4"
S4.mkdir(exist_ok=True)
INK, INK2, INK3, RULE, PAPER = "#141413", "#55534e", "#8a887f", "#d9d6cc", "#f7f6f2"
FILL = {"red": "#f3b3ad", "amber": "#f7d488", "green": "#a9dfc6", "service": "#dedbd2"}
EDGE = {"red": "#b8302f", "amber": "#c98500", "green": "#138a5e", "service": "#8a887f"}
WARD = {"suspect": "#f6b9b2", "probable": "#ee8b81", "confirmed": "#d4605a"}
LAT0 = (BBOX[1] + BBOX[3]) / 2
MX, MY = 111320 * math.cos(math.radians(LAT0)), 110570      # metres per degree


# ---------------------------------------------------------------- map placement
def orientation(site):
    """Rotate so the road side (local -y) faces the nearest truck road; mirror so the incinerator is downwind."""
    roads = json.load(open(OUT / "osm2014" / "roads.geojson"))["features"]
    pts = np.vstack([np.asarray(f["geometry"]["coordinates"] if f["geometry"]["type"] == "LineString"
                                else f["geometry"]["coordinates"][0])
                     for f in roads if f["properties"].get("type") not in ("path", "footway", "pedestrian")])
    d, i = cKDTree(np.c_[pts[:, 0] * MX, pts[:, 1] * MY]).query([site["lon"] * MX, site["lat"] * MY])
    vx, vy = (pts[i, 0] - site["lon"]) * MX, (pts[i, 1] - site["lat"]) * MY
    theta = math.atan2(vy, vx) + math.pi / 2          # local -y → towards the road
    # incinerator sits at local (+x, +y); downwind bearing = wind-from + 180°
    down = math.radians(90 - (G.WIND_FROM_DEG + 180))  # compass → math angle
    inc_dir = math.atan2(math.sin(theta) + math.cos(theta), math.cos(theta) - math.sin(theta))  # rotate (1,1)
    mirror = math.cos(inc_dir - down) < 0
    return theta, mirror, d


def to_lonlat(x, y, site, theta, mirror, cx, cy):
    x, y = x - cx, y - cy
    if mirror:
        x = -x
    X = x * math.cos(theta) - y * math.sin(theta)
    Y = x * math.sin(theta) + y * math.cos(theta)
    return site["lon"] + X / MX, site["lat"] + Y / MY


def footprints(layouts, briefs):
    feats = []
    for L, b in zip(layouts, briefs):
        theta, mirror, d = orientation(b)
        L["placement"] = {"rotation_deg": round(math.degrees(theta), 1), "mirrored": mirror, "road_m": round(d)}
        fx, fy, fw, fh = L["fences"]["outer"]
        cx, cy = fx + fw / 2, fy + fh / 2
        for r in L["rects"] + [{"name": "outer_fence", "zone": "fence", "x": fx, "y": fy, "w": fw, "h": fh, "kind": "fence"}]:
            ring = [to_lonlat(px, py, b, theta, mirror, cx, cy) for px, py in
                    [(r["x"], r["y"]), (r["x"] + r["w"], r["y"]), (r["x"] + r["w"], r["y"] + r["h"]),
                     (r["x"], r["y"] + r["h"]), (r["x"], r["y"])]]
            feats.append({"type": "Feature", "properties": {"site_id": b["site_id"], "name": r["name"],
                                                            "zone": r["zone"], "kind": r["kind"]},
                          "geometry": {"type": "Polygon", "coordinates": [[[round(a, 7), round(c, 7)] for a, c in ring]]}})
    json.dump({"type": "FeatureCollection", "features": feats}, open(S4 / "footprints.geojson", "w"))


# ---------------------------------------------------------------- drawings
LABEL = {"admin_data": "admin", "staff_rest": "staff rest", "water_treatment": "water", "loading_zone": "loading",
         "patient_discharge": "discharge", "incinerator_waste": "incin.", "family_visiting": "family",
         "staff_dormitory": "dormitory", "burial_area": "burial", "patient_corridor": ""}


OFF_PLAN = {"staff_dormitory", "burial_area"}


def plan(ax, L, b, c):
    for r in [r for r in L["rects"] if r["name"] not in OFF_PLAN]:
        if r["kind"] == "ward_module":
            fc, ec = WARD[r["ward"]], EDGE["red"]
        else:
            fc, ec = FILL[r["zone"]], EDGE[r["zone"]]
        ax.add_patch(mp.Rectangle((r["x"], r["y"]), r["w"], r["h"], fc=fc, ec=ec, lw=.7))
        if r["kind"] == "ward_module":
            for k in range(6):  # 6 beds per side
                for side in (0.6, r["w"] - 1.5):
                    ax.add_patch(mp.Rectangle((r["x"] + side, r["y"] + 1 + k * 2.8), .9, 2.0, fc="white", ec="none", alpha=.8))
        name = LABEL.get(r["name"], r["name"].split("_")[0] if r["kind"] in ("donning", "doffing", "store") else r["name"])
        if r["kind"] == "ward_module":
            name = ""
        if name and r["w"] * r["h"] >= 30:
            ax.text(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, name.replace("_", " "), ha="center", va="center",
                    fontsize=6.3 if r["w"] < 9 else 7, color=INK, rotation=90 if r["h"] > r["w"] * 1.6 and r["w"] < 7 else 0)
    for row in L["rows"]:
        ax.text(L["fences"]["red_inner"][0] + G.BAY + 1, row["y"] + G.MODULE_D + .6, f"{row['ward']} · {row['modules']}×12",
                fontsize=7, color=EDGE["red"], weight="bold")
    fx, fy, fw, fh = L["fences"]["outer"]
    ax.add_patch(mp.Rectangle((fx, fy), fw, fh, fc="none", ec=INK, lw=1.2, ls=(0, (4, 2))))
    ax.add_patch(mp.Rectangle((fx - G.FENCE_GAP, fy - G.FENCE_GAP), fw + 2 * G.FENCE_GAP, fh + 2 * G.FENCE_GAP,
                              fc="none", ec=INK, lw=.6, ls=(0, (4, 2))))
    xs, ys = zip(*L["patient_flow"])
    ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]),
                arrowprops=dict(arrowstyle="-|>", color="#2a78d6", lw=1.6))
    ax.plot(xs, ys, color="#2a78d6", lw=1.6, ls="-", zorder=5)
    ax.text(xs[0], ys[0] - 4.5, "patients in", fontsize=7, color="#2a78d6", ha="center")
    ax.annotate("road", xy=(fx + fw / 2, fy - 16), ha="center", fontsize=7, color=INK3)
    ax.set_aspect("equal"); ax.axis("off")
    on = [r for r in L["rects"] if r["name"] not in OFF_PLAN]
    x0, y0 = min(r["x"] for r in on), min(r["y"] for r in on)
    x1, y1 = max(r["x"] + r["w"] for r in on), max(r["y"] + r["h"] for r in on)
    ax.set_xlim(x0 - 4, x0 + 82); ax.set_ylim(y0 - 20, y0 + 132)   # same scale in every panel
    ax.set_title(f"{b['site_id']} · {b['near']}  —  {b['modules_total']} modules · {b['beds_total']} beds", loc="left",
                 fontsize=11, weight="bold")
    ax.text(0, -.02, f"fenced {c['fenced_size_m'][0]} × {c['fenced_size_m'][1]} m · patient path {c['patient_path_m']:.0f} m\n"
            f"longest staff walk {c['max_staff_walk_m']:.0f} m"
            f"{'' if c['staff_walk_ok'] else ' (over the ' + str(G.MAX_STAFF_WALK_M) + ' m limit)'} · "
            f"checks {'passed' if c['ok'] else 'FAILED'}\n"
            f"outside the fence (not drawn): staff dormitory {next(r['w'] * r['h'] for r in L['rects'] if r['name'] == 'staff_dormitory'):,.0f} m², "
            f"burial area {next(r['w'] * r['h'] for r in L['rects'] if r['name'] == 'burial_area'):,.0f} m²",
            transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    # scale bar
    ax.plot([x1 - 20, x1], [y1 + 3, y1 + 3], color=INK, lw=2)
    ax.text(x1 - 10, y1 + 4.5, "20 m", ha="center", fontsize=7)


def fig_plans(layouts, briefs, checks):
    fig, axs = plt.subplots(1, len(layouts), figsize=(19, 9.5), facecolor=PAPER,
                            gridspec_kw=dict(wspace=.08, left=.02, right=.99, top=.84, bottom=.09))
    for ax, L, b, c in zip(np.atleast_1d(axs), layouts, briefs, checks):
        plan(ax, L, b, c)
    fig.text(.02, .95, "Ward layouts · generated from each site's brief", fontsize=20, weight="bold", color=INK)
    fig.text(.02, .915, "Kit of parts: 12-bed ward module 6 × 18 m (2015 origami tent) and 6 × 6 m service bays on a 6 m grid. "
             "Rules: triage → suspect → probable → confirmed → discharge/morgue; staff green → donning → red → doffing; "
             "double fence; incinerator downwind.", fontsize=10.5, color=INK2)
    handles = [mp.Patch(fc=FILL[z], ec=EDGE[z], label=n) for z, n in
               [("red", "high risk"), ("amber", "transition"), ("green", "low risk"), ("service", "services")]] + \
              [mp.Patch(fc=WARD[w], ec=EDGE["red"], label=f"{w} module") for w in WARD] + \
              [plt.Line2D([], [], color="#2a78d6", lw=1.6, label="patient flow (one-way)")]
    fig.legend(handles=handles, loc="lower center", ncol=8, frameon=False, fontsize=9.5)
    fig.savefig(S4 / "fig_9_plans.png", dpi=110, facecolor=PAPER)


def iso(x, y, z):
    a = math.radians(30)
    return (x - y) * math.cos(a), (x + y) * math.sin(a) + z


def fig_axon(L, b):
    """Isometric view: ward modules as folded tents, services as boxes."""
    polys, cols = [], []
    items = []
    for r in [r for r in L["rects"] if r["name"] not in OFF_PLAN]:
        h = G.SERVICE_H if r["kind"] != "corridor" else 0.2
        items.append((r["x"] + r["y"], r, h))
    for _, r, h in sorted(items, key=lambda t: -(t[0])):
        x, y, w, d = r["x"], r["y"], r["w"], r["h"]
        base = FILL[r["zone"]] if r["kind"] != "ward_module" else WARD[r["ward"]]
        dark = EDGE["red"] if r["zone"] == "red" else EDGE.get(r["zone"], INK3)
        if r["kind"] == "ward_module":
            e, k = G.MODULE_H, G.MODULE_RIDGE
            # walls (front x-face and y-face) and two roof planes folded along the long axis (y)
            polys += [[iso(x, y, 0), iso(x + w, y, 0), iso(x + w, y, e), iso(x + w / 2, y, k), iso(x, y, e)],
                      [iso(x + w, y, 0), iso(x + w, y + d, 0), iso(x + w, y + d, e), iso(x + w, y, e)],
                      [iso(x, y, e), iso(x + w / 2, y, k), iso(x + w / 2, y + d, k), iso(x, y + d, e)],
                      [iso(x + w / 2, y, k), iso(x + w, y, e), iso(x + w, y + d, e), iso(x + w / 2, y + d, k)]]
            cols += [base, base, "#f9e3e1", "#e8a39d"]
            # origami folds on the roof
            for t in np.linspace(0, d, 7)[1:-1]:
                polys.append([iso(x + w / 2, y + t, k), iso(x + w, y + t, e), iso(x + w, y + t + .05, e), iso(x + w / 2, y + t + .05, k)])
                cols.append(dark)
        else:
            polys += [[iso(x, y, 0), iso(x + w, y, 0), iso(x + w, y, h), iso(x, y, h)],
                      [iso(x + w, y, 0), iso(x + w, y + d, 0), iso(x + w, y + d, h), iso(x + w, y, h)],
                      [iso(x, y, h), iso(x + w, y, h), iso(x + w, y + d, h), iso(x, y + d, h)]]
            cols += [base, base, base]
    fig, ax = plt.subplots(figsize=(15, 10), facecolor=PAPER)
    fx, fy, fw, fh = L["fences"]["outer"]
    ground = [iso(fx, fy, 0), iso(fx + fw, fy, 0), iso(fx + fw, fy + fh, 0), iso(fx, fy + fh, 0)]
    ax.add_collection(PolyCollection([ground], facecolors="#eceae2", edgecolors=INK3, linewidths=.8, linestyles="--"))
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="#55534e", linewidths=.35))
    ax.autoscale(); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"{b['site_id']} · {b['near']} · {b['modules_total']} folded-tent ward modules, {b['beds_total']} beds",
                 loc="left", fontsize=15, weight="bold")
    fig.savefig(S4 / "fig_10_axonometric.png", dpi=120, facecolor=PAPER, bbox_inches="tight")


def fig_variants(brief, values=(3, 5, 8)):
    """Same brief, different generator variable (modules per row) → different plans."""
    import importlib
    import s4_layout
    fig, axs = plt.subplots(1, len(values), figsize=(18, 9), facecolor=PAPER,
                            gridspec_kw=dict(wspace=.06, left=.02, right=.99, top=.84, bottom=.06))
    keep = G.MAX_MODULES_PER_ROW
    runs = []
    for v in values:
        G.MAX_MODULES_PER_ROW = v
        importlib.reload(s4_layout)
        L = s4_layout.layout(brief)
        runs.append((v, L, s4_layout.check(L, brief)))
    top = max(max(r["y"] + r["h"] for r in L["rects"] if r["name"] not in OFF_PLAN) for _, L, _ in runs)
    for ax, (v, L, c) in zip(axs, runs):
        plan(ax, L, brief, c)
        ax.set_title(f"max {v} modules per row", loc="left", fontsize=13, weight="bold")
        ax.set_xlim(L["extent"][0] - 4, L["extent"][0] + top * .62); ax.set_ylim(-22, top + 6)
    G.MAX_MODULES_PER_ROW = keep
    importlib.reload(s4_layout)
    fig.text(.02, .95, f"One variable, three layouts · {brief['site_id']} · {brief['near']}", fontsize=20, weight="bold", color=INK)
    fig.text(.02, .915, "Same brief and rules; only 'modules per row' changes. Short rows mean shorter staff walks but a "
             "longer patient path and a deeper plot; long rows do the reverse.", fontsize=10.5, color=INK2)
    fig.savefig(S4 / "fig_11_variants.png", dpi=105, facecolor=PAPER)


def main():
    briefs = json.load(open(S3 / "briefs.json"))["sites"]
    layouts, checks = [], []
    for b in briefs:
        L = layout(b)
        c = check(L, b)
        layouts.append(L); checks.append(c)
        print(f"[s4] {b['site_id']}: {len(L['rects'])} parts, {c['beds_in_layout']} beds, fenced "
              f"{c['fenced_size_m'][0]}×{c['fenced_size_m'][1]} m, staff walk {c['max_staff_walk_m']} m, "
              f"red/green contacts {len(c['red_green_contacts'])}, overlaps {len(c['overlaps'])} → "
              f"{'OK' if c['ok'] else 'FAIL'}")
    footprints(layouts, briefs)
    for L in layouts:
        print(f"[s4] {L['site_id']} placed: rotation {L['placement']['rotation_deg']}°, mirrored {L['placement']['mirrored']}, "
              f"{L['placement']['road_m']} m from road")
    json.dump({"meta": {"units": "m", "origin": "local plan, road along bottom edge", "params": "pipeline/s4_params.py"},
               "layouts": layouts}, open(S4 / "layouts.json", "w"), indent=1)
    json.dump(dict(zip([b["site_id"] for b in briefs], checks)), open(S4 / "checks.json", "w"), indent=1)
    fig_plans(layouts, briefs, checks)
    fig_axon(layouts[0], briefs[0])
    fig_variants(briefs[0])
    return layouts, checks


if __name__ == "__main__":
    main()
