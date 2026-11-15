# SIH 2026 — SatQuery AI: Problem Statement & Proposed Approach Context

## Verified NISAR case-study integration

The application includes a read-only Bengaluru NISAR case-study view backed by
the compact Phase 2–4 outputs. The API catalog reports the two verified
observation dates, EPSG:32643 grid metadata, HH/HV candidate-area summaries,
and the documented absence of verified external land-cover data. Candidate
GeoJSON and preview PNG assets are served from the processed case-study
directory; raw HDF5 products and large measurement rasters remain local and
ignored by Git.

The frontend view supports polarization selection, AOI/candidate-region map
display, candidate area summaries, and temporal dB/potential-change previews.
It is intentionally observational and does not claim a confirmed environmental
event.

Phase 7 scientific validation additionally verified the generated dB, ratio,
and percentage equations against the original linear measurements, confirmed
the mask/grid metadata, and corrected the map-display CRS boundary by
transforming projected candidate geometry to WGS84 only for Leaflet rendering.
The original projected GeoJSON remains preserved as the scientific asset.

## 1. Purpose of this document

This document is a complete context package for an AI assistant, developer, researcher, or team member working on **Smart India Hackathon 2026 Problem Statement SIH26167**.

The goal is to provide enough information to understand:

- what the official problem statement asks for;
- what is mandatory versus optional;
- what our proposed solution is;
- how the proposed architecture maps to the requirements;
- what models/tools/components need to exist;
- what must be demonstrated in the final prototype;
- what technical risks must be handled;
- what should NOT be done;
- and how the project should be approached for implementation.

This document is based primarily on the official SIH26167 problem statement supplied by the team and the SIH 2026 internal idea-submission template.

---

# 2. Official Problem Statement

## Problem Statement ID

**SIH26167**

## Title

**SatQuery AI — An Interactive Vision-Language Assistant for Multimodal Remote Sensing Image Analysis through Text Queries**

## Organization

**Indian Space Research Organisation (ISRO)**

## Department

**Department of Space / Indian Space Research Organisation**

## Category

**Software**

## Theme

**Space Technology**

---

# 3. Official Problem Context

Remote-sensing imagery is widely used for:

- agricultural monitoring;
- disaster management;
- urban planning;
- forest monitoring;
- water-resource assessment;
- infrastructure mapping;
- environmental analysis.

However, many existing remote-sensing AI systems are isolated systems designed for one predefined task, such as:

- land-cover classification;
- object detection;
- visual question answering;
- change detection.

These systems often require users to understand:

- satellite-data characteristics;
- GIS workflows;
- model selection;
- task-specific parameters.

This creates a usability problem for non-expert users.

The problem statement proposes a natural-language interface where users can ask questions about remote-sensing imagery and the system automatically determines what analysis is required.

---

# 4. Why a Single Image Is Not Always Enough

Many operational remote-sensing questions cannot reliably be answered from one optical image.

Useful information can be distributed across:

1. images acquired at different times;
2. images acquired by different sensors;
3. optical/multispectral imagery;
4. synthetic aperture radar (SAR) imagery.

### Optical / multispectral imagery

Provides:

- spectral information;
- contextual information;
- information useful for land-cover interpretation.

### SAR imagery

Provides complementary structural information and supports:

- day-and-night acquisition;
- observation through cloud cover.

### Multitemporal imagery

Two observations of the same geographic area at different times are required for:

- change detection;
- change description;
- change-based visual question answering.

### Optical + SAR

Co-registered optical and SAR images can provide more complete information than either modality alone.

---

# 5. Core Problem

A generic LLM or VLM cannot automatically be assumed to understand remote-sensing imagery reliably.

The system therefore needs:

- remote-sensing fine-tuning or domain adaptation;
- specialist remote-sensing models/tools;
- an agentic controller that chooses the appropriate tools;
- evidence-grounded outputs.

The official problem statement explicitly states that a generic LLM/VLM without remote-sensing adaptation is insufficient.

---

# 6. Core Idea of SatQuery AI

SatQuery AI is a **software-based agentic vision-language assistant** for analysing:

- single remote-sensing images;
- cross-modal optical + SAR image pairs;
- bi-temporal image pairs.

The user provides:

1. one or more supported images;
2. a natural-language query.

The system then:

1. validates the inputs;
2. understands the query;
3. determines the requested task;
4. selects appropriate specialist models/tools;
5. executes the workflow;
6. combines textual and spatial outputs;
7. estimates confidence;
8. returns evidence-grounded results;
9. exposes an auditable execution summary.

The system should behave more like an **AI remote-sensing analysis platform** than a generic chatbot.

---

