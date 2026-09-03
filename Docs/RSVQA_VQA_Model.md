# RSVQA BLIP LoRA VQA Model Pipeline

**Status:** Verified & Stabilized (Phase 2)  
**Architecture:** `Salesforce/blip-vqa-base` + PEFT LoRA Adapter (`checkpoints/rsvqa-blip-lora`)  
**Modality:** Optical Remote Sensing RGB Imagery  

---

## 1. System Architecture & Model Loading

SatQuery AI's Remote Sensing Visual Question Answering (RSVQA) specialist utilizes a parameter-efficient fine-tuned LoRA adapter attached to Salesforce's base BLIP-VQA model:

$$\text{Base: Salesforce/blip-vqa-base} + \text{PEFT Adapter: checkpoints/rsvqa-blip-lora} \longrightarrow \text{RemoteSensingVQAModel}$$

### Verified Loading Protocol
* **Base Model Identifier:** `Salesforce/blip-vqa-base` (via Hugging Face `transformers.BlipForQuestionAnswering`)
* **LoRA Adapter Checkpoint:** `checkpoints/rsvqa-blip-lora` (via `peft.PeftModel`)
  * Target modules: `["query", "value"]`
  * Rank $r=8$, $\alpha=16$, dropout $=0.05$
* **Processor & Tokenizer:** `transformers.BlipProcessor` loaded directly from the adapter checkpoint directory to ensure exact parity with fine-tuning tokenization and image transformations.
* **Device Placement:** Dynamic device selection (`cuda` $\rightarrow$ `mps` $\rightarrow$ `cpu`).
* **Operational Mode:** Explicitly set to evaluation mode (`model.eval()`) with `torch.no_grad()` active during inference.

---

## 2. Input Preprocessing & Image Contract

* **Ingestion:** Handled by `backend/models/vqa/preprocessing.py:load_rgb_image`.
* **Accepted Formats:** 3-channel RGB or 4-channel RGBA in PNG, JPEG, or standard TIFF formats.
* **Multispectral Raster Rejection:** Multi-band rasters with $> 4$ bands (e.g. 12-band Sentinel-2 or 14-band S1+S2 GeoTIFFs) are intercepted with `rasterio` and cleanly rejected with HTTP 422:
  > *"The fine-tuned RSVQA BLIP adapter expects an RGB image, not a raw multispectral raster. Provide an RGB visualization or route multispectral classification to /land-cover."*
* **BLIP Processing Pipeline:**
  * Resizes image to $384 \times 384$ pixels.
  * Normalizes with ImageNet channel statistics:
    * Mean: `[0.48145466, 0.4578275, 0.40821073]`
    * Std: `[0.26862954, 0.26130258, 0.27577711]`

---

## 3. Constrained Deterministic Generation Configuration

To prevent runaway generation, repetitive loops, or random hallucination, decoding is configured with deterministic beam search:

| Parameter | Value | Purpose |
| :--- | :--- | :--- |
| `max_new_tokens` | `16` | RSVQA responses are short words or concise phrases |
| `num_beams` | `3` | Deterministic beam search decoding |
| `repetition_penalty` | `1.15` | Penalizes token repetition and degenerative looping |
| `do_sample` | `False` | Disables stochastic sampling for reproducible predictions |
| `length_penalty` | `1.0` | Balanced length scoring |

---

## 4. Output Sanity & Validation Layer

The destructive heuristic text replacement of earlier prototypes has been replaced with an explicit output sanity validation layer:

1. **Validation Checks:**
   * **Empty / Whitespace Detection:** Rejects empty string outputs (`""`).
   * **Punctuation-Only Detection:** Rejects pure punctuation or non-alphanumeric noise (`"..."`, `"?"`).
   * **Excessive Length Detection:** Flags runaway generation exceeding 120 characters or 20 words for VQA.
   * **Repetitive Loop Detection:** Flags repeated single-token loops (e.g., `"water water water"`).
2. **Honest Fallback String:**
   If an answer fails validation, the system outputs:
   $$\text{"Unable to determine a reliable answer from the provided image."}$$
   The system **never fabricates** synthetic answers or hardcoded percentage overrides.
3. **Spectral Diagnostic Metrics:**
   Auxiliary spectral metrics (vegetation ratio, water ratio, built-up structural ratio) are computed and transparently placed in `evidence.visual_metrics` without mutating the model's textual answer.

---

## 5. Three-Way Benchmark Comparison

Evaluation conducted across representative satellite imagery (`lake_suburb.png`, `forest_scene.png`, `rsvqa_sample_0.png`):

| # | Image | Query | Base BLIP | BLIP + LoRA | Fallback (Spectral) | Expected |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | `lake_suburb.png` | *"Is there a large water body?"* | `"no"` | `"no"` | `"Yes, a water body is detected..."` | `yes` |
| 2 | `lake_suburb.png` | *"Is the area predominantly urban or rural?"* | `"rural"` | `"rural"` | `"Yes, urban features present..."` | `urban / residential` |
| 3 | `forest_scene.png` | *"Is vegetation present?"* | `"no"` | `"no"` | `"Yes, vegetation cover visible..."` | `yes` |
| 4 | `forest_scene.png` | *"What type of land cover is visible?"* | `"grass"` | `"grass"` | `"Primarily dense vegetation..."` | `forest / dense vegetation` |
| 5 | `rsvqa_sample_0.png`| *"Is it a rural or an urban area"* | `"rural"` | `"rural"` | `"No prominent built-up areas..."` | `rural` |
| 6 | `lake_suburb.png` | *"Are roads visible?"* | `"no"` | `"no"` | `"Contains primarily a water body..."` | `yes` |

### Key Diagnostic Takeaway
* The fine-tuned LoRA checkpoint behaves consistently with Base BLIP on general questions because the LoRA adapter was trained on a small 40-sample subset dominated by negative (`"no"`) binary labels.
* The inference pipeline now runs 100% deterministically without crashing, without random generation, and with strict sanity validation.

---

## 6. API Response Specification

### Successful Model-Backed Inference:
```json
{
  "status": "success",
  "query": "Is it a rural or an urban area",
  "answer": "rural",
  "confidence": 0.85,
  "evidence": {
    "model_source": "Salesforce/blip-vqa-base + local RSVQA LoRA adapter",
    "model_name": "Salesforce/blip-vqa-base",
    "adapter_path": "checkpoints/rsvqa-blip-lora",
    "device": "mps",
    "input_representation": "RGB 384x384 normalized (ImageNet stats)",
    "inference_mode": "model",
    "raw_model_answer": "rural",
    "validation_status": "validated",
    "visual_metrics": {
      "vegetation_ratio": 0.0004,
      "water_ratio": 0.0,
      "structural_ratio": 0.0076
    }
  },
  "execution_trace": {
    "task": "Visual Question Answering (VQA)",
    "model": "RemoteSensingVQA (RSVQA BLIP + LoRA adapter)",
    "adapter_loaded": true,
    "inference_mode": "model",
    "fallback_active": false,
    "execution_time_seconds": 0.145
  }
}
```

---

## 7. Automated Test Verification

Run the full regression test suite:

```bash
# Run specialized VQA pipeline regression tests
.venv/bin/pytest -v tests/test_vqa_pipeline.py tests/test_vqa_evidence_guard.py

# Run side-by-side mode comparison
.venv/bin/python tests/compare_vqa_modes.py

# Run end-to-end API integration verification
.venv/bin/python tests/verify_model_vqa.py
```
