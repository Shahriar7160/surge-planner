"""Shared settings for the S.U.R.G.E. pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # rework/
REPO = ROOT.parent
REFS = REPO / "References" / "Data"                 # 2014 OSM extracts from the 2015 project
RAW = ROOT / "data" / "raw"                         # downloads (git-ignored)
OUT = ROOT / "data" / "processed"                   # cleaned, clipped, committed

# Study window: Forest Guinea (Guéckédou · Macenta · Kissidougou).
# Same extent as the 2015 MeerkatGIS crop.
BBOX = (-10.83, 8.00, -9.03, 9.23)  # lon_min, lat_min, lon_max, lat_max (WGS84)
CRS = "EPSG:4326"
CRS_M = "EPSG:32629"                # UTM 29N, metres, for distances and areas

# Prefectures inside or touching the window (Guinea MoH spelling -> display name)
PREFECTURES = {"Gueckedou": "Guéckédou", "Macenta": "Macenta", "Kissidougou": "Kissidougou"}