# 7. Supported Input Types

## 7.1 Single image

One:

- optical/multispectral image, or
- SAR image.

Possible tasks:

- visual question answering;
- captioning / scene description;
- text-guided region grounding.

## 7.2 Cross-modal pair

Two co-registered images of the same geographic area:

- optical/multispectral;
- SAR.

Purpose:

- joint information extraction;
- cross-modal analysis.

## 7.3 Bi-temporal pair

Two spatially corresponding images of the same geographic area acquired at different times.

Purpose:

- change detection;
- change description;
- change-based VQA.

## 7.4 Supported formats

Primary supported formats:

- GeoTIFF;
- TIFF.

PNG/JPEG may be accepted only for prescribed public benchmark datasets where permitted.

---

# 8. Mandatory Functional Requirements

The solution MUST demonstrate all of the following.

## Requirement 1 — Remote-Sensing Adaptation

At least one visual or vision-language component must be:

- fine-tuned, or
- otherwise adapted

using:

- BigEarthNet.txt, or
- other open-source remote-sensing training data.

A generic VLM alone is NOT sufficient.

---

## Requirement 2 — Single-Image VQA

Visual question answering is mandatory.

Example:

> "Describe the land-cover and major objects visible in this image."

The system must analyze the image and answer the natural-language question.

---

## Requirement 3 — One Additional Single-Image Task

In addition to VQA, implement at least one of:

### Option A — Captioning / Scene Description

Example:

> "Describe this scene."

### Option B — Text-Guided Region Grounding

Example:

> "Highlight the water body referred to in the query."

Our preferred approach is to implement BOTH captioning and grounding if feasible, because this provides stronger functionality and a better demonstration.

---

## Requirement 4 — Multitemporal Change Analysis

The system MUST support a bi-temporal pair.

It must perform either:

- change description, or
- change-based visual question answering.

A spatial change map may additionally be generated where reference masks are available.

Example:

> "What changed between these two dates, and where did the change occur?"

or:

> "Has the built-up area increased, decreased, or remained unchanged?"

---

## Requirement 5 — Cross-Modal Optical + SAR Analysis

The system MUST analyze a co-registered optical/multispectral + SAR pair.

The system must extract complementary information from both modalities.

Example:

> "Use the optical and SAR images together to identify built-up and water-covered regions."

---

## Requirement 6 — Agentic Orchestration

The system MUST automatically:

1. interpret the query;
2. classify the requested task;
3. inspect input configuration;
4. validate image compatibility;
5. select one or more specialist models/tools;
6. configure permitted task parameters;
7. execute the selected workflow;
8. combine outputs;
9. estimate confidence;
10. return visual evidence;
11. provide an auditable execution summary.

The internal chain-of-thought is NOT required.

What matters is the observable execution trace.

---

# 9. Representative User Queries

The system should be capable of handling queries such as:

### Single image

> Describe the land-cover and major objects visible in this image.

### Grounding

> Highlight the water body referred to in the query.

### Change analysis

> What changed between these two dates, and where did the change occur?

### Optical + SAR

> Use the optical and SAR images together to identify built-up and water-covered regions.

### Built-up change

> Has the built-up area increased, decreased, or remained unchanged?

The agent should infer the appropriate workflow instead of requiring the user to manually select a model.

---

# 10. Proposed System Architecture

## High-level architecture

```text
                         USER
                           |
                           v
              +-------------------------+
              |     IMAGE + QUERY       |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |    INPUT VALIDATOR      |
              |-------------------------|
              | Format                  |
              | Modality                |
              | Metadata                |
              | Number of images        |
              | Pair compatibility      |
              | Registration checks     |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |     SATQUERY AGENT      |
              |-------------------------|
              | Query understanding     |
              | Task classification     |
              | Workflow planning       |
              | Tool/model selection    |
              +------------+------------+
                           |
          +----------------+----------------+
          |                |                |
          v                v                v
 +----------------+ +----------------+ +------------------+
 | SINGLE IMAGE   | | TEMPORAL       | | CROSS-MODAL      |
 | TOOLS          | | TOOLS          | | TOOLS            |
 |----------------| |----------------| |------------------|
 | VQA            | | Registration   | | Optical encoder  |
 | Captioning     | | Change detect. | | SAR encoder      |
 | Grounding      | | Change VQA     | | Fusion model     |
 +-------+--------+ +-------+--------+ +--------+---------+
         |                  |                   |
         +------------------+-------------------+
                            |
                            v
              +-------------------------+
              |     EVIDENCE FUSION     |
              |-------------------------|
              | Text answer             |
              | Spatial evidence        |
              | Bounding boxes/maps     |
              | Confidence              |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |    EXECUTION TRACE      |
              |-------------------------|
              | Selected task           |
              | Models/tools used       |
              | Key parameters          |
              | Outputs                 |
              +------------+------------+
                           |
                           v
              +-------------------------+
              |     FINAL RESPONSE      |
              |-------------------------|
              | Answer                  |
              | Visual evidence         |
              | Confidence              |
              | Downloadable report     |
              +-------------------------+
```

