# Interactive Temporal Backscatter View audit

## Current implementation

The Bengaluru experience is rendered by `frontend/src/components/NisarBengaluruView.jsx` and is opened from the existing React application; it is not a separate route or processing pipeline. The component loads the read-only `/api/v1/nisar/bengaluru/case-study` catalog, fetches polarization-specific candidate GeoJSON, and uses `react-leaflet` with an OpenStreetMap tile layer and an AOI rectangle.

Existing behavior includes:

- HH/HV selection.
- October 29 and November 10 preview selection.
- Candidate polygon display and opacity control.
- Candidate area summary rows.
- Local NISAR processing submission and polling.
- Backend execution trace display.
- Existing LangGraph-generated PDF download.
- Processing history and scientific limitations.

The backend catalog is served by `backend/api/endpoints/nisar.py`. Static processed assets are mounted by `backend/api/main.py` under `/api/v1/nisar/assets`. Candidate polygons are transformed from EPSG:32643 to EPSG:4326 by the candidate-region endpoint, so the browser does not need to load large raw HDF5 products.

## Verified data sources

The case-study outputs under `datasets/processed/bengaluru/` contain:

- Four real HH/HV observation previews.
- HH/HV temporal difference and candidate-mask PNG previews.
- HH/HV candidate-region GeoJSON.
- `candidate_area_summary.csv`.
- `temporal_statistics.csv`.
- `change_summary.json`.
- Candidate masks in GeoTIFF form.

The reported candidate totals are measured outputs: HH 5,741 pixels / 57.41 ha and HV 3,762 pixels / 37.62 ha. These are candidate radar-backscatter anomalies only; the UI must not label them as confirmed environmental events.

## Gaps found

1. The map only rendered candidate polygons and did not expose observation, difference, mask, or AOI visibility as independent controls.
2. The catalog returned area summaries but not temporal statistics or change-summary data, preventing an actual-data chart without duplicating file-serving logic in the browser.
3. There was no region table, selected-region zoom/highlight state, or coordinate readout.
4. The page showed previews as figures but had no before/after, swipe, or side-by-side comparison workspace.
5. Processing status was only shown while polling; the page did not expose a durable stage model or clear evidence/uncertainty interpretation.
6. GeoJSON and CSV exports were missing. Difference GeoTIFF exports are not present in the verified processed outputs and must be represented as unavailable.
7. The existing CSS had responsive support for the old two-column layout but no workspace-level hierarchy for scientific analysis cards.

## Upgrade plan implemented

- Extend the existing catalog endpoint with the verified temporal statistics and change summary.
- Keep the existing Leaflet architecture and add a real layer registry using the processed preview/mask assets and transformed candidate GeoJSON.
- Add observation metadata, KPI cards, layer visibility/opacity controls, map coordinate readout, fit-to-AOI, and candidate selection.
- Add a real-data HH/HV statistics panel and a before/after comparison mode using the four catalog previews.
- Add a candidate-region explorer with filtering, sorting, selected-feature highlighting, and zoom-to-region.
- Add grounded interpretation copy that separates measured observations, algorithm-generated candidates, possible explanations, and unavailable corroborating evidence.
- Add job-stage transparency, GeoJSON/CSV downloads, and reuse the existing PDF helper.
- Keep raw HDF5 and large rasters server-side; do not load source products into the browser.
- Preserve the existing processing request, job, trace, and report contracts.

## Known limitations

- Only two acquisitions are available, so no intermediate time series is invented.
- The current verified catalog exposes compact PNG displays rather than browser-ready tiled rasters or COG URLs.
- Difference GeoTIFF files are not available in the processed asset set and are intentionally shown as unavailable.
- No independent rainfall, optical, soil-moisture, land-cover, or field evidence has been verified for these candidates.
- No browser automation runner is configured in the repository; build validation and live API smoke checks remain the available automated checks.
