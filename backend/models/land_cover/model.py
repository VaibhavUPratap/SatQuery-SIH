"""Adapter for BIFOLD's BigEarthNet v2.0 ConvMixer land-cover model."""

import logging
import os
import time
from typing import Any, Dict

import numpy as np

from backend.config import settings
from backend.models.base import BaseSpecialistModel

logger = logging.getLogger("satquery.land_cover")


# The 19-level nomenclature used by BigEarthNet v2.0 / reBEN.
BIGEARTHNET_LABELS = [
    "Agro-forestry areas",
    "Arable land",
    "Beaches, dunes, sands",
    "Broad-leaved forest",
    "Coastal wetlands",
    "Complex cultivation patterns",
    "Coniferous forest",
    "Inland wetlands",
    "Inland waters",
    "Industrial or commercial units",
    "Land principally occupied by agriculture, with significant areas of natural vegetation",
    "Marine waters",
    "Mixed forest",
    "Moors, heathland and sclerophyllous vegetation",
    "Natural grassland and sparsely vegetated areas",
    "Pastures",
    "Permanent crops",
    "Transitional woodland/shrub",
    "Urban fabric",
]


# The convmixer_768_32-all-v0.2.0 checkpoint was trained on 12 Sentinel-2 bands
# ("all" refers to all 19 label classes, not all 14 S1+S2 bands).
S2_BAND_ORDER = ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12")