---

# 11. Remote-Sensing Adaptation Layer

This layer is critical because the official PS explicitly rejects a generic LLM/VLM-only solution.

Conceptually:

```text
BigEarthNet / Open Remote-Sensing Data
                  |
                  v
      Remote-Sensing Adaptation
                  |
                  v
    Remote-Sensing-Aware VLM/Vision
                  |
                  v
          Specialist Tools
                  |
                  v
             SatQuery Agent
```

The team must select at least one concrete model/component that can be adapted using remote-sensing data.

This is a real implementation requirement, not just a PPT statement.

---

# 12. Specialist Tool Registry

The SatQuery Agent should have a predefined registry of tools/models.

Example conceptual registry:

```python
TOOLS = {
    "vqa": RemoteSensingVQAModel(),
    "caption": RemoteSensingCaptioningModel(),
    "grounding": RemoteSensingGroundingModel(),
    "change_detection": ChangeDetectionModel(),
    "change_vqa": ChangeVQAModel(),
    "optical_sar": OpticalSARFusionModel()
}
```

The exact models are still a technical selection decision.

The architecture should remain model-agnostic so models can be replaced without redesigning the entire application.

---

# 13. Agent Routing Logic

The agent should infer the workflow from both:

- the natural-language query;
- the uploaded image configuration.

Example:

```text
Query:
"What is visible in this image?"

Input:
1 optical image

        |
        v

Task = VQA

        |
        v

Select VQA model
```

---

Another example:

```text
Query:
"Describe this scene."

Input:
1 optical image

        |
        v

Task = Captioning

        |
        v

Select Captioning model
```

---

Another:

```text
Query:
"Where is the water body?"

Input:
1 optical image

        |
        v

Task = Grounding

        |
        v

Select Grounding model
```

---

Another:

```text
Query:
"What changed between these two dates?"

Input:
2 spatially corresponding images

        |
        v

Task = Temporal Change Analysis

        |
        +--> Change Detection
        |
        +--> Change VQA
        |
        v

Generate change map + answer
```

---

Another:

```text
Query:
"Use optical and SAR together to identify built-up regions."

Input:
1 optical image
1 SAR image

        |
        v

Task = Cross-Modal Analysis

        |
        +--> Optical encoder
        |
        +--> SAR encoder
        |
        +--> Fusion model
        |
        v

Joint interpretation
```

---

# 14. Input Validation

Before model execution, SatQuery should check:

- file format;
- image count;
- modality;
- metadata;
- geospatial compatibility;
- spatial correspondence;
- co-registration where required;
- whether the selected workflow is compatible with the input.

Example:

```text
INPUT VALIDATION
----------------
Optical TIFF       ✓
SAR TIFF           ✓
Same geographic area ✓
Co-registration    ✓
Compatible query   ✓

Proceeding to cross-modal workflow...
```

Invalid inputs should be rejected with a useful explanation instead of producing a hallucinated answer.

---

# 15. Evidence-Grounded Response

The final answer should not only be text.

It should include, where applicable:

- visual evidence;
- highlighted regions;
- bounding boxes;
- change maps;
- modality-specific evidence;
- confidence;
- execution trace.

Example:

```text
RESULT
------

Built-up area increased.

Estimated change:
+18.7%

Primary change region:
Northern section of the image.

Confidence:
91.2%
```

Then display the relevant change map.

---

# 16. Execution Trace

This is a major feature because the official PS says the observable execution trace will be evaluated.

Example UI:

```text
SATQUERY EXECUTION TRACE
------------------------

✓ Input validation
  - Optical TIFF
  - SAR TIFF
  - Co-registration verified

✓ Query classification
  - Task: Cross-modal analysis

✓ Model selection
  - Optical encoder
  - SAR encoder
  - Fusion model

✓ Inference completed

✓ Evidence generated

✓ Confidence estimated

Final confidence: 93.7%
```

The trace should expose:

- selected task;
- selected models/tools;
- permitted parameters;
- important outputs.

Do NOT expose private/internal chain-of-thought.

---

# 17. Evaluation Strategy

The official problem statement specifies evaluation using prescribed public benchmark test subsets and an ISRO/SAC evaluation dataset.

