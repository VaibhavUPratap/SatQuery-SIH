# SatQuery AI — Delivery Schedule and Checkpoints

Last updated: 14 November 2026

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
- C7 — in progress: TerraPulse/NISAR foundation added, including HDF5 reading, metadata and temporal-pair validation, CMR/ASF-style search, radar change detection, flood analysis, preview generation, and initial frontend/API integration.
- C8 — pending: acquire and verify real NISAR products for one study area, run a two-date end-to-end case study, connect the workflow to the main agent and report UI, and evaluate against independent reference data.

## Current overall interpretation

The SatQuery AI/SIH prototype is ready for demonstration. The TerraPulse AI
NISAR expansion has a working foundation but is not complete until real NISAR
observations are acquired, processed, visualized, and independently evaluated.
Synthetic products and curated catalog records remain development fixtures and
must be labelled as such.

