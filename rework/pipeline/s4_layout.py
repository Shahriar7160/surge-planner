"""Step 4 — automatic ward layout from the step 3 brief (rule-based generator).

Layout grammar (local metres; road along the bottom edge, flow runs upward):

    ┌ outer fence ────────────────────────────────────────────────┐
    │ GREEN column │ fence │ DON/DOFF │ ward modules … │ patient  │  ← morgue, discharge,
    │ (lab, pharm, │  gap  │ per row  │ (red)          │ corridor │    laundry, incinerator
    │ stores, rest)│       │          │                │ one-way  │    at the far (downwind) end
    │              │       │ TRIAGE (amber) ── patient gate ─────│
    └ services strip: loading, water, generator ── road ─────────┘

Rules encoded:
  - patients enter only through triage, then suspect → probable → confirmed → discharge / morgue
  - staff go green → donning → red ward → doffing → green (donning/doffing at the start of every row)
  - no red space touches a green space except through donning/doffing (checked)
  - double fence (1 m) between the green column and the red block
  - incinerator at the downwind corner (the plan is mirrored if needed when placed on the map)
"""
import math

import s4_params as G


def _bays(area, depth=G.BAY):
    """Width in whole bays for a space of given area and depth."""
    return max(1, math.ceil(area / depth / G.BAY)) * G.BAY


def rect(name, zone, x, y, w, h, kind="space", **kw):
    return {"name": name, "zone": zone, "x": round(x, 2), "y": round(y, 2), "w": round(w, 2), "h": round(h, 2),
            "kind": kind, **kw}


def layout(brief):
    sp = {s["space"]: s for s in brief["spaces"]}
    R = []                                            # rectangles
    flow = []                                         # patient flow polyline
    green_w = G.GREEN_COL_BAYS * G.BAY
    x_red = green_w + G.FENCE_GAP                     # red block starts after the fence gap
    x_mod = x_red + G.BAY                             # ward modules start after the donning/doffing column

    # ---------------- triage at the bottom of the red block (patient gate from the road)
    n_row_max = min(G.MAX_MODULES_PER_ROW, max(w["modules"] for w in brief["wards"]))
    row_len = n_row_max * G.MODULE_W
    triage_w = _bays(sp["triage"]["area_m2"])
    y = 0.0
    R.append(rect("triage", "amber", x_red, y, max(triage_w, G.BAY * 2), G.BAY, kind="space"))
    R.append(rect("family_visiting", "amber", x_red + max(triage_w, 2 * G.BAY), y,
                  _bays(sp["family_visiting"]["area_m2"]), G.BAY))
    flow.append((x_red + G.BAY, y + G.BAY / 2))
    y += G.BAY + G.ROW_GAP

    # ---------------- ward rows: suspect → probable → confirmed
    x_corr = x_mod + row_len                          # patient corridor runs up the right side
    flow.append((x_corr + G.PATIENT_CORRIDOR / 2, G.BAY / 2))   # along the triage front to the corridor
    rows = []
    for ward in brief["wards"]:
        n = ward["modules"]
        k = 0
        while k < n:
            m = min(n_row_max, n - k)
            ry = y
            # donning (green) and doffing (amber) at the start of the row; PPE store between them
            R.append(rect(f"donning_{ward['ward']}_{len(rows) + 1}", "green", x_red, ry, G.BAY, G.BAY, kind="donning"))
            R.append(rect(f"ppe_store_{len(rows) + 1}", "green", x_red, ry + G.BAY, G.BAY, G.BAY, kind="store"))
            R.append(rect(f"doffing_{ward['ward']}_{len(rows) + 1}", "amber", x_red, ry + 2 * G.BAY, G.BAY, G.BAY,
                          kind="doffing"))
            for j in range(m):
                R.append(rect(f"{ward['ward']}_M{k + j + 1}", "red", x_mod + j * G.MODULE_W, ry, G.MODULE_W,
                              G.MODULE_D, kind="ward_module", ward=ward["ward"], beds=12))
            rows.append({"ward": ward["ward"], "y": ry, "modules": m})
            flow.append((x_corr + G.PATIENT_CORRIDOR / 2, ry + G.MODULE_D / 2))
            k += m
            y += G.MODULE_D + G.ROW_GAP
    R.append(rect("patient_corridor", "red", x_corr, G.BAY, G.PATIENT_CORRIDOR, y - G.BAY - G.ROW_GAP,
                  kind="corridor"))

    # ---------------- far end: discharge, laundry (amber) · morgue, incinerator (red)
    yt = y
    R.append(rect("patient_discharge", "amber", x_red, yt, G.BAY, G.BAY))
    laundry_w = _bays(sp["laundry"]["area_m2"])
    R.append(rect("laundry", "amber", x_red + G.BAY, yt, laundry_w, G.BAY))
    morgue_w = _bays(sp["morgue"]["area_m2"])
    # morgue at the top of the patient corridor, but never over the laundry (narrow rows push it right)
    mx = max(x_corr + G.PATIENT_CORRIDOR - morgue_w, x_red + G.BAY + laundry_w + G.FENCE_GAP)
    R.append(rect("morgue", "red", mx, yt, morgue_w, G.BAY))
    R.append(rect("incinerator_waste", "red", max(x_corr + G.PATIENT_CORRIDOR, mx + morgue_w) + G.FENCE_GAP, yt,
                  _bays(sp["incinerator_waste"]["area_m2"]), G.BAY))
    flow.append((x_corr + G.PATIENT_CORRIDOR / 2, yt + G.BAY / 2))
    top = yt + G.BAY

    # ---------------- green column, stacked bottom-up
    gy = 0.0
    for name in ("admin_data", "lab", "pharmacy", "stores", "staff_rest"):
        h = _bays(sp[name]["area_m2"], depth=green_w)
        R.append(rect(name, "green", 0, gy, green_w, h))
        gy += h
    top = max(top, gy)

    # ---------------- services strip below (outside the clinical fence, along the road)
    sx, sy = 0.0, -G.OUTER_MARGIN - G.BAY
    for name in ("water_treatment", "generator"):
        w = _bays(sp[name]["area_m2"])
        R.append(rect(name, "service", sx, sy, w, G.BAY))
        sx += w + G.BAY
    R.append(rect("loading_zone", "service", sx, sy - G.BAY, _bays(sp["loading_zone"]["area_m2"], depth=2 * G.BAY),
                  2 * G.BAY))

    right = max(r["x"] + r["w"] for r in R)
    # dormitory and burial area outside, to the right
    dorm_w = _bays(sp["staff_dormitory"]["area_m2"], depth=2 * G.BAY)
    R.append(rect("staff_dormitory", "service", right + G.OUTER_MARGIN * 2, 0, dorm_w, 2 * G.BAY))
    bur = max(sp["burial_area"]["area_m2"], 36)
    bw = _bays(bur, depth=3 * G.BAY)
    R.append(rect("burial_area", "service", right + G.OUTER_MARGIN * 2, top - 3 * G.BAY, bw, 3 * G.BAY))

    clinic = [r for r in R if r["zone"] != "service" and r["name"] not in ("staff_dormitory", "burial_area")]
    x0 = min(r["x"] for r in clinic) - G.OUTER_MARGIN
    y0 = min(r["y"] for r in clinic) - G.OUTER_MARGIN
    x1 = max(r["x"] + r["w"] for r in clinic) + G.OUTER_MARGIN
    y1 = max(r["y"] + r["h"] for r in clinic) + G.OUTER_MARGIN
    fences = {
        "outer": [x0, y0, x1 - x0, y1 - y0],
        "red_inner": [x_red - G.FENCE_GAP / 2, G.BAY + G.ROW_GAP / 2, x1 - G.OUTER_MARGIN - x_red + G.FENCE_GAP,
                      top - G.BAY - G.ROW_GAP / 2],
    }
    return {"site_id": brief["site_id"], "rects": R, "patient_flow": flow, "rows": rows, "fences": fences,
            "extent": [min(r["x"] for r in R), min(r["y"] for r in R), max(r["x"] + r["w"] for r in R),
                       max(r["y"] + r["h"] for r in R)]}