Public benchmark resources mentioned:

- VRSBench;
- RSVQA;
- CDVQA.

The final evaluation is expected to include an ISRO/SAC dataset containing:

- pre-georeferenced;
- co-registered;
- Cartosat-2S optical;
- RISAT SAR;
- task-specific reference answers;
- labels;
- bounding boxes;
- masks where applicable.

Evaluation annotations will not be disclosed to participating teams.

Therefore, the system should be designed to generalize to unseen data instead of hard-coding solutions for public samples.

---

# 18. Evaluation Dashboard — Proposed

A useful internal evaluation dashboard could show:

```text
MODEL EVALUATION
----------------

Remote-Sensing VQA
Accuracy: XX

Captioning
Metric: XX

Grounding
IoU: XX

Change VQA
Accuracy: XX

Change Detection
F1 / IoU: XX

Optical-SAR Analysis
Metric: XX
```

The exact metrics should follow the prescribed benchmark evaluation methodology rather than being invented arbitrarily.

---

# 19. Proposed Technology Stack

## Frontend

Recommended:

- React
- Tailwind CSS

Geospatial visualization:

- Leaflet
- OpenLayers if required

## Backend

Recommended:

- Python
- FastAPI

## Machine Learning

Recommended ecosystem:

- PyTorch
- Hugging Face Transformers
- OpenCV
- NumPy

## Geospatial processing

Recommended:

- Rasterio
- GDAL
- GeoPandas where vector processing is needed

## Model architecture

Use an abstraction layer so specialist models can be replaced independently.

---

# 20. Proposed Backend Structure

Conceptually:

```text
backend/
│
├── agent/
│   ├── query_router
│   ├── task_classifier
│   ├── planner
│   └── tool_registry
│
├── validation/
│   ├── format_validator
│   ├── metadata_validator
│   └── compatibility_checker
│
├── models/
│   ├── vqa/
│   ├── captioning/
│   ├── grounding/
│   ├── change_detection/
│   ├── change_vqa/
│   └── optical_sar/
│
├── preprocessing/
│   ├── optical/
│   ├── sar/
│   ├── registration/
│   └── normalization/
│
├── evidence/
│   ├── overlays/
│   ├── maps/
│   ├── confidence/
│   └── report/
│
└── api/
    └── endpoints/
```

This is an architectural suggestion, not an official SIH requirement.

---

# 21. Suggested User Workflow

## Step 1 — Upload

User uploads:

- one image;
- or optical + SAR;
- or a bi-temporal pair.

## Step 2 — Ask

User enters natural-language query.

## Step 3 — Validate

System checks image compatibility.

## Step 4 — Understand

SatQuery Agent classifies the task.

## Step 5 — Route

Agent selects specialist model/tool(s).

## Step 6 — Process

Models execute the required workflow.

## Step 7 — Fuse

Outputs are combined.

## Step 8 — Explain

System generates:

- answer;
- visual evidence;
- confidence;
- execution trace.

## Step 9 — Export

User can download a report.

---

# 22. Example End-to-End Scenario

## Input

Two optical satellite images of the same region:

- Date A
- Date B

## Query

> "Has the built-up area increased, and where did the change occur?"

## Agent reasoning at the task level

The observable workflow should be:

```text
Input:
2 corresponding optical images

Query:
Built-up change

Detected task:
Bi-temporal change analysis

Selected tools:
1. Image registration / preprocessing
2. Change detection
3. Built-up classification
4. Change VQA
5. Evidence generation
```

## Output

```text
BUILT-UP CHANGE DETECTED

Change:
Increased

Estimated increase:
XX%

Main affected region:
Northern / eastern section

Confidence:
XX%

Evidence:
- Change map
- Built-up region overlay
- Before/after comparison

Execution:
- Change Detection Model
- Built-up Analysis Model
- Change VQA Model
```

---

# 23. Example Optical + SAR Scenario

## Input

- Sentinel-2 optical image
- Sentinel-1 SAR image

## Query

> "Use the optical and SAR images together to identify built-up and water-covered regions."

## Workflow

```text
Input validation
      |
      v
Optical + SAR confirmed
      |
      v
Cross-modal analysis
      |
      +------------------+
      |                  |
      v                  v
 Optical encoder      SAR encoder
      |                  |
      +--------+---------+
               |
               v
          Fusion model
               |
               v
       Region extraction
               |
               v
    Visual evidence + answer
```

---

# 24. Example Grounding Scenario

## Input

One remote-sensing image.

## Query

> "Highlight the water body."

## Workflow

```text
Image
  |
  v
Query classification
  |
  v
Grounding
  |
  v
Water-region localization
  |
  v
Bounding box / mask
  |
  v
Highlighted image
```

