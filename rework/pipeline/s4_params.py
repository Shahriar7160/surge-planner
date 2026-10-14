"""S.U.R.G.E. step 4 — kit of parts and layout rules (the ward generator).

Kit of parts (from the 2015 origami tent, on a 6 m structural bay):
  ward module    6 × 18 m (1 × 3 bays), 12 beds, 9 m² per bed
  service bay    6 × 6 m  (1 × 1 bay), used for every support space
Change a number and rerun:  python pipeline/s4_run.py
"""

BAY = 6.0                       # structural bay (m)
MODULE_W, MODULE_D = 6.0, 18.0  # 12-bed ward module footprint (m)
MODULE_H, MODULE_RIDGE = 2.8, 4.6   # eave and ridge height of the folded tent (m), for 3D
SERVICE_H = 3.0
MAX_MODULES_PER_ROW = 5         # modules side by side before a new row starts (limits walking distance)
ROW_GAP = 3.0                   # one-way corridor between ward rows (m)
PATIENT_CORRIDOR = 3.0          # one-way patient corridor along the ward rows (m)
GREEN_COL_BAYS = 2              # width of the low-risk column (bays)
FENCE_GAP = 1.0                 # double fence between zones (MSF: 1 m)
OUTER_MARGIN = 6.0              # between buildings and the outer fence (m)
WIND_FROM_DEG = 225             # prevailing wind in the rainy season (south-west); incinerator goes downwind
MAX_STAFF_WALK_M = 45           # check: donning room to the farthest bed in its row
