# Master Task List — TerraPulse AI

## Current Progress Snapshot

**Overall status: COMPLETE — Phases 0–11 implemented and integrated, with
external-data and independent-label limitations explicitly preserved.**

Last verification:

- Backend regression suite: **80 passed**.
- Frontend production build: **successful** with `npm --prefix frontend run build`.
- FastAPI health smoke test: **200 OK** (`TerraPulse AI API`).
- Scientific limitation retained: NISAR outputs are candidate radar-backscatter anomalies, not independently confirmed environmental events.

Progress is updated phase-by-phase below. A phase is marked complete only when its implementation and focused verification are present in the repository.

### TerraPulse implementation progress

- **Phase 1 — Audit:** complete; see `Docs/FINAL_IMPLEMENTATION_PLAN.md`.
- **Phase 2 — Real NISAR processing API:** complete and covered by focused API tests.
- **Phase 3 — NISAR jobs:** complete with owned status, results, trace, progress, and failure handling.
- **Phase 4 — LangGraph:** complete foundation; validated processing results enter the existing typed graph.
- **Phase 5 — Corroboration:** local raster/GeoJSON source inspection added with source dates, CRS, dimensions, and AOI coverage; unsupplied sources remain unverified.
- **Phase 6 — Scientific validation:** complete for the verified Bengaluru HH/HV case study.
- **Phase 7 — Reports:** NISAR report branding and candidate-evidence limitations integrated.
- **Phase 8 — Frontend:** verified Bengaluru case-study UI exposes job progress, execution trace, and evidence-report download.
- **Phase 9 — Raster performance:** AOI window reads, tiled temporary GeoTIFFs, overviews, and compact browser assets are in use.
- **Phase 10 — Testing:** baseline, failure-path, external-evidence, LangGraph, report, and focused NISAR tests pass.
- **Phase 11 — Documentation:** final API, workflow, limitations, demo, plan, and implementation reports added.

### Interactive Temporal Backscatter View — 13-phase completion

- [x] **Phase 1 — Audit and data contract:** current React view, APIs, assets,
  GeoJSON, statistics, and limitations documented.
- [x] **Phase 2 — Dashboard design:** map-first scientific workspace and
  responsive hierarchy added without replacing the existing application.
- [x] **Phase 3 — Observation controls:** catalog-driven dates, IDs, metadata,
  CRS, resolution, track, frame, orbit, and polarization controls.
- [x] **Phase 4 — Interactive map:** real preview/difference/candidate/AOI
  layers, visibility, opacity, coordinates, fit control, and selection.
- [x] **Phase 5 — Temporal comparison:** swipe and side-by-side modes.
- [x] **Phase 6 — Polarization analysis:** measured HH/HV statistics and
  product-channel explanation.
- [x] **Phase 7 — Statistics/charts:** actual temporal and change-summary data
  served by the case-study endpoint.
- [x] **Phase 8 — Candidate explorer:** table, filtering, sorting, selection,
  highlight, zoom, GeoJSON export, and statistics CSV export.
- [x] **Phase 9 — AI interpretation:** grounded evidence, possible causes,
  required corroboration, and explicit uncertainty.
- [x] **Phase 10 — Processing transparency:** asynchronous status, stage model,
  trace, and failure messaging.
- [x] **Phase 11 — Reports/exports:** existing PDF integration retained;
  unavailable GeoTIFF exports are not fabricated.
- [x] **Phase 12 — Performance/responsiveness:** raw products remain server-side,
  compact assets are used, and mobile layout was smoke-tested.
- [x] **Phase 13 — Testing:** 80 backend tests, frontend build, API smoke,
  browser interaction checks, and React cleanup fix completed.

## Completed Milestones

- [x] **Phase 0: Project Structure Setup**
  - [x] Create folder layout (`backend/agent`, `backend/models`, `backend/validation`, etc.).
  - [x] Define `requirements.txt` and base project configuration (`config.py`).
  - [x] Set up virtual environment and install backend packages.
- [x] **Phase 1: Foundation & Single-Image VQA**
  - [x] Define specialist model base class (`base.py`).
  - [x] Create input validator (`validator.py`).
  - [x] Implement `RemoteSensingVQAModel` with spectral/pixel-analysis fallback.
  - [x] Build FastAPI routes (`vqa.py`, `main.py`).
  - [x] Test green (vegetation) and blue (water) mock images.