---

# 25. What Makes the Proposed Solution Different

The main differentiator should NOT be:

> "We use an LLM."

That is too generic.

The core innovation is:

## Agentic, query-driven remote-sensing analysis

Instead of one generic model doing everything:

```text
User query
    |
    v
SatQuery Agent
    |
    +--> VQA
    +--> Captioning
    +--> Grounding
    +--> Change Detection
    +--> Change VQA
    +--> Optical-SAR Fusion
    |
    v
Evidence-grounded response
```

The system dynamically selects the appropriate specialist workflow.

Additional differentiating capabilities:

- multimodal optical + SAR reasoning;
- temporal reasoning;
- visual evidence;
- confidence estimation;
- auditable execution trace;
- downloadable reports;
- remote-sensing-adapted model component.

---

# 26. What NOT to Build

## Do NOT make this:

```text
Image
  ↓
Generic Gemini/GPT vision API
  ↓
Answer
```

This is insufficient because the official PS explicitly requires remote-sensing adaptation.

---

## Do NOT make this:

```text
Four buttons:

VQA
Change Detection
SAR
Caption
```

with the user manually choosing everything.

That does not demonstrate the intended agentic orchestration strongly enough.

The system should automatically determine the workflow from:

- query;
- number of images;
- modalities;
- metadata.

---

## Do NOT focus only on UI

A beautiful dashboard without working remote-sensing models will be weak.

The project should prioritize:

1. working specialist models;
2. remote-sensing adaptation;
3. multimodal/temporal pipelines;
4. agentic routing;
5. evaluation;
6. UI.

---

# 27. Main Technical Risks

## Risk 1 — Remote-sensing VLM adaptation is difficult

Mitigation:

- start with an existing open-source remote-sensing-capable model;
- perform targeted fine-tuning/adaptation;
- demonstrate measurable adaptation/evaluation.

## Risk 2 — Large models may require significant compute

Mitigation:

- use efficient models where possible;
- use quantization;
- use GPU/cloud inference during development;
- cache embeddings/results for demonstrations.

## Risk 3 — Optical and SAR data are different modalities

Mitigation:

- use modality-specific encoders;
- perform controlled preprocessing;
- use a dedicated fusion approach.

## Risk 4 — Temporal images may not be perfectly aligned

Mitigation:

- use registration/preprocessing;
- validate spatial correspondence;
- reject incompatible pairs.

## Risk 5 — Public benchmark success may not generalize

Mitigation:

- keep the pipeline model-agnostic;
- test on varied regions;
- avoid overfitting to a single benchmark.

## Risk 6 — Agent may select an inappropriate workflow

Mitigation:

- use a constrained tool registry;
- define explicit routing rules;
- validate available modalities before execution;
- expose the execution trace.

---

# 28. Implementation Priority

The team should NOT build everything simultaneously.

Recommended order:

```text
PHASE 1
Remote-sensing VQA
        |
        v
PHASE 2
Captioning OR Grounding
        |
        v
PHASE 3
Bi-temporal Change Analysis
        |
        v
PHASE 4
Optical + SAR Analysis
        |
        v
PHASE 5
Agentic Controller
        |
        v
PHASE 6
Evidence + Confidence + Execution Trace
        |
        v
PHASE 7
Frontend Integration
        |
        v
PHASE 8
Benchmark Evaluation
        |
        v
PHASE 9
End-to-End Demonstration
```

---

# 29. Minimum Viable Prototype

The MVP must prioritize compliance.

Minimum end-to-end demonstration:

### Demo 1 — Single-image VQA

```text
Image + question
      ↓
VQA
      ↓
Answer
```

### Demo 2 — Single-image grounding/captioning

```text
Image + query
      ↓
Grounding or captioning
      ↓
Visual/text output
```

### Demo 3 — Bi-temporal change

```text
Image A + Image B + question
      ↓
Change workflow
      ↓
Change map + answer
```

### Demo 4 — Optical + SAR

```text
Optical + SAR + question
      ↓
Fusion workflow
      ↓
Joint analysis
```

### Demo 5 — Agentic routing

```text
Natural-language query
      ↓
Agent
      ↓
Automatically selected tool(s)
      ↓
Execution trace
      ↓
Evidence-grounded response
```

---

# 30. Strong Final Demonstration

The ideal final demo should make the judge see the following sequence:

```text
USER
Upload satellite data
        |
        v
Ask natural-language question
        |
        v
SATQUERY
"What type of analysis is required?"
        |
        v
VALIDATE INPUT
        |
        v
SELECT SPECIALIST MODEL(S)
        |
        v
EXECUTE
        |
        v
FUSE EVIDENCE
        |
        v
ANSWER + MAP + CONFIDENCE
        |
        v
EXECUTION TRACE
```

