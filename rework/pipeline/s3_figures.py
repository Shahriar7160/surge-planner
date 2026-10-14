"""Step 3 figures: ward briefs per site (modules, areas by zone) and the module schedule."""
import json

import matplotlib
import pandas as pd

from s2_figures import BLUE, INK, INK2, INK3, ORANGE, PAPER, RED, RULE
from s3_run import S3

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.patches as mp  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ZONE = {"red": "#e34948", "amber": "#eda100", "green": "#1baf7a", "service": "#8a887f"}
ZONE_NAME = {"red": "high risk", "amber": "transition", "green": "low risk", "service": "services / outdoor"}
WARD_COL = {"suspect": "#f6b9b2", "probable": "#ee8b81", "confirmed": "#b8302f"}
plt.rcParams.update({"font.family": "Inter", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def fig_briefs():
    B = json.load(open(S3 / "briefs.json"))["sites"]
    fig = plt.figure(figsize=(16, 9.2), facecolor=PAPER)
    fig.text(.03, .945, "Ward brief · generated per site", fontsize=20, weight="bold", color=INK)
    fig.text(.03, .91, "Peak demand from step 2 → wards → 12-bed modules → staff, supplies and spaces. "
             "Ratios in pipeline/s3_params.py (draft, to verify).", fontsize=11, color=INK2)
    n = len(B)
    for k, b in enumerate(B):
        x0 = .03 + k * (.94 / n)
        w = .94 / n - .02
        # header
        fig.text(x0, .86, f"{b['site_id']} · {b['near']}", fontsize=13, weight="bold", color=INK)
        fig.text(x0, .835, f"peak {b['peak_confirmed_beds']:.0f} confirmed beds", fontsize=9.5, color=INK2)
        # module blocks
        ax = fig.add_axes([x0, .53, w, .28]); ax.axis("off")
        ax.set_xlim(0, 6); ax.set_ylim(-1, 9); ax.invert_yaxis()
        row = 0
        for wd in b["wards"]:
            ax.text(0, row, f"{wd['ward']} · {wd['modules']} × 12", fontsize=9, color=INK, va="center")
            row += 0.8
            for i in range(wd["modules"]):
                ax.add_patch(mp.Rectangle((i % 6 * 1.0, row + (i // 6) * .9), .9, .7, color=WARD_COL[wd["ward"]]))
            row += (wd["modules"] - 1) // 6 * .9 + 1.4
        # area by zone
        sp = pd.DataFrame(b["spaces"])
        z = sp.groupby("zone").area_m2.sum().reindex(["red", "amber", "green", "service"]).fillna(0)
        bx = fig.add_axes([x0, .44, w, .07])
        left = 0
        for zone, a in z.items():
            bx.barh(0, a, left=left, color=ZONE[zone], height=.6)
            left += a
        bx.set_yticks([]); bx.set_xlim(0, max(pd.DataFrame(bb["spaces"]).area_m2.sum() for bb in B) * 1.02)
        bx.set_xlabel("net area by zone (m²)", fontsize=9, color=INK2)
        for sp_ in ("left", "top", "right"):
            bx.spines[sp_].set_visible(False)
        # key numbers
        s, a = b["supplies"], b["area"]
        lines = [("modules / beds", f"{b['modules_total']} / {b['beds_total']}"),
                 ("staff (per shift)", f"{b['staff_total']} ({b['staff_per_shift']})"),
                 ("water", f"{s['water_l_day'] / 1000:,.0f} m³/day"),
                 ("power", f"{s['power_kw']} kW"),
                 ("medical waste", f"{s['medical_waste_kg_day'] / 1000:.1f} t/day"),
                 ("PPE sets", f"{s['ppe_sets_day']:,}/day"),
                 ("plot (fenced)", f"{a['plot_m2'] / 10000:.2f} ha ≈ {a['plot_side_m']} m square"),
                 ("fits on site?", "yes" if a["fits"] else "NO")]
        for i, (k_, v) in enumerate(lines):
            fig.text(x0, .335 - i * .032, k_, fontsize=9.5, color=INK2)
            fig.text(x0 + w, .335 - i * .032, v, fontsize=9.5, color=INK, ha="right", weight="bold")
    handles = [mp.Patch(color=ZONE[z], label=ZONE_NAME[z]) for z in ZONE] + \
              [mp.Patch(color=WARD_COL[w], label=f"{w} module") for w in WARD_COL]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5, .005), ncol=7, frameon=False, fontsize=9.5)
    fig.savefig(S3 / "fig_7_ward_briefs.png", dpi=115, facecolor=PAPER)


def fig_schedule():
    s = pd.read_csv(S3 / "schedule.csv", parse_dates=["week"])
    cols = [BLUE, ORANGE, "#1baf7a", "#6250d6"]
    fig, ax = plt.subplots(figsize=(13, 5.6), facecolor=PAPER)
    fig.subplots_adjust(left=.07, right=.86, top=.8, bottom=.12)
    seen = {}
    for (sid, g), c in zip(s.groupby("site_id"), cols):
        ax.step(g.week, g.confirmed_modules, where="post", color=c, lw=2.2)
        y = g.confirmed_modules.iloc[-1]
        dy = seen.get(y, 0)
        seen[y] = dy + 0.45
        ax.text(g.week.iloc[-1] + pd.Timedelta(days=2), y - dy, f" {sid}", color=c, va="center", fontsize=10, weight="bold")
    ax.set_ylabel("confirmed-ward modules in use", color=INK2)
    ax.grid(axis="y", color=RULE, lw=.8)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    fig.text(.07, .93, "Deployment schedule · modules grow with the forecast", fontsize=16, weight="bold", color=INK)
    fig.text(.07, .87, "Weekly confirmed-ward modules per site from the opening date. Suspect and probable wards are "
             "added at full size from day one.", fontsize=10.5, color=INK2)
    fig.savefig(S3 / "fig_8_schedule.png", dpi=115, facecolor=PAPER)


if __name__ == "__main__":
    fig_briefs(); fig_schedule()
    print("[s3] figures written")
