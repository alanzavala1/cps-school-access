# Rebuild the data

[Back to README](../README.md) · [Data sources](../analysis/DATA_INVENTORY.md) ·
[Methods](../analysis/FINDINGS.md)

The frontend can run directly from committed data. Use this guide to rebuild
the analysis or refresh routing matrices and map layers. Commands start at the
repository root unless stated otherwise.

## Prepare the environment

Requires Python 3.11+, Docker with Linux containers, Bash, curl, Node.js 22+, and
npm/npx. On Windows, use PowerShell for Python setup and Git Bash for the shell
pipeline. WSL also works with a Python environment created inside WSL.

Create the environment and install production dependencies in PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
```

On macOS or Linux, use `.venv/bin/python -m pip install -r requirements.txt`
after creating the environment. To run the independent clustering check, install
`requirements-dev.txt` instead; it includes the production dependencies.

Start the database with this command, usable in PowerShell or Bash:

```sh
docker run -d --name chicago-postgis -e POSTGRES_PASSWORD=chicago -e POSTGRES_DB=school_gap -p 5433:5432 postgis/postgis:16-3.4
```

Wait until it accepts connections:

```sh
docker exec chicago-postgis pg_isready -U postgres -d school_gap
```

The scripts use container `chicago-postgis`, database `school_gap`, and user
`postgres`. Host connections use port 5433; pipeline SQL uses `docker exec`.
If the container already exists, use `docker start chicago-postgis`. The example
has no named data volume: removing the container discards its database.

## Rebuild using committed routing data

In Git Bash on Windows:

```bash
export MSYS_NO_PATHCONV=1
PY=.venv/Scripts/python bash analysis/run_all.sh
```

On macOS or Linux:

```bash
PY=.venv/bin/python bash analysis/run_all.sh
```

[`run_all.sh`](../analysis/run_all.sh) recreates analysis tables, replacing their
contents, and overwrites exports. Retain copies of any outputs you need to
compare. It downloads missing raw files, reuses cached nonempty files, and uses
the committed driving/transit CSVs without needing routing engines.

| Stages | Result |
| --- | --- |
| `01_download.py`, `02_load.py` | Cache sources; generate and apply `analysis/load.sql` to load PostGIS tables |
| `03_finding1.sql`–`08_combined.sql`, including `06_honesty_check.py` | Tract assignments, income/composition comparisons, income proxies, selective access, and combined status |
| `11_distress.sql`, `12_community_metrics.sql` | Composite tract indices and community metrics |
| `16_routed_access.sql` | Import both routing matrices and build per-tract time summaries |
| `09_export.sql` | Export tracts, schools, city boundary, community areas, and community metrics |
| `13_community_groups.py` | Generate community groups, diagnostics, and selective-school sensitivity |
| `17_cta_rail.py` | Refresh rail, station, and bus layers if the cached CTA feed exists |
| `18_routes.py` | Refresh route paths if the default OSRM and OTP endpoints respond |
| Final copy and `npx -y mapshaper` | Copy core layers to the frontend and simplify tract geometry to 18%, retaining shapes |

When the CTA feed is absent, committed context layers are reused. When either
router is unavailable, committed routes are reused. Matrices are **never
regenerated automatically** by `run_all.sh`; use the next section to refresh them.
If both routers are running, the pipeline can overwrite route geometry even
while using older matrices. Use matching inputs and service dates when refreshing.

Both committed CSVs are required for the documented rebuild. The script's
missing-matrix fallback creates an empty `tract_routed` table without the
`closest_*` columns referenced by `09_export.sql`, so that path currently fails
at export. Restore the two CSVs from Git or regenerate them before rebuilding.

## Refresh routing and CTA layers

Run the base pipeline first: routing scripts read `output/tracts.geojson`,
`output/schools.geojson`, and `data/raw/tiger_tracts_2020.geojson`.

In Bash, choose the Python executable for this environment:

```bash
export MSYS_NO_PATHCONV=1
export PY=.venv/Scripts/python
# macOS/Linux: export PY=.venv/bin/python
```

Start OSRM before OTP, which reuses the downloaded street extract:

```bash
bash analysis/osrm/osrm_up.sh
bash analysis/otp/otp_up.sh
```

The helpers download missing inputs, build missing graphs, and replace existing
containers named `chicago-osrm` and `chicago-otp`. OTP uses image
`opentripplanner/opentripplanner:2.5.0` and a 6 GB Java heap by default. OSRM uses
the unpinned `osrm/osrm-backend` image. Graph builds need additional memory and
disk space beyond the input downloads.

Check engine readiness:

```bash
curl --fail 'http://localhost:5000/table/v1/driving/-87.63,41.88;-87.62,41.89?annotations=duration'
curl --fail -H 'Content-Type: application/json' --data '{"query":"{feeds{feedId}}"}' http://localhost:8080/otp/routers/default/index/graphql
```

Choose a weekday covered by the cached GTFS feed. The committed matrices use
`2026-07-08`, also the scripts' default. A newly downloaded feed may not cover
that date. Inspect `calendar.txt` and `calendar_dates.txt` inside
`data/otp/cta.gtfs.zip`, then export `OTP_DATE=YYYY-MM-DD` in Bash for the chosen
date; it applies to both matrix and path generation. The transit script also
checks that its date returns an itinerary for a test trip.

Generate both matrices, refresh the map data, and rebuild routes:

```bash
"$PY" analysis/14_driving_access.py
"$PY" analysis/15_transit_access.py
"$PY" analysis/17_cta_rail.py
bash analysis/run_all.sh
```

With both default endpoints available, the last command incorporates the new
CSVs and invokes `18_routes.py`. To regenerate paths separately after exporting
the updated tracts, run `"$PY" analysis/18_routes.py`. Stages 13, 17, and 18 write
their frontend files directly; the pipeline copies the core exports. Manually
copying only `output/tracts.geojson` skips the topology-aware simplification.

Review the regenerated matrices, `transit_access.json` metadata, clustering
diagnostics, and frontend data before committing. Feed downloads are live and
cached, so exact reproduction requires retaining original raw inputs, the street
extract, GTFS feed, and engine versions.

## Configuration and recovery

| Setting | Default | Scope |
| --- | --- | --- |
| `PY` | `python` | Python used by `run_all.sh` |
| `CONTAINER` | `chicago-postgis` | SQL calls in `run_all.sh` only; `06_honesty_check.py` still hard-codes `chicago-postgis` |
| `OSRM_URL` | `http://localhost:5000` | Stages 14 and 18 |
| `OTP_URL` | `http://localhost:8080/otp/routers/default/index/graphql` | Stages 15 and 18 |
| `OTP_DATE` | `2026-07-08` | Stages 15 and 18 |
| `PBF_URL` | BBBike Chicago extract | OSRM helper; downloaded only if the local PBF is absent or empty |
| `GTFS_URL` | CTA GTFS ZIP | OTP helper; downloaded only if the local ZIP is absent or empty |
| `OTP_XMX` | `6g` | Java heap for OTP build and serving |