The key message should be:

> **The user does not need to understand remote-sensing workflows. SatQuery converts a natural-language question into the appropriate remote-sensing analysis workflow and returns an evidence-grounded result.**

---

# 31. Six-Slide SIH Internal PPT Context

The uploaded DSU SIH 2026 template allows a maximum of six slides including the title slide.

Required structure:

1. Title slide
2. Proposed Solution
3. Technical Approach
4. Feasibility & Viability
5. Impact & Benefits
6. Research & References

The template instructs teams to:

- avoid paragraphs;
- use points, diagrams, infographics and pictures;
- keep explanations precise and easy to understand;
- present a unique and novel idea;
- use the provided template;
- submit the final file as PDF.

The presentation time is 5 minutes, followed by a viva.

For SatQuery AI, the PPT should therefore be visual and architecture-heavy rather than text-heavy.

---

# 32. Recommended PPT Story

## Slide 1 — Title

**SatQuery AI**

Interactive Vision-Language Assistant for Multimodal Remote-Sensing Image Analysis

Include:

- SIH26167
- ISRO
- Space Technology
- team details

---

## Slide 2 — Proposed Solution

Show:

```text
Natural Language Query
          +
Satellite Images
          ↓
     SatQuery AI
          ↓
Evidence-grounded answer
```

Show the five core capabilities:

- VQA;
- Captioning/Grounding;
- Change Analysis;
- Optical + SAR;
- Agentic Orchestration.

---

## Slide 3 — Technical Approach

Show the complete architecture:

```text
Input
 ↓
Validation
 ↓
SatQuery Agent
 ↓
Specialist Tool Registry
 ↓
VQA / Grounding / Change / Optical-SAR
 ↓
Evidence Fusion
 ↓
Confidence + Execution Trace
 ↓
Result
```

---

# 33. Implementation Status — November 2026

## 33.1 Completed SatQuery AI / SIH prototype

The original SIH26167 prototype is implemented as a working demonstration
platform. Completed capabilities include:

- FastAPI backend and React/Vite dashboard.
- Upload validation, raster checks, metadata checks, size limits, and temporary-file cleanup.
- Single-image VQA with a real BLIP + PEFT LoRA remote-sensing adapter and deterministic fallback.
- Scene captioning and text-guided grounding.
- Bi-temporal change detection and change-focused VQA.
- Optical + SAR fusion for water and built-up evidence.
- BigEarthNet land-cover classification integration.
- Deterministic task classification plus persisted LangGraph orchestration.
- Evidence overlays, confidence values, execution traces, and PDF export.
- Session/job isolation, path sanitization, and bounded concurrency controls.
- Automated evaluation scripts and regression tests.

The documented benchmark baseline is 60% exact accuracy on the repaired
10-image RSVQA holdout, 0.6589 change-detection IoU / 0.6627 F1 on three
repository-provided pairs, 0.3767 grounding mIoU, and 0.9200 optical-SAR
alignment. Change metrics now use the emitted model masks; reference-mask
provenance remains unverified, so they are not independent scientific
validation. These are prototype measurements, not production guarantees.

## 33.2 TerraPulse AI / NISAR expansion in progress

The project is now being extended toward the NASA Space Apps Challenge
“Dancing with the SARs” direction under the TerraPulse AI concept. Initial
NISAR-specific implementation exists for:

- HDF5 NISAR metadata inspection and official hierarchy checks.
- Polarization discovery and calibrated backscatter extraction.
- Product validation, quality checks, and temporal-pair validation.
- NASA CMR/ASF-style search integration points.
- NISAR preview generation.
- L-band dB backscatter change detection with speckle filtering.
- Flood inundation and water-dynamics analysis using HH/HV evidence.
- Dedicated NISAR API routes for search, validation, preview, and controlled demo synthesis.
- Initial TerraPulse-oriented frontend views and agent/tool integration points.

These modules establish the processing foundation, but synthetic products,
curated catalog records, or offline fallbacks must not be presented as proof of
real NISAR observations.

## 33.3 Remaining NISAR completion criteria

Before claiming full compliance with the NISAR-focused challenge direction, the
team must:

1. Acquire real NISAR products for a selected study area.
2. Verify product identifiers, acquisition dates, coverage, polarization, CRS,
   and product maturity from authoritative metadata.
3. Process at least two real observations through the temporal pipeline.
4. Connect search, selection, validation, analysis, visualization, explanation,
   and reporting into one user workflow.
