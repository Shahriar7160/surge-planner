"""Minimal shapefile/DBF reader (no GDAL) + study-area crop.

Reads the 2014 OSM layers in References/Data and returns geometry clipped to
the Forest Guinea study window used in the 2015 Grasshopper definitions.
"""
import struct
from pathlib import Path

DATA = Path(__file__).resolve().parents[3] / "References" / "Data"

# Same window as the 2015 MeerkatGIS crop (places.mkgis): Gueckedou / Macenta / Kissidougou
BBOX = (-10.83, 8.00, -9.03, 9.23)  # lon_min, lat_min, lon_max, lat_max


def read_dbf(path):
    with open(path, "rb") as f:
        n, hl, rl = struct.unpack("<xxxxIHH20x", f.read(32))
        fields = []
        while True:
            b = f.read(32)
            if b[0] == 13:
                break
            fields.append((b[:11].split(b"\0")[0].decode(), b[16]))
        f.seek(hl)
        rows = []
        for _ in range(n):
            r = f.read(rl)
            o, d = 1, {}
            for name, ln in fields:
                d[name] = r[o:o + ln].decode("utf8", "ignore").strip()
                o += ln
            rows.append(d)
    return rows


def read_shp(path):
    """Yield (shape_type, parts) where parts is a list of [(x, y), ...]."""
    with open(path, "rb") as f:
        f.seek(100)
        while True:
            h = f.read(8)
            if len(h) < 8:
                break
            _, clen = struct.unpack(">ii", h)
            rec = f.read(clen * 2)
            st = struct.unpack("<i", rec[:4])[0]
            if st == 0:
                yield st, []
            elif st == 1:
                x, y = struct.unpack("<2d", rec[4:20])
                yield st, [[(x, y)]]
            elif st in (3, 5):
                npart, npt = struct.unpack("<2i", rec[36:44])
                idx = list(struct.unpack(f"<{npart}i", rec[44:44 + 4 * npart]))
                off = 44 + 4 * npart
                pts = struct.unpack(f"<{2 * npt}d", rec[off:off + 16 * npt])
                xy = list(zip(pts[0::2], pts[1::2]))
                idx.append(npt)
                yield st, [xy[idx[i]:idx[i + 1]] for i in range(npart)]
            else:
                yield st, []


def inside(x, y, pad=0.0):
    a, b, c, d = BBOX
    return a - pad <= x <= c + pad and b - pad <= y <= d + pad


def layer(shp, dbf=None, keep=lambda row: True):
    rows = read_dbf(DATA / dbf) if dbf else None
    out = []
    for i, (st, parts) in enumerate(read_shp(DATA / shp)):
        if not parts:
            continue
        row = rows[i] if rows else {}
        if not keep(row):
            continue
        if any(inside(x, y, 0.05) for p in parts for x, y in p[:: max(1, len(p) // 8)] + [p[-1]]):
            out.append((row, parts))
    return out


def load_all():
    return {
        "places": layer("places/places.shp", "places/places.dbf"),
        "roads": layer("roads/roads.shp", "roads/roads.dbf"),
        "waterways": layer("waterways/waterways.shp", "waterways/waterways.dbf"),
        "landuse": layer("landuse/Guinea_landuse.shp", "landuse/Guinea_landuse.dbf"),
        "natural": layer("Guinea natural areas/Guinea_natural_areas.shp",
                         "Guinea natural areas/Guinea_natural_areas.dbf"),
        "cell": layer("Guinea Cellular Coverage/Guinea_Cellular_Coverage.shp",
                      "Guinea Cellular Coverage/Guinea_Cellular_Coverage.dbf"),
    }


if __name__ == "__main__":
    from collections import Counter
    L = load_all()
    for k, v in L.items():
        print(k, len(v), Counter(r.get("type", "") for r, _ in v).most_common(10))
    print([ (r["name"], r["type"]) for r, _ in L["places"] if r["type"] in ("city", "town")])
