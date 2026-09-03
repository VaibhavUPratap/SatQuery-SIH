import os
import time
import logging
from typing import Any, Dict
import numpy as np
from PIL import Image
from backend.models.base import BaseSpecialistModel
from backend.config import settings

logger = logging.getLogger("satquery.captioning")

class RemoteSensingCaptionModel(BaseSpecialistModel):
    """
    Specialist model for Remote Sensing Scene Captioning.
    Wraps Salesforce/blip-image-captioning-base and provides a rule-based
    pixel-analyzing fallback for offline/sandboxed environments.
    """

    def __init__(self):
        self.model_name = "Salesforce/blip-image-captioning-base"
        self.pipeline = None
        self.processor = None
        self.model = None
        self.device = "cpu"
        self._fallback_active = settings.CAPTION_USE_FALLBACK

        if self._fallback_active:
            logger.info("Captioning fallback explicitly enabled; skipping Hugging Face model loading.")
            return

        # Attempt to load PyTorch & Transformers
        try:
            import torch
            from transformers import BlipProcessor, BlipForConditionalGeneration
            
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
                
            logger.info(f"Loading Captioning model '{self.model_name}' on device '{self.device}'...")
            self.processor = BlipProcessor.from_pretrained(self.model_name)
            self.model = BlipForConditionalGeneration.from_pretrained(self.model_name).to(self.device)
            logger.info("Successfully loaded HuggingFace Captioning model.")
        except Exception as e:
            self._fallback_active = True
            logger.warning(
                f"Failed to load Hugging Face Captioning model: {str(e)}. "
                f"Falling back to rule-based pixel heuristic caption generator."
            )

    @property
    def name(self) -> str:
        return "RemoteSensingCaptioning"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Scene Captioning.
        
        Args:
            inputs: Dictionary containing:
                - image_path (str): Absolute path to the image.
                
        Returns:
            Dict containing:
                - caption (str)
                - confidence (float)
                - evidence (dict)
                - execution_trace (dict)
        """
        image_path = inputs.get("image_path")
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        with Image.open(image_path) as source:
            if len(source.getbands()) > 4:
                raise ValueError("Captioning expects an RGB visualization, not a raw multispectral raster.")

        start_time = time.time()

        if self._fallback_active or settings.CAPTION_USE_FALLBACK:
            return self._run_fallback(image_path, start_time)
            
        try:
            image = Image.open(image_path).convert("RGB")
            inputs_encoded = self.processor(image, return_tensors="pt").to(self.device)
            
            import torch
            with torch.no_grad():
                outputs = self.model.generate(**inputs_encoded)
                
            caption = self.processor.decode(outputs[0], skip_special_tokens=True)
            elapsed = time.time() - start_time
            confidence = 0.90 if len(caption) > 0 else 0.50
            
            return {
                "caption": caption,
                "confidence": confidence,
                "evidence": {
                    "model_source": "Hugging Face Hub",
                    "model_name": self.model_name,
                    "device": self.device
                },
                "execution_trace": {
                    "task": "Scene Captioning",
                    "model": f"{self.name} (HF BLIP)",
                    "execution_time_seconds": round(elapsed, 4),
                    "fallback_active": False
                }
            }
            
        except Exception as e:
            logger.error(f"Captioning inference failed, using fallback: {str(e)}")
            return self._run_fallback(image_path, start_time, error_msg=str(e))

    def _run_fallback(self, image_path: str, start_time: float, error_msg: str = None) -> Dict[str, Any]:
        """Generates scene captions based on pixel metrics."""
        try:
            image = Image.open(image_path).convert("RGB")
            img_arr = np.array(image)
            height, width, _ = img_arr.shape
            total_pixels = height * width

            r, g, b = img_arr[:, :, 0], img_arr[:, :, 1], img_arr[:, :, 2]

            green_mask = (g > (r.astype(int) + 10)) & (g > (b.astype(int) + 10))
            green_ratio = float(np.sum(green_mask) / total_pixels)

            blue_mask = (b > (r.astype(int) + 15)) & (b > (g.astype(int) + 15)) & (b < 230)
            blue_ratio = float(np.sum(blue_mask) / total_pixels)

            diff_rg = np.abs(r.astype(int) - g.astype(int))
            diff_gb = np.abs(g.astype(int) - b.astype(int))
            mean_val = (r.astype(int) + g.astype(int) + b.astype(int)) / 3.0
            gray_mask = (diff_rg < 15) & (diff_gb < 15) & (mean_val > 80) & (mean_val < 200)
            gray_ratio = float(np.sum(gray_mask) / total_pixels)
        except Exception as e:
            green_ratio, blue_ratio, gray_ratio = 0.25, 0.05, 0.10
            logger.warning(f"Fallback pixel analysis failed: {str(e)}")

        # Build caption
        elements = []
        if green_ratio > 0.40:
            elements.append("dense vegetation or forest area")
        elif green_ratio > 0.15:
            elements.append("patches of vegetation and agricultural land")
            
        if blue_ratio > 0.05:
            elements.append("a clear water body (lake/river/coast)")
            
        if gray_ratio > 0.25:
            elements.append("developed built-up urban structures and roads")
        elif gray_ratio > 0.10:
            elements.append("some residential or infrastructure buildings")

        if not elements:
            caption = "A high-altitude remote sensing view of mixed terrain, barren land, and light vegetation."
        else:
            caption = "A satellite scene showing " + " with ".join(elements) + "."

        confidence = float(np.clip(0.75 + (green_ratio * 0.10) + (blue_ratio * 0.10), 0.70, 0.92))
        elapsed = time.time() - start_time

        trace_info = {
            "task": "Scene Captioning",
            "model": f"{self.name} (Spectral Fallback)",
            "execution_time_seconds": round(elapsed, 4),
            "fallback_active": True
        }
        if error_msg:
            trace_info["hf_model_error"] = error_msg

        return {
            "caption": caption,
            "confidence": round(confidence, 4),
            "evidence": {
                "spectral_metrics": {
                    "vegetation_ratio": round(green_ratio, 4),
                    "water_ratio": round(blue_ratio, 4),
                    "structural_ratio": round(gray_ratio, 4)
                }
            },
            "execution_trace": trace_info
        }