5. Add real-product fixtures and end-to-end NISAR tests.
6. Evaluate against independent reference data and report uncertainty.
7. Clearly label real, synthetic, curated, and fallback outputs.

Until these criteria are met, the correct project status is: **SatQuery SIH
prototype ready for demonstration; TerraPulse/NISAR integration underway**.

---

## Slide 4 — Feasibility & Viability

Show:

- open-source datasets;
- open-source models;
- Python/PyTorch ecosystem;
- cloud/GPU inference;
- modular architecture.

Show risks and mitigations.

---

## Slide 5 — Impact & Benefits

Potential applications:

- disaster response;
- agriculture;
- urban planning;
- water monitoring;
- forest monitoring;
- infrastructure monitoring;
- environmental monitoring;
- defense/security-adjacent geospatial analysis where appropriate.

Main benefit:

> Natural-language access to complex remote-sensing analysis without requiring the user to manually select GIS/AI workflows.

---

## Slide 6 — Research & References

Include:

- official SIH26167 problem statement;
- BigEarthNet;
- VRSBench;
- RSVQA;
- CDVQA;
- relevant remote-sensing VLM research;
- change detection research;
- optical-SAR fusion research.

Only include references that the team actually uses.

---

# 33. Team Division — Six People

Suggested division for a 6-person AI/ML + Data Science team:

## Member 1 — Remote-Sensing VLM / VQA

Responsibilities:

- VQA model;
- remote-sensing adaptation;
- benchmark evaluation.

## Member 2 — Change Detection

Responsibilities:

- temporal preprocessing;
- registration;
- change detection;
- change maps;
- change VQA.

## Member 3 — Optical + SAR

Responsibilities:

- optical preprocessing;
- SAR preprocessing;
- modality fusion;
- cross-modal analysis.

## Member 4 — Grounding / Vision

Responsibilities:

- grounding;
- region localization;
- bounding boxes/masks;
- visual evidence.

## Member 5 — Agent / Backend

Responsibilities:

- SatQuery Agent;
- query routing;
- tool registry;
- workflow orchestration;
- API/backend.

## Member 6 — Frontend / Integration

Responsibilities:

- React interface;
- satellite visualization;
- overlays;
- execution trace;
- confidence display;
- report export.

---

# 34. Core Design Principle

The entire project should follow this principle:

> **Do not build one model that tries to do everything. Build an intelligent controller that knows which specialist model/tool should be used for the user's question.**

Architecture:

```text
                SATQUERY AGENT
                     |
       +-------------+-------------+
       |             |             |
      VQA       CHANGE MODEL    FUSION
       |             |             |
   Grounding      Change VQA    Optical+SAR
       |             |             |
       +-------------+-------------+
                     |
              Evidence Fusion
                     |
             Final Explanation
```

---

# 35. Final Compliance Checklist

Before considering the project compliant, verify:

- [ ] Single-image VQA works.
- [ ] Captioning or grounding works.
- [ ] Bi-temporal change analysis works.
- [ ] Optical + SAR paired analysis works.
- [ ] At least one vision/VLM component is remote-sensing adapted.
- [ ] GeoTIFF/TIFF support works.
- [ ] Input validation works.
- [ ] Agent automatically classifies the task.
- [ ] Agent automatically selects tools.
- [ ] Agent can sequence multiple tools when required.
- [ ] Outputs are combined.
- [ ] Visual evidence is returned.
- [ ] Confidence is returned.
- [ ] Execution summary is visible.
- [ ] Model/tool names are visible in the execution trace.
- [ ] Key permitted parameters are visible.
- [ ] Downloadable report is available.
- [ ] Public benchmark evaluation is performed.
- [ ] The pipeline is designed for unseen ISRO/SAC data.
- [ ] No generic VLM is being presented as the entire solution.

---

# 36. Current Status of the Proposed Approach

The proposed architecture is **strongly aligned with the official SIH26167 requirements**.

However, architecture alone is not enough.

The highest-priority implementation decisions still to be finalized are:

1. exact remote-sensing VLM/vision model;
2. exact adaptation/fine-tuning method;
3. exact VQA model;
4. exact captioning/grounding model;
5. exact change detection model;
6. exact change-VQA model;
7. exact optical-SAR fusion strategy;
8. compute requirements;
9. benchmark evaluation pipeline;
10. end-to-end agent implementation.

These should be researched and validated before committing them to the final PPT.

## 36.1 Implemented Prototype Status (31 August 2026)

The backend prototype now exposes the following FastAPI routes:

