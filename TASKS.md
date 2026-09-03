# Master Task List — SatQuery AI

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
