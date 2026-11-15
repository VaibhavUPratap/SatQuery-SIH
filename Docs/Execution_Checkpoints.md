# SatQuery AI — Delivery Schedule and Checkpoints

Last updated: 15 November 2026

## Delivery context

SatQuery AI must demonstrate domain-adapted remote-sensing analysis across
single-image, bi-temporal, and optical/SAR inputs. The delivered backend uses
deterministic local fallbacks so the complete demo remains runnable without a
GPU or network access. Model-training checkpoints are treated separately from
code completion: they must be produced by a reproducible external training run
and never substituted with fabricated benchmark claims.

## Schedule

| Checkpoint | Target | Deliverable | Completion evidence |
| --- | --- | --- | --- |
| C1 | 24 Aug | Phase 5 adaptation workflow | Dataset manifest, Colab-ready notebook, adapter loading contract |
| C2 | 25 Aug | Phase 6 agent orchestration | Classifier, routed `/api/v1/agent`, auditable trace tests |
| C3 | 26 Aug | Phase 7 evidence | Overlay renderer and downloadable PDF report |
| C4 | 27 Aug | Phase 9 evaluation | Accuracy/IoU/F1 runner and evaluation manifest |
| C5 | 28 Aug | Phase 8 dashboard | React UI scaffold for uploads, results, trace, report export |
| C6 | 29–31 Aug | Integration rehearsal | Real RSVQA/BigEarthNet subset, model checkpoint import, API/UI demo |

## Checkpoint rules

- Every code checkpoint must include an automated test or a repeatable command.
- Training checkpoints must record base model, dataset version/split, seed,
  hyperparameters, metric, and artifact checksum in `Docs/training_runs/`.
- Do not mark a model adaptation or benchmark milestone complete until a real
  run produces weights and metrics.
- The offline spectral/backscatter specialists remain the demonstration fallback
  when trained artifacts are unavailable.

## Current status

- C1 — complete: BIFOLD BigEarthNet v2.0 selected; streaming manifest preparation, Colab notebook, LoRA entry point, artifact contract, and a real CUDA RSVQA adapter run are recorded in `Docs/training_runs/`.
- C2 — complete: transparent classifier, LangGraph StateGraph engine, thread-level checkpointing, and unified agent route verified.
- C3 — complete: mask overlay and PDF evidence export implemented.
- C4 — partially complete: metric runner executes against the available 10-row manifest, but a representative registry benchmark and adapted-versus-generic comparison remain required.
- C5 — implemented: React/Leaflet dashboard now includes upload, paired-image, result, trace, report, and evidence-view workflows; production build requires Node/npm dependencies, unavailable in the current environment.
- C6 — partially complete: selected training data, adapter checkpoint, GPU run, and API/UI integration are present; a larger real RSVQA/BigEarthNet rehearsal remains.
- C7 — complete: TerraPulse/NISAR foundation, generalized local-product processing, owned jobs, StateGraph handoff, report integration, frontend controls, and scientific limitations are implemented.
- C8 — complete for the available evidence: the Bengaluru two-date case study is connected end-to-end and optional local corroboration adapters are available. Independent event-level labels and contemporaneous ancillary data remain deployment dependencies and are not fabricated.

## Current overall interpretation

The SatQuery AI/SIH prototype is ready for demonstration. The TerraPulse AI
NISAR expansion has a working foundation but is not complete until real NISAR
observations are acquired, processed, visualized, and independently evaluated.
Synthetic products and curated catalog records remain development fixtures and
must be labelled as such.

## TerraPulse completion update — 15 November 2026

- Phase 1 audit: complete; gaps and preservation constraints are recorded in
  `Docs/FINAL_IMPLEMENTATION_PLAN.md`.
- Phases 2–4: generalized real-product processing, owned NISAR jobs, and
  validated StateGraph handoff implemented and tested.
- Phase 5: local raster/GeoJSON corroboration inspection records source date,
  CRS, dimensions, and AOI coverage; unsupported sources remain `not_verified`.
- Phase 6: existing HH/HV equation, grid, mask, and candidate-screen
  validation remains authoritative.
- Phase 7: NISAR report title, candidate evidence, and limitations are carried
  through the existing PDF generator.
- Phase 9: AOI processing uses windowed reads, tiled outputs, and overviews;
  the case-study browser view continues to load compact previews and vector geometry.
- Phase 10: generalized API, failure-path, external-evidence, LangGraph, report,
  full regression, and frontend build checks pass.

## Interactive temporal backscatter workspace — phase-by-phase release

The existing Bengaluru React/Leaflet page was enhanced without creating a
duplicate processing path. The following phase gate is the authoritative
progress record for the 13-phase UI request:

1. **Audit:** complete; current component, API routes, processed assets, and
   limitations documented in `Docs/TEMPORAL_BACKSCATTER_UI_AUDIT.md`.
2. **Dashboard design:** complete; map-first dark scientific workspace with
   responsive cards and preserved application theme.
3. **Observation controls:** complete; catalog-driven pair metadata and HH/HV
   controls, with no fabricated future observations.
4. **Map workspace:** complete; real compact previews, difference preview,
   candidate GeoJSON, AOI, layer toggles, opacity, coordinates, and fit control.
5. **Temporal comparison:** complete; swipe slider and side-by-side views.
6. **Polarization analysis:** complete; measured HH/HV KPIs and channel
   explanation using only available product channels.
7. **Statistics:** complete; backend serves actual temporal rows and change
   summaries for the UI chart.
8. **Candidate explorer:** complete; filtering, sorting, selection, highlight,
   zoom, region properties, GeoJSON export, and CSV export.
9. **AI interpretation:** complete; evidence and uncertainty are separated from
   possible explanations and unavailable corroboration.
10. **Processing transparency:** complete; asynchronous job status and trace
    are represented without fake completion.
11. **Reports/exports:** complete; existing PDF helper is reused and missing
    difference GeoTIFFs are explicitly reported unavailable.
12. **Performance/responsiveness:** complete; raw HDF5 stays server-side,
    candidate rows are bounded for rendering, and a 390px browser check passed.
13. **Testing:** complete; frontend build passed, Python compilation passed,
    full backend suite passed (80 tests), catalog API smoke passed, and live
    browser interactions passed. A React `useEffect` cleanup warning found
    during smoke testing was fixed in `bf4a39d`.

The two commits for this release are pushed to `origin/main`. Unrelated
`.DS_Store`, generated report-output, and user-provided prompt files remain
outside the release commit.