# ---------------------------------------------------------------- checks
def _touch(a, b, tol=0.01):
    ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
    oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
    return (ox > tol and abs(oy) <= tol) or (oy > tol and abs(ox) <= tol) or (ox > tol and oy > tol)


def check(L, brief):
    R = L["rects"]
    interface = {"donning", "doffing", "store"}
    bad = [(a["name"], b["name"]) for i, a in enumerate(R) for b in R[i + 1:]
           if {a["zone"], b["zone"]} == {"red", "green"} and _touch(a, b)
           and not ({a["kind"], b["kind"]} & interface)]
    overlaps = [(a["name"], b["name"]) for i, a in enumerate(R) for b in R[i + 1:]
                if min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]) > .01
                and min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]) > .01]
    modules = [r for r in R if r["kind"] == "ward_module"]
    beds = sum(r["beds"] for r in modules)
    walk = max(r["x"] + r["w"] - (L["fences"]["red_inner"][0] + G.BAY) for r in modules)
    fx, fy, fw, fh = L["fences"]["outer"]
    flow = L["patient_flow"]
    path = sum(math.dist(p, q) for p, q in zip(flow[:-1], flow[1:]))
    return {
        "beds_in_layout": beds, "beds_in_brief": brief["beds_total"], "beds_match": beds == brief["beds_total"],
        "red_green_contacts": bad, "overlaps": overlaps,
        "max_staff_walk_m": round(walk, 1), "staff_walk_ok": walk <= G.MAX_STAFF_WALK_M,
        "patient_path_m": round(path, 1),
        "fenced_area_m2": round(fw * fh), "fenced_size_m": [round(fw), round(fh)],
        "brief_plot_m2": brief["area"]["plot_m2"],
        "ok": beds == brief["beds_total"] and not bad and not overlaps and walk <= G.MAX_STAFF_WALK_M,
    }
