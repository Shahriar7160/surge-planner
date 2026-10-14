"""Step 4 — export the briefs and the reference layouts as plain CSV for a native Grasshopper definition.

    python pipeline/s4_gh_export.py
Writes data/s4/gh/:
  briefs_gh.csv          one row per site, fixed columns (read with Read File → Split Text)
  reference_<site>.csv   every rectangle of the Python layout (name, zone, kind, group, x, y, w, h)
  reference_checks.csv   expected check values per site
  fig_12_groups.png      S1 plan coloured by build-guide group (D–K)
"""
import json

import matplotlib
import pandas as pd

from config import OUT

matplotlib.use("Agg")
import matplotlib.patches as mp  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

S3, S4 = OUT.parent / "s3", OUT.parent / "s4"
GH = S4 / "gh"
GH.mkdir(exist_ok=True)

SPACES = ["triage", "family_visiting", "laundry", "morgue", "incinerator_waste", "admin_data", "lab", "pharmacy",
          "stores", "staff_rest", "water_treatment", "generator", "loading_zone", "staff_dormitory", "burial_area"]


def group_of(r):
    """Build-guide group that creates this part (see grasshopper/GH_BUILD_GUIDE.md and GH_TUTORIAL.md)."""
    n, k = r["name"], r["kind"]
    if k == "ward_module":
        return "D"
    if k in ("donning", "doffing", "store"):
        return "E"
    if n in ("triage", "family_visiting", "patient_corridor"):
        return "F"
    if n in ("admin_data", "lab", "pharmacy", "stores", "staff_rest"):
        return "G"
    if n in ("patient_discharge", "laundry", "morgue", "incinerator_waste"):
        return "H"
    return "I"


def main():
    briefs = json.load(open(S3 / "briefs.json"))["sites"]
    layouts = {L["site_id"]: L for L in json.load(open(S4 / "layouts.json"))["layouts"]}
    checks = json.load(open(S4 / "checks.json"))
    rows = []
    for b in briefs:
        sp = {s["space"]: s["area_m2"] for s in b["spaces"]}
        wm = {w["ward"]: w["modules"] for w in b["wards"]}
        L = layouts[b["site_id"]]
        r = {"site_id": b["site_id"], "near": b["near"],
             "modules_suspect": wm["suspect"], "modules_probable": wm["probable"], "modules_confirmed": wm["confirmed"],
             "beds_total": b["beds_total"]}
        r.update({f"area_{s}": round(sp[s], 1) for s in SPACES})
        r.update({"rotation_deg": L["placement"]["rotation_deg"], "mirrored": int(L["placement"]["mirrored"]),
                  "lon": b["lon"], "lat": b["lat"]})
        rows.append(r)
        ref = pd.DataFrame([{**{k: x[k] for k in ("name", "zone", "kind", "x", "y", "w", "h")}, "group": group_of(x)}
                            for x in L["rects"]])
        ref.to_csv(GH / f"reference_{b['site_id']}.csv", index=False)
    pd.DataFrame(rows).to_csv(GH / "briefs_gh.csv", index=False)
    ck = pd.DataFrame([{"site_id": s, "beds": c["beds_in_layout"], "fence_w": c["fenced_size_m"][0],
                        "fence_h": c["fenced_size_m"][1], "staff_walk_m": c["max_staff_walk_m"],
                        "patient_path_m": c["patient_path_m"], "ok": c["ok"]} for s, c in checks.items()])
    ck.to_csv(GH / "reference_checks.csv", index=False)

    # diagram: which group builds which part (S1)
    cols = {"D": "#d4605a", "E": "#f7d488", "F": "#9ec5f4", "G": "#a9dfc6", "H": "#c9b8f0", "I": "#dedbd2"}
    names = {"D": "D · ward modules", "E": "E · donning / PPE / doffing per row", "F": "F · triage, family, patient corridor",
             "G": "G · low-risk column", "H": "H · far end", "I": "I · services, dormitory, burial"}
    L = layouts["S1"]
    fig, ax = plt.subplots(figsize=(12, 12), facecolor="#f7f6f2")
    for x in L["rects"]:
        g = group_of(x)
        ax.add_patch(mp.Rectangle((x["x"], x["y"]), x["w"], x["h"], fc=cols[g], ec="#55534e", lw=.6))
        if x["w"] * x["h"] >= 36 and x["kind"] != "ward_module":
            ax.text(x["x"] + x["w"] / 2, x["y"] + x["h"] / 2, x["name"].replace("_", " "), ha="center", va="center", fontsize=6.5)
    fx, fy, fw, fh = L["fences"]["outer"]
    ax.add_patch(mp.Rectangle((fx, fy), fw, fh, fc="none", ec="#141413", lw=1.2, ls="--"))
    ax.add_patch(mp.Rectangle(tuple(L["fences"]["red_inner"][:2]), *L["fences"]["red_inner"][2:], fc="none", ec="#b8302f",
                              lw=1, ls=":"))
    xs, ys = zip(*L["patient_flow"])
    ax.plot(xs, ys, color="#2a78d6", lw=2)
    for g in cols:
        ax.add_patch(mp.Rectangle((0, 0), 0, 0, fc=cols[g], label=names[g]))
    ax.plot([], [], color="#141413", ls="--", label="J · outer fence (offset of bounding box)")
    ax.plot([], [], color="#b8302f", ls=":", label="J · inner red fence")
    ax.plot([], [], color="#2a78d6", lw=2, label="K · patient flow polyline")
    ax.legend(loc="upper right", fontsize=9, frameon=True)
    ax.set_aspect("equal"); ax.autoscale()
    ax.set_title("S1 reference layout coloured by build-guide group (local metres, origin at bottom-left of the low-risk column)",
                 loc="left", fontsize=11, weight="bold")
    ax.grid(color="#e0ddd4", lw=.5)
    ax.set_xticks(range(-12, 160, 12)); ax.set_yticks(range(-24, 130, 12))
    ax.tick_params(labelsize=7)
    fig.savefig(GH / "fig_12_groups.png", dpi=110, facecolor="#f7f6f2", bbox_inches="tight")
    print(f"[s4-gh] wrote {GH}: briefs_gh.csv, reference_S*.csv, reference_checks.csv, fig_12_groups.png")


if __name__ == "__main__":
    main()
