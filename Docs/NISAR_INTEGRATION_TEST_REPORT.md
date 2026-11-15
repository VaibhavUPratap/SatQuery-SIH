# NISAR Phase 6 Integration Test Report

**Project:** SatQuery-SIH  
**Test date:** 15 November 2026  
**Branch:** `phase6-integration-qa`

## 1. Scope

This QA pass tested the existing Phase 2–5 NISAR integration without rerunning
HDF5 extraction or temporal analysis. Tests covered the declared Python
dependency, FastAPI NISAR routes, processed raster and GeoJSON integrity, the
React build, and the live browser workflow.

## 2. Dependency resolution

`requirements.txt` declares `fpdf2>=2.8.0`. The report generator imports
`from fpdf import FPDF`, which is the module name provided by the `fpdf2`
package; the legacy `fpdf` package was not declared. Installing the declared
dependency (`fpdf2 2.9.0`) resolved the previous backend import blocker.

No dependency manifest change was required.

## 3. Executed test cases

| ID | Test | Expected result | Actual result | Status |
|---|---|---|---|---|
| DEP-01 | Import FastAPI after installing declared PDF dependency | Application imports successfully | `backend.api.main` imported; 23 routes registered | PASS |
| API-01 | Start Uvicorn on `127.0.0.1:8000` | Server starts and responds | Catalog returned HTTP 200 in 0.001 s | PASS |
| API-02 | `GET /api/v1/nisar/bengaluru/case-study` | Valid verified catalog JSON | EPSG:32643, 10 m, two observations, HH/HV and four area rows returned | PASS |
| API-03 | Serve compact HH/HV GeoJSON and PNG assets | Existing assets resolve | GeoJSON HTTP 200; PNG HTTP 200 | PASS |
| API-04 | Missing asset request | HTTP 404 | HTTP 404 JSON response | PASS |
| API-05 | Existing `/search` route | Valid search response | HTTP 200; response envelope contained two granules | PASS |
| API-06 | Invalid `/validate` and `/preview` uploads | Explicit validation error | Both returned HTTP 400 for invalid HDF5 bytes | PASS |
| API-07 | `/synthesize` with a small test product | Valid synthetic response | HTTP 200 and `metadata.is_nisar == true` | PASS |
| API-08 | WGS84 candidate-region map route | Valid EPSG:4326 GeoJSON | HH and HV returned HTTP 200 with lon/lat coordinates | PASS |
| GEO-01 | Measurement, mask, and change raster metadata | Common validated grid | 20 rasters: 4382 × 3920, EPSG:32643, 10 m, identical transform/bounds | PASS |
| GEO-02 | Source candidate GeoJSON | Projected geometries remain intact | Declared EPSG:32643 and UTM coordinate ranges verified | PASS |
| FE-01 | `npm run build` | Production bundle builds | Vite build completed successfully | PASS |
| FE-02 | Login and case-study navigation | Case-study view opens | Browser rendered the verified Bengaluru view | PASS |
| FE-03 | Leaflet map and AOI | Map and Bengaluru AOI display | Leaflet map, zoom controls, OSM attribution, and AOI displayed | PASS |
| FE-04 | HH/HV switching | Layer, labels, previews, and statistics change | HH and HV values changed to the corresponding real summaries/assets | PASS |
| FE-05 | Browser console/network | No integration errors | No console errors or failed requests during successful flow | PASS |
| FE-06 | Backend unavailable behavior | User-visible failure | Login displayed `Failed to fetch`; no silent success fallback | PASS |
| TEST-01 | Existing `tests/test_nisar_ingestion.py` | NISAR regression tests pass | 6 passed in 1.83 s | PASS |

## 4. Defect found and fixed

The original candidate-region GeoJSON files are correctly projected in
EPSG:32643. Leaflet, however, interprets GeoJSON coordinates as longitude and
latitude. The first integration check detected UTM coordinates being sent
directly to the map.

The original projected assets were preserved. A read-only backend route now
transforms candidate geometries to EPSG:4326 for web-map display, while the
catalog continues to expose the original EPSG:32643 files for scientific use.
The frontend consumes only the transformed map route.

## 5. Performance observations

Measured local response times:

- Catalog JSON: 0.001 s, 2.8 KB.
- HH transformed candidate GeoJSON: 0.337 s, 1.26 MB.
- Original HH candidate GeoJSON asset: 0.003 s, 1.16 MB.
- HH preview PNG: 0.005 s, 2.17 MB.

The frontend does not load the large raw HDF5 products or measurement
GeoTIFFs. It loads compact catalog metadata, transformed candidate geometry,
and display PNGs.

## 6. Limitations

- Browser validation was performed manually through the live Vite page and
  Playwright interaction; no browser test framework was added.
- OSM basemap tiles require network access and are external context, not
  scientific NISAR data.
- The frontend currently displays compact previews and candidate polygons
  rather than streaming full measurement GeoTIFFs.
- The source GeoJSON geometries are projected EPSG:32643; only the map-view
  API response is transformed to EPSG:4326.
- The environmental interpretation remains explicitly unconfirmed because
  no contemporaneous external land-cover or event dataset was verified.

## 7. Final status

The verified NISAR workflow is operational across:

`processed GeoTIFF / GeoJSON → FastAPI catalog and assets → React → Leaflet`

All executed Phase 6 tests passed after the dependency resolution and CRS map
display fix. No validated source datasets were overwritten, and no HDF5
extraction or temporal analysis was repeated.