- `POST /api/v1/vqa` — single-image VQA;
- `POST /api/v1/caption` — scene captioning;
- `POST /api/v1/grounding` — text-guided region grounding;
- `POST /api/v1/change` — bi-temporal change analysis;
- `POST /api/v1/optical-sar` — optical and SAR fusion;
- `POST /api/v1/agent` — agent-driven routing and evidence fusion;
- `POST /api/v1/land-cover` — BigEarthNet v2.0 multi-label land-cover classification.

### Verification result

The supplied `rsvqa-blip-lora` checkpoint has been verified as a real LoRA
adapter on `Salesforce/blip-vqa-base`, trained on the local RSVQA subset. A
model-backed smoke test loaded the cached BLIP base and adapter on CPU, returned
the non-empty answer `rural` for an RSVQA sample, and reported
`inference_mode: model` with `fallback_active: false`. The same test verified
automatic VQA routing through `/api/v1/agent`. The fallback VQA checks also
pass, as do captioning, grounding, change detection, optical-SAR fusion, and
the tested agent HTTP routes. The standard pytest suite passed (3 tests), and
the evaluation-metric test passed when run through pytest.

### Current limitations and honest demo claims

- Model-backed VQA currently requires the cached `Salesforce/blip-vqa-base`
  base weights because the supplied artifact is a LoRA adapter rather than a
  complete standalone BLIP checkpoint. `VQA_LOCAL_FILES_ONLY=true` prevents
  an accidental network request; deployments without the cached base model use
  the visibly identified fallback.
- BigEarthNet route validation is implemented and rejects non-14-band inputs;
  an actual prediction has not yet been validated with a real co-registered
  Sentinel-1/Sentinel-2 GeoTIFF and the official reBEN custom model code.
- `tests/verify_agent.py` currently fails its history assertion when native
  LangGraph checkpointing is active: `get_state_history()` reads the fallback
  in-memory history rather than the native checkpointer state. The agent API
  requests in that script still returned HTTP 200.
- `tests/verify_evaluation.py` is pytest-compatible but cannot be invoked
  directly because it does not add the project root to `sys.path`.

Therefore, describe VQA as a **prototype-validated model-backed RSVQA LoRA
workflow**, with a separately identified fallback. Captioning, grounding,
change, and optical-SAR remain prototype-validated fallback workflows. Do not
yet claim end-to-end BigEarthNet inference validation or production-grade VQA
benchmark performance.

---

# 37. One-Sentence Project Definition

**SatQuery AI is an agentic remote-sensing vision-language system that converts natural-language questions and satellite imagery into automatically selected, multimodal or temporal analysis workflows, producing evidence-grounded answers, visual results, confidence estimates, and an auditable execution trace.**

---

# 38. Important Constraint

Do not claim that a component is implemented, fine-tuned, benchmarked, or validated until the team has actually completed and tested it.

Separate:

- **official SIH requirements**
- **proposed architecture**
- **planned implementation**
- **implemented features**
- **measured evaluation results**

This distinction is especially important during the SIH viva.

---

# 39. Verified NISAR Bengaluru Case Study Status

The project now contains a verified four-phase NISAR L2 GCOV case study for
Bengaluru:

- **Phase 1:** Two real NISAR L2 GCOV HDF5 products were verified, including
  HHHH/HVHV paths, metadata, EPSG:32643 frequency-A grid, and quality masks.
- **Phase 2:** HH/HV linear gamma-zero measurements and source masks were
  extracted to a reproducible 10 m Bengaluru AOI window (`3920 × 4382`).
- **Phase 3:** Full-AOI temporal statistics, gamma-zero dB conversions,
  difference/ratio products, and robust spatially coherent candidate masks were
  generated for 2026-10-29 versus 2026-11-10.
- **Phase 4:** Candidate masks were polygonized in EPSG:32643, areas and WGS84
  centroids were calculated, and geospatial interpretation maps were produced.

The case-study reports are:

- `Docs/NISAR_HDF5_VALIDATION_REPORT.md`
- `Docs/NISAR_BENGALURU_EXTRACTION_REPORT.md`
- `Docs/NISAR_TEMPORAL_CHANGE_ANALYSIS_REPORT.md`
- `Docs/NISAR_ENVIRONMENTAL_INTERPRETATION_REPORT.md`

The environmental interpretation remains deliberately limited: no
Bengaluru-specific external land-cover, optical, rainfall, soil-moisture,
water-body, or OpenStreetMap layer was downloaded and verified. Candidate
regions are measured radar anomalies and hypotheses, not confirmed
deforestation, flooding, agriculture, or construction events. Large HDF5 and
derived GeoTIFF files remain local and are excluded from Git; scripts,
reports, metadata, summaries, GeoJSON, and visual outputs are versioned.
