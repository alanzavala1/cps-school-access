# Data sources and fields

[Back to README](../README.md) · [Rebuild the data](../docs/DATA_PIPELINE.md)

The committed map combines CPS SY2024–25 school records, tract estimates from
ACS 2020–24, and precomputed travel times. Counts below describe the committed
snapshot; new downloads may change source coverage.

## Sources

[`01_download.py`](01_download.py) saves school, boundary, tract, and ACS
downloads under `data/raw/`. Nonempty files are reused unless `--force` is passed.

| Data | Source used by the code | Local file or consumer |
| --- | --- | --- |
| CPS School Progress Reports SY2425 | [Chicago Data Portal, `twrw-chuq`](https://data.cityofchicago.org/resource/twrw-chuq.json) | `data/raw/progress_sy2425.json` |
| CPS School Profile SY2425 | [Chicago Data Portal, `3dhs-m3w4`](https://data.cityofchicago.org/resource/3dhs-m3w4.json) | `data/raw/school_demographics_sy2425.json` |
| High school attendance boundaries | [Chicago Data Portal, `4kfz-zr3a`](https://data.cityofchicago.org/resource/4kfz-zr3a.geojson) | `data/raw/hs_attendance_boundaries.geojson` |
| Community areas | [Chicago Data Portal, `igwz-8jzy`](https://data.cityofchicago.org/resource/igwz-8jzy.geojson) | `data/raw/community_areas.geojson` |
| Cook County tract geometry and internal points | [Census TIGERweb tract layer](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/0) | `data/raw/tiger_tracts_2020.geojson` |
| Median household income | [Census Reporter, `acs2024_5yr`](https://api.censusreporter.org/1.0/data/show/acs2024_5yr?table_ids=B19013&geo_ids=140%7C05000US17031), table `B19013` | `data/raw/acs_b19013_cook.json` |
| Race, ethnicity, and poverty | Same Census Reporter release, tables `B03002` and `B17001` | `data/raw/acs_demographics_cook.json` |
| CTA stops, routes, and schedules | [CTA GTFS feed](https://www.transitchicago.com/downloads/sch_data/google_transit.zip) | `data/otp/cta.gtfs.zip`; OTP and [`17_cta_rail.py`](17_cta_rail.py) |
| Road and walking network | [BBBike Chicago OpenStreetMap extract](https://download.bbbike.org/osm/bbbike/Chicago/Chicago.osm.pbf) | `data/osrm/chicago.osm.pbf`; OSRM and OTP |

Downloads require no API keys. The ACS release slug and expected release name
are checked explicitly. The TIGERweb service URL, Socrata records, CTA feed, and
OSM extract are not archived or version-pinned by the downloader. The tract
filename describes the intended 2020 geography; the live service response is not
checked for that vintage. Retain raw inputs for repeatable rebuilds.

## School fields

[`02_load.py`](02_load.py) joins progress reports and school profiles by
`school_id`. It loads all 649 progress-report schools and marks the 170 rows with
`primary_category = 'HS'` as high schools. The frontend exports that category;
it does not include every school that might serve an individual high school grade.

| Source field | Loaded/exported field | Use |
| --- | --- | --- |
| `sat_grade_11_score_school` | `sat_g11` | SAT comparisons, access thresholds, and school indices; zero becomes null |
| `student_attendance_year_2` | `attendance_pct` / `attendance` | Current per-school attendance; assigned and local indices |
| `student_attendance_year_1` | `attendance_prior` | Loaded for reference; not exported to the map |
| `chronic_truancy_pct` | `truancy_pct` / `truancy` | Outcome panels and school indices; higher values mean more concern |
| `graduation_4_year_school` | `grad_4yr` | Outcome panels and school indices |
| `college_enrollment_school` | `college_enroll` | Outcome panels and school indices |
| `freshmen_on_track_school` | `freshman_ontrack` | Outcome panels and school indices |
| School latitude, longitude, address, type, and names | Point geometry and profile fields | Spatial joins, pins, and school cards |
| `student_count_total`, `student_count_low_income`, and racial/ethnic student counts | Enrollment and composition | School cards and enrollment-weighted representation comparisons |

SAT is available for 150 of 170 high schools; attendance for 167. All 45 assigned
schools in the exported tract layer have SAT, attendance, and truancy values.
Missing values remain null in the map; available components are averaged when
building the composite indices.

Use per-school fields when interpreting the progress reports. In the cached
source, `student_attendance_avg_pct` repeats the district value 88.3 and
`teacher_attendance_avg_pct` repeats 94 wherever populated. District comparison
fields such as `sat_grade_11_score_cps_avg` are not per-school outcomes. The
loader uses `student_attendance_year_2`, not `student_attendance_avg_pct`.
Dropout, mobility, college persistence, and school survey fields are not loaded.

## Tracts, assignment, and demographics

- Tract GEOIDs join TIGER geometry to ACS records. Census Reporter prefixes are
  removed to retain the standard 11-digit GEOID. The cached Cook County inputs
  contain 1,332 tract geometries and matching income records.
- A Census internal point locates each tract within an attendance boundary and
  community area. This assigns a whole tract to one school even when its polygon
  crosses a boundary. The exported map has 791 tracts with an assigned-school SAT.
- Income is the tract median from `B19013`, not an individual student's income.
  The loader retains its margin of error but does not use it in calculations.
  Income is present for 773 of the 791 exported tracts.
- `B03002` supplies non-Hispanic white share, Black share, and Hispanic share;
  `B17001` supplies the share below poverty among people with a poverty status.
  Race and poverty values are present for 789 exported tracts. These categories
  are not a complete, mutually exclusive population partition.
- SQL stores demographic shares as fractions and exports percentages to the map.
  Community summaries use unweighted tract means or medians, as described in
  [findings and methods](FINDINGS.md#how-the-map-summarizes-an-area).

[`05_proxy_tiers.sql`](05_proxy_tiers.sql) groups the 773 assigned tracts with
income into quartiles. These are income proxies, not official CPS tiers or
admissions categories, and they are not shown on the map. Official tier scores,
origin-level applications, offers, admission probabilities, and seat capacity
are not inputs to this analysis.

## Routing exports

Each committed routing CSV has 8,701 rows: 791 origins × 11 selective schools.
Blank durations represent missing routes rather than zero-minute trips.

| File in `output/` | Contents |
| --- | --- |
| `driving_times_selective.csv` | Tract and school identifiers, school SAT, road-network minutes and miles |
| `transit_times_selective.csv` | Same origin/destination pairs, with median morning CTA minutes |
| `driving_access.json`, `transit_access.json` | Per-tract access summaries and method metadata |
| `routes.geojson` | Precomputed assigned-school driving and selective-school driving/CTA paths |
| `cta_rail_lines.geojson`, `cta_rail_stations.geojson`, `cta_bus_lines.geojson` | GTFS-derived visual context layers |

See [travel-time definitions](FINDINGS.md#travel-time-definitions) for destination
selection and timing, and the [pipeline guide](../docs/DATA_PIPELINE.md#refresh-routing-and-cta-layers)
for regeneration. Neither live routing nor live service status is used by the map.