The pipeline's router readiness probes use default ports even when stage URLs
are overridden. Run stage 18 manually for custom endpoints. Use the default
PostGIS container name for a complete pipeline run.

- **Raw source refresh:** `python analysis/01_download.py --force` bypasses the
  nonempty-file cache. It does not refresh OSM or GTFS. Back up raw files first if
  you need earlier results. ACS release mismatches stop the download; review
  `ACS_RELEASE` and `ACS_RELEASE_NAME` rather than bypassing the check.
- **Incomplete road coverage:** the OSRM helper accepts a larger extract through
  `PBF_URL=https://download.geofabrik.de/north-america/us/illinois-latest.osm.pbf`.
  Setting the URL alone does not replace a cached PBF. Move the old
  `data/osrm/chicago.osm.pbf` aside and remove `data/osrm/.built` before rerunning
  the helper. Removing only `.built` rebuilds the graph from the same extract.
- **Changed transit inputs:** OTP reuses `data/otp/chicago.osm.pbf` and
  `data/otp/graph.obj`. When changing the street extract, move both aside; when
  changing GTFS, replace `cta.gtfs.zip` and move `graph.obj` aside. Rerun the OTP
  helper to copy/build from the new inputs, then regenerate matrices and paths
  with a date inside that feed's service period.
- **Missing community metrics:** rerun the pipeline through `run_all.sh`. The
  clustering script requires `output/community_metrics.json` with 77 areas and
  170 local high schools; it rejects frontend-derived fallbacks.
- **Interrupted rebuild:** fix the failed source, container, or engine stage and
  rerun `run_all.sh`. The shell stops on errors; exports from earlier stages may
  already have changed, so inspect the diff before using or publishing them.

Stop the services after rebuilding:

```sh
docker stop chicago-osrm chicago-otp chicago-postgis
```

## Check the results

From the repository root, run the clustering check with development dependencies
installed:

```powershell
.venv/Scripts/python.exe analysis/validate_clustering.py
```

Use `.venv/bin/python` on macOS/Linux. The check validates algorithm correctness
and reports initialization sensitivity; it does not validate the full SQL or
routing pipeline. See [clustering validation](../analysis/COMMUNITY_CLUSTERING.md#validation).

From `frontend/`, run `npm run build`, then `npm run preview`. Check area and
school selection, school comparisons, route labels, and all three layer toggles.
There is no automated end-to-end pipeline or browser test suite.
