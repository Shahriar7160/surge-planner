"""S.U.R.G.E. ward generator as a Grasshopper Hops component.

Run this server, then in Grasshopper drop a Hops component and point it at
    http://127.0.0.1:5000/surge_layout
Change Site / MaxPerRow / Bay / Tent sliders in Grasshopper and the layout regenerates live.

Setup (once):
    cd rework
    python -m venv .venv && .venv\\Scripts\\activate          (macOS: source .venv/bin/activate)
    pip install -r requirements.txt ghhops-server rhino3dm flask
    python grasshopper/surge_hops_server.py
"""
import importlib
import json
import sys
from pathlib import Path

import ghhops_server as hs
import rhino3dm as r3
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))
import s4_layout  # noqa: E402
import s4_params  # noqa: E402

BRIEFS = ROOT / "data" / "s3" / "briefs.json"
app = Flask(__name__)
hops = hs.Hops(app)
LIST = hs.HopsParamAccess.LIST


def _rect_curve(r, z=0.0):
    pts = [r3.Point3d(r["x"], r["y"], z), r3.Point3d(r["x"] + r["w"], r["y"], z),
           r3.Point3d(r["x"] + r["w"], r["y"] + r["h"], z), r3.Point3d(r["x"], r["y"] + r["h"], z),
           r3.Point3d(r["x"], r["y"], z)]
    return r3.Curve.CreateControlPointCurve(pts, 1)


def _tent_profile(r):
    """Folded-tent cross-section at the module's front edge (extrude along +Y by r['h'] in Grasshopper)."""
    e, k = s4_params.MODULE_H, s4_params.MODULE_RIDGE
    x, y, w = r["x"], r["y"], r["w"]
    pts = [r3.Point3d(x, y, 0), r3.Point3d(x, y, e), r3.Point3d(x + w / 2, y, k), r3.Point3d(x + w, y, e),
           r3.Point3d(x + w, y, 0), r3.Point3d(x, y, 0)]
    return r3.Curve.CreateControlPointCurve(pts, 1)


def run_layout(site_id, max_per_row, bay):
    importlib.reload(s4_params)
    s4_params.MAX_MODULES_PER_ROW = int(max_per_row)
    s4_params.BAY = float(bay)
    importlib.reload(s4_layout)
    briefs = json.load(open(BRIEFS))["sites"]
    b = next(x for x in briefs if x["site_id"] == site_id)
    L = s4_layout.layout(b)
    return L, s4_layout.check(L, b)


@hops.component(
    "/surge_layout",
    name="SURGE layout",
    nickname="SURGE",
    description="Generate an Ebola treatment-unit layout from the S.U.R.G.E. brief",
    inputs=[
        hs.HopsString("Site", "S", "Site id from step 3 (S1, S2, …)", default="S1"),
        hs.HopsInteger("MaxPerRow", "M", "Ward modules side by side before a new row", default=5),
        hs.HopsNumber("Bay", "B", "Structural bay (m)", default=6.0),
    ],
    outputs=[
        hs.HopsCurve("Footprints", "F", "Plan rectangles of every part", access=LIST),
        hs.HopsString("Names", "N", "Name of each part", access=LIST),
        hs.HopsString("Zones", "Z", "red / amber / green / service", access=LIST),
        hs.HopsString("Kinds", "K", "ward_module, donning, doffing, space, …", access=LIST),
        hs.HopsCurve("TentProfiles", "T", "Folded-tent sections for ward modules (extrude along Y by 18 m)", access=LIST),
        hs.HopsCurve("PatientFlow", "P", "One-way patient route"),
        hs.HopsCurve("Fence", "Fe", "Outer fence"),
        hs.HopsString("Checks", "C", "Rule checks as JSON"),
    ],
)
def surge_layout(site, max_per_row, bay):
    L, c = run_layout(site, max_per_row, bay)
    R = [r for r in L["rects"] if r["name"] not in ("staff_dormitory", "burial_area")]
    flow = r3.Curve.CreateControlPointCurve([r3.Point3d(x, y, 0.1) for x, y in L["patient_flow"]], 1)
    fx, fy, fw, fh = L["fences"]["outer"]
    fence = _rect_curve({"x": fx, "y": fy, "w": fw, "h": fh})
    return ([_rect_curve(r) for r in R], [r["name"] for r in R], [r["zone"] for r in R], [r["kind"] for r in R],
            [_tent_profile(r) for r in R if r["kind"] == "ward_module"], flow, fence,
            json.dumps({k: v for k, v in c.items() if k not in ("red_green_contacts", "overlaps")}))


if __name__ == "__main__":
    app.run(debug=False)
