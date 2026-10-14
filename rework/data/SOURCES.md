# S.U.R.G.E. — data sources (Step 1)

Study window: lon −10.83 to −9.03, lat 8.00 to 9.23 (WGS84). This is the same extent as the 2015 MeerkatGIS crop.
It covers Guéckédou (100% of the prefecture), Macenta (82%) and Kissidougou (48%), plus border areas of Sierra Leone and Liberia.

Rebuild everything: `python pipeline/s1_fetch.py && python pipeline/s1_qa.py`. The numbers are in `DATA_QA.md` and the picture in `atlas_step1.png`.

## Collected

| Layer | File (data/processed/) | Source | Vintage | Licence | Notes |
|---|---|---|---|---|---|
| Population, 90 m | `population_hrsl_90m.tif` | Meta & CIESIN High Resolution Settlement Layer (HRSL), `s3://dataforgood-fb-data/hrsl-cogs/hrsl_general` | 2015–18 imagery, census-adjusted | CC BY 4.0 | Stand-in for WorldPop 2014 (host blocked). 30 m summed to 90 m. Guéckédou = 292,828 people. **Check this against the 2014 census.** |
| Settlement population | `settlements_population.csv` | OSM 2014 places + HRSL | — | ODbL + CC BY | Each HRSL cell is assigned to its nearest OSM settlement within 5 km. Towns split into neighbourhood points still need merging (done in Step 2). |
| Elevation, 90 m | `elevation_cop30_90m.tif` | Copernicus DEM GLO-30, `s3://copernicus-dem-30m` | 2011–15 | Copernicus DEM licence (free, attribution) | 30 m averaged to 90 m. |
| Slope, 90 m | `slope_pct_x10_90m.tif` | derived from the DEM | — | — | Values are slope % × 10 (uint16). 28% of the area has slope < 5%. |
| Land cover, 90 m | `landcover_worldcover2021_90m.tif` | ESA WorldCover 10 m v200, `s3://esa-worldcover` | 2021 | CC BY 4.0 | Majority-resampled. Classes: 10 tree, 20 shrub, 30 grass, 40 crop, 50 built, 80 water, 90 wetland. Later than 2014, so treat as indicative. |
| Admin boundaries | `admin_adm0.geojson`, `admin_adm2.geojson` | geoBoundaries gbOpen (GIN, SLE, LBR) | current | CC BY 4.0 | Clipped to the window. ADM2 = Guinea prefectures / SL & Liberia districts. |
| Roads, places, waterways, land use, natural, cell towers | `osm2014/*.geojson` | OpenStreetMap via Geofabrik/HDX, the 2015 project's extracts in `References/Data` | Sept–Dec 2014 | ODbL | Converted from shapefile and clipped. Readable in Grasshopper (e.g. with Heron or a GeoJSON reader). |
| Cases by prefecture (all metrics) | `cases_guinea_moh_by_prefecture_2014.csv` | Guinea Ministry of Health daily sitreps, digitised by Caitlin Rivers (`github.com/cmrivers/ebola`) | 22 dates, 4 Aug – 1 Oct 2014 | Free use with attribution | Long format: date, area, metric, value. Includes CTE (treatment centre) admissions, contacts and health-worker cases. |
| Cases, study area summary | `cases_study_area_2014.csv` | same | same | same | Cumulative cases, deaths and CTE use for Guéckédou, Macenta and Kissidougou. |
| Cases, Guinea weekly | `cases_guinea_who_weekly.csv` | WHO (via cmrivers/ebola `who_data/guinea.csv`) | Jan – Nov 2014 | WHO terms, attribution | National weekly counts from both the sitreps and the patient database. Used to calibrate the outbreak model. |

### What the data already tells us about the 2014 response
- The sitreps record treatment centre (CTE) admissions in **Guéckédou** and **Macenta**. Kissidougou has none in this period.
- This gives the first validation check in Step 5: does S.U.R.G.E. place sites near Guéckédou and Macenta?

## Mobility layer