class BigEarthNetLandCoverModel(BaseSpecialistModel):
    """Run multi-label land-cover inference using BIFOLD's published checkpoint.

    The checkpoint is not a standard Transformers architecture.  Its custom
    ``BigEarthNetv2_0_ImageClassifier`` class is provided by the official reBEN
    repository, so loading is deferred until the first request.  This keeps API
    startup deterministic and lets deployments choose where its weights live.
    """

    def __init__(self) -> None:
        self.model_id = settings.BIGEARTHNET_MODEL_ID
        self.expected_bands = settings.BIGEARTHNET_EXPECTED_BANDS
        self.threshold = settings.BIGEARTHNET_THRESHOLD
        self._model = None
        self._device = "cpu"

    @property
    def name(self) -> str:
        return "BigEarthNetV2ConvMixer"

    @property
    def version(self) -> str:
        return "0.2.0"

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            import json
            import torch
            from huggingface_hub import hf_hub_download
            from configilm.ConfigILM import ILMConfiguration, ILMType
            from reben_publication.BigEarthNetv2_0_ImageClassifier import BigEarthNetv2_0_ImageClassifier
        except ImportError as exc:
            raise RuntimeError(
                "BigEarthNet inference needs configilm and the official reBEN repository on PYTHONPATH. "
                "Follow Docs/BigEarthNet_Integration.md before calling this endpoint."
            ) from exc

        self._device = "cuda" if torch.cuda.is_available() else "cpu"

        # ── Step 1: read the published config.json ──────────────────────────
        config_path = hf_hub_download(repo_id=self.model_id, filename="config.json")
        with open(config_path) as fh:
            cfg = json.load(fh)

        # The installed configilm==0.4.x ILMConfiguration has a hand-written
        # __init__, so huggingface_hub's _load_dataclass cannot reconstruct it
        # via __dataclass_fields__.  We build it manually instead.
        ilm_config = ILMConfiguration(
            timm_model_name=cfg["timm_model_name"],
            hf_model_name=cfg.get("hf_model_name"),
            image_size=cfg.get("image_size", 120),
            channels=cfg.get("channels", 12),
            classes=cfg.get("classes", 19),
            class_names=cfg.get("class_names"),
            network_type=ILMType(cfg.get("network_type", 0)),
            visual_features_out=cfg.get("visual_features_out", 512),
            fusion_in=cfg.get("fusion_in", 512),
            fusion_out=cfg.get("fusion_out"),
            fusion_hidden=cfg.get("fusion_hidden", 256),
            v_dropout_rate=cfg.get("v_dropout_rate", 0.25),
            t_dropout_rate=cfg.get("t_dropout_rate", 0.25),
            fusion_dropout_rate=cfg.get("fusion_dropout_rate", 0.25),
            drop_rate=cfg.get("drop_rate", cfg.get("drop_path_rate", 0.15)),
            use_pooler_output=cfg.get("use_pooler_output", True),
            max_sequence_length=cfg.get("max_sequence_length", 32),
            load_pretrained_timm_if_available=cfg.get("load_pretrained_timm_if_available", False),
            load_pretrained_hf_if_available=cfg.get("load_pretrained_hf_if_available", True),
        )

        # ── Step 2: build the LightningModule (randomly initialised) ────────
        classifier = BigEarthNetv2_0_ImageClassifier(config=ilm_config)

        # ── Step 3: load published safetensors weights ───────────────────────
        weights_path = hf_hub_download(repo_id=self.model_id, filename="model.safetensors")
        try:
            from safetensors.torch import load_file
            state_dict = load_file(weights_path, device="cpu")
        except ImportError:
            # Fallback: torch.load (works for .bin files too)
            state_dict = torch.load(weights_path, map_location="cpu")

        # The LightningModule wraps a .model sub-module; the safetensors file
        # stores keys prefixed with "model." already.
        missing, unexpected = classifier.load_state_dict(state_dict, strict=False)
        if unexpected:
            logger.warning("Unexpected keys in checkpoint (ignored): %s", unexpected[:5])
        if missing:
            raise RuntimeError(f"BigEarthNet checkpoint is incomplete; missing {len(missing)} model keys.")

        self._model = classifier.to(self._device).eval()
        logger.info("Loaded BigEarthNet ConvMixer checkpoint from %s", self.model_id)
        return self._model

    def _read_multispectral_raster(self, image_path: str) -> Dict[str, np.ndarray]:
        try:
            import rasterio
        except ImportError as exc:
            raise RuntimeError("GeoTIFF inference requires rasterio. Install the BigEarthNet optional dependencies.") from exc

        with rasterio.open(image_path) as source:
            if source.count != self.expected_bands:
                raise ValueError(
                    f"This checkpoint expects {self.expected_bands} Sentinel-2 bands; "
                    f"the uploaded raster has {source.count}. RGB and 3-band images are unsupported."
                )
            image = source.read(out_dtype="float32")
            descriptions = tuple((item or "").upper() for item in source.descriptions)
        if not np.isfinite(image).all():
            raise ValueError("Input raster contains NaN or infinite band values.")
        # Use explicit GeoTIFF band descriptions where available, otherwise the
        # S2-only 12-channel order is the input contract.
        names = descriptions if all(descriptions) else S2_BAND_ORDER
        if set(names) != set(S2_BAND_ORDER):
            raise ValueError(
                f"GeoTIFF band descriptions must be Sentinel-2 B01–B12 (got {set(names)}). "
                "SAR bands (VV/VH) are not used by this checkpoint."
            )
        return dict(zip(names, image))

    def _prepare_tensor(self, bands: Dict[str, np.ndarray]):
        """Match ConfigILM's reBEN stacking, interpolation, and normalization."""
        import torch
        from configilm.extra.BENv2_utils import STANDARD_BANDS, means, stack_and_interpolate, stds

        # STANDARD_BANDS['S2'] covers all 12 Sentinel-2 bands used by this checkpoint.
        ordered_bands = STANDARD_BANDS["S2"]
        tensor = stack_and_interpolate(bands, order=ordered_bands, img_size=120, upsample_mode="nearest").unsqueeze(0)
        mean = torch.tensor([means["120_nearest"][band] for band in ordered_bands], dtype=tensor.dtype)
        std = torch.tensor([stds["120_nearest"][band] for band in ordered_bands], dtype=tensor.dtype)
        return (tensor - mean[None, :, None, None]) / std[None, :, None, None]

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        image_path = inputs.get("image_path")
        if not image_path or not os.path.isfile(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        started = time.time()
        bands = self._read_multispectral_raster(image_path)
        model = self._load_model()
        import torch

        tensor = self._prepare_tensor(bands).to(self._device)
        with torch.no_grad():
            output = model(tensor)
        logits = output.logits if hasattr(output, "logits") else output
        probabilities = torch.sigmoid(logits).detach().cpu().numpy().reshape(-1)
        if probabilities.size != len(BIGEARTHNET_LABELS):
            raise RuntimeError(
                f"Checkpoint returned {probabilities.size} classes; expected {len(BIGEARTHNET_LABELS)}."
            )

        scores = [
            {"label": label, "score": round(float(score), 6)}
            for label, score in zip(BIGEARTHNET_LABELS, probabilities)
        ]
        predictions = [entry for entry in scores if entry["score"] >= self.threshold]
        predictions.sort(key=lambda entry: entry["score"], reverse=True)
        scores.sort(key=lambda entry: entry["score"], reverse=True)
        answer = ", ".join(item["label"] for item in predictions) or "No class exceeded the configured threshold."
        return {
            "answer": answer,
            "predictions": predictions,
            "scores": scores,
            "confidence": round(predictions[0]["score"] if predictions else scores[0]["score"], 6),
            "evidence": {
                "model_source": "Hugging Face Hub",
                "model_id": self.model_id,
                "task": "multi-label land-cover classification",
                "input_bands": self.expected_bands,
                "threshold": self.threshold,
            },
            "execution_trace": {
                "task": "BigEarthNet v2.0 land-cover classification",
                "model": self.name,
                "device": self._device,
                "execution_time_seconds": round(time.time() - started, 4),
            },
        }