- [x] **Phase 2: Single-Image Scene Captioning & Text-Guided Grounding**
  - [x] Implement `RemoteSensingCaptionModel` (BLIP + offline fallback).
  - [x] Implement `RemoteSensingGroundingModel` (bounding-box output + fallback).
  - [x] Expose `/api/v1/caption` and `/api/v1/grounding` routes.
  - [x] Add verification tests for scene descriptions and coordinates.
- [x] **Phase 3: Bi-temporal Change Detection & Change VQA**
  - [x] Build registration compatibility checks (`backend/preprocessing/registration.py`).
  - [x] Implement `ChangeDetectionModel` (pixel-difference map and thresholding).
  - [x] Implement `ChangeVQAModel` (dual-image difference VQA).
  - [x] Expose `/api/v1/change` with change-map overlay and explanation.
  - [x] Verify change logic using mock temporal pairs.

## Upcoming Milestones

### [x] Phase 4: Cross-Modal Optical + SAR Analysis

- [x] Implement optical-SAR coregistration validator.
- [x] Implement `OpticalSARFusionModel` for joint water/built-up extraction.
- [x] Expose `/api/v1/optical-sar` route.
- [x] Verify optical+SAR combination outputs.

### [x] Phase 5: Remote-Sensing VLM Model Adaptation Layer

- [x] Select BIFOLD BigEarthNet v2.0 VQA as the adaptation dataset and document image-patch integration.
- [x] Set up Google Colab notebook for downstream fine-tuning.
- [x] Fine-tune a model (for example, RemoteCLIP or LLaVA) on BigEarthNet or RSVQA.
- [x] Export and load adapted checkpoints in specialist models.
- [x] Run benchmarks comparing the adapted model with a generic VLM.
  - Measured evidence: Adapted model achieves 40.0%–50.0% overall domain accuracy and 66.7%–81.5% binary question accuracy on the strictly held-out RSVQA-LR chips (samples 40–49, 0% train overlap). Recorded in `Docs/Benchmark_Results.md` and `experiments/evaluation_summary.json`.

### [x] Phase 6: LangGraph Agent Orchestration

- [x] Create query task classifier router (`backend/agent/task_classifier.py`).
- [x] Define and implement an auditable deterministic flow: Validator → Router → specialist execution → evidence fusion.
- [x] Replace the deterministic flow with a persisted LangGraph `StateGraph` supporting node transitions, conditional edges, and thread-level state persistence (`backend/agent/graph.py`, `backend/agent/state.py`).
- [x] Expose `/api/v1/agent` returning answer, confidence, overlays, and execution trace.
- [x] Verify single-image, bi-temporal, and optical-SAR agent routing with StateGraph workflow.

### [x] Phase 7: Evidence Fusion & Reports

- [x] Implement mask-overlay renderer (`backend/evidence/generator.py`).
- [x] Build PDF report export (`backend/evidence/report.py`).

### [x] Phase 8: React Web Dashboard

- [x] Develop upload UI.
- [x] Integrate Leaflet image and mask-overlay viewer.
- [x] Add interactive execution-trace dashboard.
- [x] Integrate report-download action.

### [x] Phase 9: Benchmark Evaluation

- [x] Write automated metric runners (IoU, accuracy, F1).
- [x] Benchmark the registry against held-out evaluation subsets.
  - Measured evidence: 
    - RSVQA Strictly Held-Out Accuracy: 40.0%–50.0% (66.7% on binary presence/rural-urban questions)
    - Grounding Mean IoU: 0.3767 (33.3% precision @ 0.5 IoU on discrete multi-object contours)
    - Bi-Temporal Change Detection: 0.6589 Pixel IoU, 0.6628 F1-score, 99.2% Precision (ultra-low false alarm rate)
    - Optical-SAR Multi-Modal Alignment Score: 0.9200 (100% Water consistency, 99.7% Built-up consistency)
    - All 17 regression tests verified (`tests/test_end_to_end_validation.py`). Detailed in `Docs/Benchmark_Results.md`.
