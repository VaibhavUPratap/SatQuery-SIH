import os
import time
import logging
from typing import Any, Dict
import numpy as np
from PIL import Image
from backend.models.base import BaseSpecialistModel
from backend.config import settings
from backend.models.vqa.preprocessing import load_rgb_image

logger = logging.getLogger("satquery.vqa")

class RemoteSensingVQAModel(BaseSpecialistModel):
    """
    Specialist model for Remote Sensing Visual Question Answering (RSVQA).
    Wraps the local RSVQA LoRA adapter on Salesforce/blip-vqa-base and provides
    a clearly identified pixel-analysis fallback when model inference is unavailable.
    """

    def __init__(self):
        self.model_name = settings.VQA_MODEL_NAME
        self.use_fallback = settings.VQA_USE_FALLBACK
        self.processor = None
        self.model = None
        self.device = "cpu"
        self._fallback_active = self.use_fallback
        self._load_error = None

        if self.use_fallback:
            logger.info("VQA fallback explicitly enabled; skipping Hugging Face model loading.")
        else:
            logger.info("VQA model will load lazily on the first model-backed request.")

    def _load_model(self) -> None:
        """Load the base BLIP checkpoint and its fine-tuned local LoRA adapter."""
        if self.model is not None:
            return
        if self._load_error:
            raise RuntimeError(self._load_error)
        try:
            import torch
            from transformers import BlipProcessor, BlipForQuestionAnswering
            
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
                
            adapter_path = settings.VQA_ADAPTER_PATH
            if not adapter_path or not os.path.isdir(adapter_path):
                raise RuntimeError("VQA_ADAPTER_PATH must point to the supplied RSVQA LoRA adapter directory.")
            logger.info("Loading BLIP base model '%s' and RSVQA LoRA adapter '%s' on %s.", self.model_name, adapter_path, self.device)
            load_options = {"local_files_only": settings.VQA_LOCAL_FILES_ONLY}
            # Prefer the processor saved alongside the adapter so inference matches training.
            self.processor = BlipProcessor.from_pretrained(adapter_path, **load_options)
            base_model = BlipForQuestionAnswering.from_pretrained(self.model_name, **load_options).to(self.device)
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(base_model, adapter_path).to(self.device).eval()
            logger.info("Loaded the fine-tuned RSVQA BLIP LoRA model.")
        except Exception as e:
            self._load_error = str(e)
            self._fallback_active = True
            logger.warning(
                "Failed to load the fine-tuned RSVQA BLIP LoRA model: %s. Falling back to the spectral analyzer.", e
            )
            raise RuntimeError(self._load_error) from e

    @property
    def name(self) -> str:
        return "RemoteSensingVQA"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute VQA.
        
        Args:
            inputs: Dictionary containing:
                - image_path (str): Absolute path to the image.
                - question (str): Query text.
                
        Returns:
            Dict containing:
                - answer (str)
                - confidence (float)
                - evidence (dict)
                - execution_trace (dict)
        """
        image_path = inputs.get("image_path")
        question = inputs.get("question", "").strip()
        
        if not image_path or not os.path.exists(image_path):
            raise FileNotFoundError(f"Image not found at path: {image_path}")

        start_time = time.time()

        # If fallback is active or explicitly requested via config
        if self._fallback_active or self.use_fallback:
            return self._run_fallback(image_path, question, start_time, error_msg=self._load_error)
            
        try:
            self._load_model()
            image = load_rgb_image(image_path)
            inputs_encoded = self.processor(images=image, text=question, return_tensors="pt").to(self.device)
            
            import torch
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs_encoded,
                    max_new_tokens=settings.VQA_MAX_NEW_TOKENS,
                    num_beams=settings.VQA_NUM_BEAMS,
                    do_sample=False,
                )
                
            answer = self.processor.decode(outputs[0], skip_special_tokens=True)
            elapsed = time.time() - start_time
            
            # Simple heuristic confidence score for standard model output
            confidence = 0.88 if len(answer) > 0 else 0.50
            
            return {
                "answer": answer,
                "confidence": confidence,
                "evidence": {
                    "model_source": "local fine-tuned LoRA adapter + cached Hugging Face base model",
                    "model_name": self.model_name,
                    "adapter_path": settings.VQA_ADAPTER_PATH,
                    "device": self.device,
                    "input_representation": "RGB; saved BLIP processor resize/normalization",
                    "inference_mode": "model",
                },
                "execution_trace": {
                    "task": "Visual Question Answering (VQA)",
                    "model": f"{self.name} (RSVQA BLIP + LoRA adapter)",
                    "adapter_loaded": True,
                    "execution_time_seconds": round(elapsed, 4),
                    "fallback_active": False,
                    "inference_mode": "model",
                }
            }
            
        except ValueError:
            # An incompatible raster must be reported to the caller, not
            # presented as a fallback VQA answer.
            raise
        except Exception as e:
            logger.error(f"Inference failed, using fallback: {str(e)}")
            return self._run_fallback(image_path, question, start_time, error_msg=str(e))

    def _run_fallback(self, image_path: str, question: str, start_time: float, error_msg: str = None) -> Dict[str, Any]:
        """
        Calculates pixel color distribution metrics from the input image
        to answer common remote sensing VQA query keywords.
        """
        try:
            image = load_rgb_image(image_path)
            img_arr = np.array(image)
            height, width, channels = img_arr.shape
            total_pixels = height * width

            # Heuristics: extract RGB channels
            r, g, b = img_arr[:, :, 0], img_arr[:, :, 1], img_arr[:, :, 2]

            # Use relative colour dominance so compressed or darker imagery is
            # not rejected solely because its channel values are low.
            green_mask = (g > (r.astype(int) * 1.05 + 4)) & (g > (b.astype(int) * 1.05 + 4))
            green_ratio = float(np.sum(green_mask) / total_pixels)

            blue_mask = (b > (r.astype(int) * 1.10 + 6)) & (b > (g.astype(int) * 1.05 + 6)) & (b < 245)
            blue_ratio = float(np.sum(blue_mask) / total_pixels)

            # Gray / structural (built-up) index: Low variance between channels, moderate brightness
            diff_rg = np.abs(r.astype(int) - g.astype(int))
            diff_gb = np.abs(g.astype(int) - b.astype(int))
            mean_val = (r.astype(int) + g.astype(int) + b.astype(int)) / 3.0
            
            # Built-up areas have gray colors, high texture
            gray_mask = (diff_rg < 15) & (diff_gb < 15) & (mean_val > 80) & (mean_val < 200)
            gray_ratio = float(np.sum(gray_mask) / total_pixels)

            # Small isolated pixels are noise. Connected components provide a
            # useful approximate object count for explicit counting questions.
            object_count = 0
            try:
                import cv2
                structure_mask = (gray_mask.astype(np.uint8) * 255)
                components, _, _, _ = cv2.connectedComponentsWithStats(structure_mask, 8)
                object_count = max(0, sum(1 for area in _[:, cv2.CC_STAT_AREA][1:] if area >= max(8, total_pixels * 0.002)))
            except Exception:
                object_count = max(0, int(gray_ratio * 20))
        except Exception as e:
            green_ratio, blue_ratio, gray_ratio, object_count = 0.25, 0.05, 0.10, 0
            total_pixels = 0
            logger.warning(f"Fallback pixel analysis failed: {str(e)}")

        q_lower = question.lower()
        
        # Formulate answer based on query keywords and pixel distributions
        if any(kw in q_lower for kw in ["land cover", "visible", "what is this", "describe", "scene"]):
            land_types = []
            if green_ratio > 0.20:
                land_types.append(f"dense vegetation/forest covering {green_ratio*100:.1f}% of the area")
            if blue_ratio > 0.03:
                land_types.append(f"a water body covering {blue_ratio*100:.1f}% of the area")
            if gray_ratio > 0.15:
                land_types.append(f"built-up urban structure/roads covering {gray_ratio*100:.1f}% of the area")
                
            if land_types:
                answer = f"The satellite image contains primarily " + ", ".join(land_types) + "."
            else:
                answer = "The image represents barren land or mixed surface features with sparse vegetation."
                
        elif any(kw in q_lower for kw in ["water", "river", "lake", "ocean", "sea"]):
            if blue_ratio > 0.02:
                answer = f"Yes, a water body is detected in the image, covering approximately {blue_ratio*100:.1f}% of the spatial extent."
            else:
                answer = "No significant water bodies were detected in this satellite scene."
                
        elif any(kw in q_lower for kw in ["vegetation", "forest", "green", "agriculture", "crop"]):
            if green_ratio > 0.05:
                answer = f"Yes, vegetation cover is visible, covering approximately {green_ratio*100:.1f}% of the area."
            else:
                answer = "The image shows very sparse or no vegetation cover."
                
        elif any(kw in q_lower for kw in ["built-up", "urban", "building", "city", "road", "infrastructure"]):
            if gray_ratio > 0.05:
                answer = f"Yes, urban or built-up structural features are present, spanning roughly {gray_ratio*100:.1f}% of the image."
            else:
                answer = "No prominent built-up areas or city structures are visible in the image."
                
        elif any(kw in q_lower for kw in ["count", "how many"]):
            answer = f"Approximately {max(1, object_count)} distinct built-up regions are detected; this is an image-analysis estimate, not a cadastral count."

        elif any(kw in q_lower for kw in ["dominant", "main", "majority"]):
            ratios = {"vegetation": green_ratio, "water": blue_ratio, "built-up structure": gray_ratio}
            label, ratio = max(ratios.items(), key=lambda item: item[1])
            answer = f"The dominant detected class is {label}, covering approximately {ratio * 100:.1f}% of the image."
            
        else:
            answer = f"Remote-sensing spectral assessment indicates {green_ratio*100:.1f}% vegetation index, {blue_ratio*100:.1f}% water index, and {gray_ratio*100:.1f}% built-up structural index."

        confidence = float(np.clip(0.70 + (green_ratio * 0.15) + (blue_ratio * 0.10), 0.65, 0.95))
        elapsed = time.time() - start_time

        trace_info = {
            "task": "Visual Question Answering (VQA)",
            "model": f"{self.name} (Spectral Fallback)",
            "execution_time_seconds": round(elapsed, 4),
            "fallback_active": True,
            "inference_mode": "fallback",
        }
        if error_msg:
            trace_info["hf_model_error"] = error_msg

        return {
            "answer": answer,
            "confidence": round(confidence, 4),
            "evidence": {
                "spectral_metrics": {
                    "vegetation_ratio": round(green_ratio, 4),
                    "water_ratio": round(blue_ratio, 4),
                    "structural_ratio": round(gray_ratio, 4),
                    "estimated_structure_count": object_count,
                },
                "image_resolution": f"{width}x{height} pixels",
                "total_analyzed_pixels": total_pixels,
                "inference_mode": "fallback",
            },
            "execution_trace": trace_info
        }
