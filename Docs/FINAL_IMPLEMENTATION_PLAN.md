# TerraPulse AI Final Implementation Plan

## Phase 1 — Repository audit

**Status: implemented and tested.** The existing NISAR reader, HDF5 validator,
temporal specialists, LangGraph graph, evidence generator, Bengaluru outputs,
React case-study view, and regression tests are present. The audit identified
the generalized processing contract and NISAR-specific job lifecycle as the
main integration gaps.

## Phase 2 — Generalized real NISAR processing API

**Status: in progress.** `POST /api/v1/nisar/process` now accepts two local
observation identifiers, GCOV, requested HH/HV channels, an optional WGS84
AOI, and processing parameters. The service resolves only existing products,
validates HDF5 pairs or compatible GeoTIFF extracts, performs windowed AOI
materialization, and delegates detection to the existing NISAR specialist.

Remaining verification: add focused API tests for real HDF5 metadata, product
compatibility, polarization selection, and AOI extraction.

## Phase 3 — Long-running NISAR jobs

**Status: in progress.** NISAR jobs have owned IDs, bounded worker execution,
progress states, timestamps, failure details, result retrieval, and trace
retrieval. The existing generic upload-job workflow remains unchanged.

Remaining verification: add queued, completed, failed, and ownership tests.

## Phase 4 — LangGraph integration

**Status: implemented foundation; generalized workflow integration in progress.**
The existing typed StateGraph already routes NISAR change and flood specialists
and persists thread state. The new job worker invokes that graph after real
product validation so reports and traces retain the existing graph semantics.

## Phase 5 — Environmental corroboration

**Status: documented limitation.** No contemporaneous ancillary dataset is
claimed as verified. Outputs explicitly identify candidate radar anomalies and
list optical, rainfall, soil-moisture, land-cover, and OSM evidence as
unavailable until downloaded and independently checked.

## Phase 6 — Scientific validation

**Status: implemented for the verified Bengaluru case study.** HH/HV grid
compatibility, mask logic, dB equations, candidate statistics, and
uncertainty limitations are documented in the existing NISAR reports.

## Phase 7 — Evidence-grounded reporting

**Status: implemented foundation.** Existing PDF generation is integrated with
the graph and includes metadata, evidence, trace, and limitations. NISAR
processing results are carried as actual specialist outputs.

## Phase 8 — Frontend integration

**Status: case-study implemented; generalized job UI pending.** The existing
dashboard supports the verified Bengaluru catalog, HH/HV layers, dates,
polygons, previews, statistics, opacity, metadata, and limitations.

## Phase 9 — Large-raster performance

**Status: partially implemented.** The case-study UI uses compact previews and
GeoJSON rather than loading raw HDF5 or full-resolution rasters. The new
processing service uses windowed reads for AOI extraction. COG/tiling remains
an optional deployment optimization.

## Phase 10 — Testing

**Status: baseline verified; focused generalized-workflow tests pending.**
The existing backend suite currently passes 75 tests and the frontend
production build succeeds.

## Phase 11 — Documentation and demo

**Status: in progress.** Existing NISAR reports and status documents are
preserved. Final API, workflow, limitations, and demo guides will be updated
after the generalized job contract is verified.