<<<<<<< HEAD
| Gap                                                              | Why it matters                                            | How to fill it                                                                                                                                                        |
| ---------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Exact coordinates and opening dates of the 2014–15 ETUs/CTEs** | Main validation for siting (Step 5)                       | HDX dataset "West Africa: Ebola Treatment Centres" (WHO/OCHA). Add `data.humdata.org` to the environment's allowed domains, or download it yourself into `data/raw/`. |
| **Pre-outbreak health facilities**                               | Should-do parameter #12 (distance to hospital)            | HDX "Guinea health facilities" or healthsites.io. Allow `data.humdata.org` / `healthsites.io`.                                                                        |
| **WorldPop 2014** (preferred over HRSL for the year)             | Population for 2014 rather than about 2016                | Allow `data.worldpop.org`. HRSL works meanwhile.                                                                                                                      |
| **Weekly cases by prefecture for the whole outbreak**            | Calibrating the model per prefecture, not just nationally | WHO "Ebola data and statistics" sub-national tables on HDX. Allow `data.humdata.org`.                                                                                 |
| **Rainfall / seasonal access**                                   | Should-do parameter #14                                   | CHIRPS (`data.chc.ucsb.edu`, blocked). Alternative: a fixed rainy-season scenario (paths and tracks at 50% speed).                                                    |
| **Phone-network mobility (CDR)**                                 | The real "big data" layer used in 2014 (Flowminder)       | Not public. Present it as the speculative part of the brief and use the road-gravity model in its place.                                                              |
=======
Movement between settlements is modelled from the data above: a gravity model on **road travel time** (OSM 2014 road
graph) weighted by **HRSL population**. This is the system's mobility input. It is what couples settlements in the
outbreak model (Step 2).
>>>>>>> origin/claude/compassionate-galileo-ol5gu9

## Added by Shahriar (in `data/user/`, processed by `python pipeline/s1_fetch.py user`)

| Layer | File (data/processed/) | Source | Vintage | Licence | Check result |
|---|---|---|---|---|---|
| Health facilities (raw MoH, window only) | `health_facilities_moh.geojson` | Guinea MoH "Structures de santé", via OCHA/HDX (`structures_de_sante_guinee_vf.csv`) | 2020 list | CC0 | 2,439 rows; 666 have no coordinates; all others fall inside Guinea. **172 in the study window**: 2 hospitals (Kissidougou, Macenta), 35 health centres, 131 health posts, 3 private, 1 other. File is Mac Roman encoded with semicolons; the loader handles this. Type is taken from the name prefix (H/Hôpital, CSU/CSR/CS, PS, Clinique…). |
| Rainfall 2014, monthly | `rain_2014_monthly_mm.tif` (12 bands) | CHIRPS v2.0 Africa monthly (UCSB CHC) | 2014 | Public domain | All 12 months present; the `.gz` and extracted copies are identical. Resolution 0.05° (~5.5 km), so 25 × 36 cells over the window. Window mean mm/month, Jan→Dec: 8, 22, 34, 112, 222, 246, **446**, 412, 391, 256, 121, 24. That is 2,294 mm/yr with the wet season May–Oct, as expected for Forest Guinea. |

**Facility repair (`pipeline/s1_facilities.py`, run after `s1_fetch.py user`):** the MoH list has 666 rows without
coordinates, and the Guéckédou prefectural hospital is missing. Three passes fill the gaps. Each facility in
`health_facilities.geojson` carries a `location_source`:

| Source | Rule | In window |
|---|---|---|
| `MoH` | coordinates from the Ministry list | 172 |
| `village_match` | name matched to exactly one OSM 2014 place inside the same prefecture | 13 |
| `town_centre` | missing prefectural hospital placed at its town's OSM point (Guéckédou) | 1 |
| `synthetic` | scenario placement. Urban facilities (clinics, NGO, CSU/CMC) go 0.5–1.8 km from the prefecture town. Rural ones (PS, CSR) go to the largest settlement in the prefecture with no facility within 5 km. Prefectures only partly inside the window get that share placed. | 21 |

18 facilities are left out (the share of Kissidougou and Kérouané outside the window). Every decision is listed in
`data/facility_repair_report.csv`, and the result is mapped in `data/facility_repair.png`.

**Sensitivity:** for Guinea's population in the window, population-weighted distance to any facility goes from 3.1 to
2.8 km, and to a hospital from 41.5 to 27.6 km (almost all of that is the Guéckédou hospital). Outputs:
`dist_facility_km_90m.tif` and `dist_hospital_km_90m.tif`. Step 2 will rerun the siting with and without the repair.

Run order: `s1_fetch.py` → `s1_qa.py` → `s1_facilities.py` (appends to DATA_QA.md).

## Out of scope (decided 2026-10-12)

Exact ETU coordinates, WorldPop 2014 and whole-outbreak weekly cases by prefecture will not be added.
Validation uses the sitrep evidence instead (CTEs operating in Guéckédou and Macenta, Aug–Oct 2014), and calibration
uses the WHO national weekly series plus the prefecture sitreps.
