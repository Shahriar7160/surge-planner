#! python3
"""S.U.R.G.E. — draw a generated layout in Rhino 8 (Grasshopper Python 3 component, no server needed).

Component inputs (set type hints in Grasshopper):
    path  : str   full path to rework/data/s4/layouts.json
    site  : str   S1, S2, S3 or S4
    tent  : bool  True = ward modules as folded tents, False = plain boxes
Component outputs:
    geo, colour, name, zone   → plug geo + colour into a Custom Preview
"""
import json

import Rhino.Geometry as rg
import System.Drawing as sd

MODULE_H, MODULE_RIDGE, SERVICE_H = 2.8, 4.6, 3.0
COL = {"red": sd.Color.FromArgb(227, 73, 72), "amber": sd.Color.FromArgb(237, 161, 0),
       "green": sd.Color.FromArgb(27, 175, 122), "service": sd.Color.FromArgb(138, 136, 127)}
WARD = {"suspect": sd.Color.FromArgb(246, 185, 178), "probable": sd.Color.FromArgb(238, 139, 129),
        "confirmed": sd.Color.FromArgb(184, 48, 47)}
TOL = 0.001

# ---- check the component's inputs (names must match exactly) ----
_missing = [n for n in ["path", "site"] if n not in globals() or globals()[n] is None]
if _missing:
    raise ValueError("Missing input(s): " + ", ".join(_missing) +
                     ". Zoom in on the component, right-click each input and rename it exactly: path = full path to rework\\data\\s4\\layouts.json, site = S1..S4, tent = True/False")

tent = globals().get("tent", True)          # optional input
data = json.load(open(path))
L = next(l for l in data["layouts"] if l["site_id"] == site)

geo, colour, name, zone = [], [], [], []
for r in L["rects"]:
    if r["name"] in ("staff_dormitory", "burial_area"):
        continue
    x, y, w, d = r["x"], r["y"], r["w"], r["h"]
    if r["kind"] == "ward_module" and tent:
        prof = rg.PolylineCurve([rg.Point3d(x, y, 0), rg.Point3d(x, y, MODULE_H), rg.Point3d(x + w / 2, y, MODULE_RIDGE),
                                 rg.Point3d(x + w, y, MODULE_H), rg.Point3d(x + w, y, 0), rg.Point3d(x, y, 0)])
        b = rg.Surface.CreateExtrusion(prof, rg.Vector3d(0, d, 0)).ToBrep().CapPlanarHoles(TOL)
        c = WARD.get(r.get("ward"), COL["red"])
    else:
        h = 0.2 if r["kind"] == "corridor" else (MODULE_H if r["kind"] == "ward_module" else SERVICE_H)
        b = rg.Box(rg.BoundingBox(rg.Point3d(x, y, 0), rg.Point3d(x + w, y + d, h))).ToBrep()
        c = WARD.get(r.get("ward"), COL[r["zone"]]) if r["kind"] == "ward_module" else COL[r["zone"]]
    if b is None:                      # Rhino could not build this solid; skip it
        print("skipped (no geometry):", r["name"])
        continue
    geo.append(b); colour.append(c); name.append(r["name"]); zone.append(r["zone"])

fx, fy, fw, fh = L["fences"]["outer"]
geo.append(rg.Rectangle3d(rg.Plane.WorldXY, rg.Interval(fx, fx + fw), rg.Interval(fy, fy + fh)).ToNurbsCurve())
colour.append(sd.Color.Black); name.append("outer_fence"); zone.append("fence")

print("S.U.R.G.E.: site", site, "→", len(geo), "solids in 'geo'. If 'geo' looks empty, the OUTPUT must be named exactly geo "
      "(and colour, name, zone).")
