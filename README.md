# CPS School Access

CPS School Access maps public high school assignments, school outcomes, and
travel to selective-enrollment schools across Chicago. It combines Chicago
Public Schools (CPS) school-year 2024–25 data with ACS 2020–24 estimates.

**[Live map](https://chicago-school-gap.vercel.app)** ·
[Findings and methods](analysis/FINDINGS.md)

![Chicago community areas grouped by school outcomes and access, with selective-enrollment school pins](docs/demo2.png)

- Explore 77 community areas grouped by assigned-school outcomes, local school
  outcomes, school counts, and selective-school access.
- Click an area to compare schools located there with citywide medians, inspect
  assigned schools, and view demographic context.
- Compare driving and CTA travel times to selective schools, with precomputed
  routes from each tract's Census internal point.
- Inspect profiles for 170 CPS high schools. Selective schools appear at all zoom
  levels; other school pins appear when zoomed in. Toggle CTA rail and bus layers
  for transit context.

The results describe geographic access and enrolled students' outcomes. They do
not measure school effectiveness or admission odds. Tract assignments approximate
attendance boundaries; this is not an address-level school locator. The map is
best viewed on a desktop browser. See [coverage and limits](analysis/FINDINGS.md#coverage-and-limits).

## Architecture

**Python and PostGIS prepare the data; React, TypeScript, and MapLibre render it.**
OSRM calculates driving times, and OpenTripPlanner calculates CTA trips using
street data and transit schedules. The pipeline exports GeoJSON and JSON to
`output/` and `frontend/public/data/`.

The frontend serves the committed files without an application backend. School
metrics and routes are computed before deployment. The browser also requests a
CARTO basemap and uses OpenStreetMap Nominatim to label clicked locations, so the
map requires network access.

| Location | Responsibility |
| --- | --- |
| `analysis/` | Downloads, spatial SQL, routing, clustering, and validation |
| `data/` | Local raw downloads and routing graphs; excluded from Git |
| `output/` | Committed analysis exports and routing matrices |
| `frontend/src/` | Data loading and selection in `App.tsx`, rendering in `components/MapView.tsx`, panels in `components/InfoPanel.tsx` |
| `frontend/public/data/` | Static data served by the map |

## Run locally

Requires **Node.js 22+ and npm**. Python, Docker, and API keys are not needed to
view the committed map.

```sh
git clone https://github.com/alanzavala1/cps-school-access.git
cd cps-school-access/frontend
npm ci
npm run dev
```

Open the local URL printed by Vite, normally **http://localhost:5173**.

From `frontend/`, check TypeScript and build the production site:

```sh
npm run build
npm run preview
```

`npm run preview` serves the build locally, normally on port 4173. For static
hosting, use `frontend/` as the project root, `npm ci && npm run build` as the
build command, and `dist/` as the publish directory. Vite uses relative asset
paths through `base: "./"`.

## Rebuild and validate the analysis

Rebuilding requires **Python 3.11+, Docker, Bash, curl, Node.js, and npm**.
Follow the [data pipeline guide](docs/DATA_PIPELINE.md) for database setup, stage
order, routing refreshes, and recovery instructions.

The clustering check compares the production implementation with scikit-learn.
Run from the repository root in PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe analysis/validate_clustering.py
```

On macOS or Linux, use `.venv/bin/python` for both commands after creating the
environment. The check writes `output/clustering_validation.txt` and exits with a
failure status if correctness thresholds fail. Initialization comparisons are
reported separately. There is no automated browser test suite.

## Documentation

- [Findings and methods](analysis/FINDINGS.md): definitions, statistical results,
  routing assumptions, and interpretation limits.
- [Data sources and fields](analysis/DATA_INVENTORY.md): source identifiers,
  transformations, coverage, and missing values.
- [Data pipeline](docs/DATA_PIPELINE.md): rebuilding exports, refreshing routing
  data, configuration, and troubleshooting.
- [Community clustering](analysis/COMMUNITY_CLUSTERING.md): model inputs,
  preprocessing, validation, and sensitivity to local selective schools.

Code is available under the [MIT license](LICENSE). Source data retain their
providers' terms.
