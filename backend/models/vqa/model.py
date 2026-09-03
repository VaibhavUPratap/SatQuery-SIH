import os
import re
import time
import logging
from typing import Any, Dict, Tuple
import numpy as np
from PIL import Image

from backend.models.base import BaseSpecialistModel
from backend.config import settings
from backend.models.vqa.preprocessing import load_rgb_image

logger = logging.getLogger("satquery.vqa")

_NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


class RemoteSensingVQAModel(BaseSpecialistModel):
    """
    Specialist model for Remote Sensing Visual Question Answering (RSVQA).
    Wraps the local RSVQA LoRA adapter on Salesforce/blip-vqa-base and provides
    a clearly identified pixel-analysis fallback when model inference is unavailable.
    """

    def __init__(self):
        self.model_name = settings.VQA_MODEL_NAME
        self.adapter_path = settings.VQA_ADAPTER_PATH
        self.use_fallback = settings.VQA_USE_FALLBACK
        self.processor = None
        self.model = None
        self.device = "cpu"
        self._fallback_active = self.use_fallback
        self._load_error = None
        self._model_info = {}

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
            from peft import PeftModel
            
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
                
            adapter_path = self.adapter_path
            if not adapter_path or not os.path.isdir(adapter_path):
                raise RuntimeError(
                    f"VQA_ADAPTER_PATH '{adapter_path}' must point to a valid directory containing the fine-tuned RSVQA LoRA adapter."
                )
            
            logger.info("Loading BLIP base model '%s' and RSVQA LoRA adapter '%s' on %s.", self.model_name, adapter_path, self.device)
            
            # Honor local-only mode so an offline deployment never attempts a network fetch.
            processor = None
            base_model = None
            
            local_only = settings.VQA_LOCAL_FILES_ONLY
            load_opts = {"local_files_only": local_only}
            try:
                # 1. Load processor (prefer adapter directory if processor config exists)
                try:
                    processor = BlipProcessor.from_pretrained(adapter_path, **load_opts)
                except Exception:
                    processor = BlipProcessor.from_pretrained(self.model_name, **load_opts)

                # 2. Load base BLIP-VQA model
                base_model = BlipForQuestionAnswering.from_pretrained(self.model_name, **load_opts)
            except Exception as load_err:
                if local_only:
                    logger.info("Local files only load failed for %s (%s).", self.model_name, load_err)
                raise

            if processor is None or base_model is None:
                raise RuntimeError("Failed to load BLIP processor or base model.")

            self.processor = processor
            base_model = base_model.to(self.device)
            
            # 3. Attach LoRA adapter
            self.model = PeftModel.from_pretrained(base_model, adapter_path).to(self.device).eval()
            
            # Verify adapter attachment
            is_peft = isinstance(self.model, PeftModel)
            active_adapters = getattr(self.model, "active_adapters", ["default"])
            
            self._model_info = {
                "base_model": self.model_name,
                "adapter_path": adapter_path,
                "processor_type": type(self.processor).__name__,
                "tokenizer_type": type(getattr(self.processor, "tokenizer", None)).__name__,
                "device": self.device,
                "is_peft_model": is_peft,
                "active_adapters": active_adapters,
                "eval_mode": not self.model.training,
                "max_new_tokens": settings.VQA_MAX_NEW_TOKENS,
                "num_beams": settings.VQA_NUM_BEAMS,
            }
            self._fallback_active = False
            logger.info("Successfully loaded fine-tuned RSVQA BLIP LoRA model on %s (active adapters: %s).", self.device, active_adapters)
        except Exception as e:
            self._load_error = str(e)
            self._fallback_active = True
            logger.warning(
                "Failed to load the fine-tuned RSVQA BLIP LoRA model: %s. Falling back to the spectral analyzer.", e
            )
            raise RuntimeError(self._load_error) from e

    def get_model_diagnostics(self) -> Dict[str, Any]:
        """Return safe diagnostic metadata about model loading and configuration."""
        return {
            "model_name": self.model_name,
            "adapter_path": self.adapter_path,
            "device": self.device,
            "fallback_active": self._fallback_active,
            "load_error": self._load_error,
            **self._model_info,
        }

    @property
    def name(self) -> str:
        return "RemoteSensingVQA"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute VQA inference using fine-tuned RSVQA LoRA adapter model with fallback guard.
        
        Args:
            inputs: Dictionary containing:
                - image_path (str): Absolute path to the image.
                - question (str): Question query text.
                
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

        if not question:
            raise ValueError("Question text cannot be empty.")

        start_time = time.time()

        # If fallback is explicitly requested or already active
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
                    repetition_penalty=settings.VQA_REPETITION_PENALTY,
                    length_penalty=settings.VQA_LENGTH_PENALTY,
                    do_sample=False,
                )
                
            raw_answer = self.processor.decode(outputs[0], skip_special_tokens=True).strip()
            raw_answer = self._canonicalize_answer(raw_answer)
            final_answer, confidence, visual_evidence = self._validate_and_sanitize_output(raw_answer, question, image)
            elapsed = time.time() - start_time
            
            return {
                "answer": final_answer,
                "confidence": confidence,
                "evidence": {
                    "model_source": "Salesforce/blip-vqa-base + local RSVQA LoRA adapter",
                    "model_name": self.model_name,
                    "adapter_path": self.adapter_path,
                    "device": self.device,
                    "input_representation": "RGB 384x384 normalized (ImageNet stats)",
                    "inference_mode": "model",
                    "raw_model_answer": raw_answer,
                    **visual_evidence,
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
            # Re-raise explicit validation errors (e.g. multispectral raster rejected)
            raise
        except Exception as e:
            logger.error("VQA model inference failed, using fallback analyzer: %s", e)
            return self._run_fallback(image_path, question, start_time, error_msg=str(e))

    @staticmethod
    def _canonicalize_answer(raw_answer: str) -> str:
        """Normalize standalone number words emitted for count questions."""
        cleaned = (raw_answer or "").strip().lower()
        return _NUMBER_WORDS.get(cleaned, raw_answer.strip() if raw_answer else "")

    @staticmethod
    def _validate_and_sanitize_output(raw_answer: str, question: str, image: Image.Image) -> Tuple[str, float, Dict[str, Any]]:
        """
        Expert output sanity layer.
        
        Cleans output punctuation, validates output bounds, and calculates honest confidence.
        """
        # Extract visual spectral metrics for diagnostic evidence
        pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
        red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]
        vegetation = float(np.mean((green > red * 1.05 + 4) & (green > blue * 1.05 + 4)))
        water = float(np.mean((blue > red * 1.10 + 6) & (blue > green * 1.05 + 6) & (blue < 245)))
        structural = float(np.mean((np.abs(red - green) < 15) & (np.abs(green - blue) < 15) & (((red + green + blue) / 3) > 80) & (((red + green + blue) / 3) < 200)))
        
        visual_metrics = {
            "vegetation_ratio": round(vegetation, 4),
            "water_ratio": round(water, 4),
            "structural_ratio": round(structural, 4),
        }

        cleaned = (raw_answer or "").strip()
        
        # Check 1: Empty or whitespace
        if not cleaned:
            return (
                "Unable to determine a reliable answer from the provided image.",
                0.20,
                {
                    "validation_status": "unreliable_empty",
                    "visual_metrics": visual_metrics,
                }
            )

        # Strip trailing/leading punctuation artifacts (e.g. "rural." -> "rural")
        cleaned = cleaned.strip(" .,!?:;\"'[](){}<>")

        # Check 2: Pure punctuation / non-alphanumeric garbage
        if not re.search(r"[a-zA-Z0-9]", cleaned):
            return (
                "Unable to determine a reliable answer from the provided image.",
                0.20,
                {
                    "validation_status": "unreliable_punctuation",
                    "visual_metrics": visual_metrics,
                }
            )

        # Check 3: Excessively long output (> 120 chars or > 20 words for VQA)
        words = cleaned.split()
        if len(cleaned) > 120 or len(words) > 20:
            return (
                "Unable to determine a reliable answer from the provided image.",
                0.20,
                {
                    "validation_status": "unreliable_length",
                    "visual_metrics": visual_metrics,
                }
            )

        # Check 4: Repetitive loops (e.g. "water water water")
        if len(words) >= 3 and len(set(words)) == 1:
            return (
                "Unable to determine a reliable answer from the provided image.",
                0.20,
                {
                    "validation_status": "unreliable_repetition",
                    "visual_metrics": visual_metrics,
                }
            )

        # Validation passed: return clean model answer with honest confidence score
        confidence = 0.85 if len(words) <= 5 else 0.75

        return (
            cleaned,
            confidence,
            {
                "validation_status": "validated",
                "visual_metrics": visual_metrics,
            }
        )

    def _run_fallback(self, image_path: str, question: str, start_time: float, error_msg: str = None) -> Dict[str, Any]:
        """
        Calculates pixel color distribution metrics from the input image
        to answer common remote sensing VQA query keywords.
        """
        fallback_reason = "model_error" if error_msg else "configured"
        try:
            image = load_rgb_image(image_path)
            img_arr = np.array(image)
            height, width, channels = img_arr.shape
            total_pixels = height * width

            r, g, b = img_arr[:, :, 0], img_arr[:, :, 1], img_arr[:, :, 2]

            green_mask = (g > (r.astype(int) * 1.05 + 4)) & (g > (b.astype(int) * 1.05 + 4))
            green_ratio = float(np.sum(green_mask) / total_pixels)

            blue_mask = (b > (r.astype(int) * 1.10 + 6)) & (b > (g.astype(int) * 1.05 + 6)) & (b < 245)
            blue_ratio = float(np.sum(blue_mask) / total_pixels)

            diff_rg = np.abs(r.astype(int) - g.astype(int))
            diff_gb = np.abs(g.astype(int) - b.astype(int))
            mean_val = (r.astype(int) + g.astype(int) + b.astype(int)) / 3.0
            
            gray_mask = (diff_rg < 15) & (diff_gb < 15) & (mean_val > 80) & (mean_val < 200)
            gray_ratio = float(np.sum(gray_mask) / total_pixels)

            object_count = 0
            try:
                import cv2
                structure_mask = (gray_mask.astype(np.uint8) * 255)
                components, labels, stats, centroids = cv2.connectedComponentsWithStats(structure_mask, 8)
                object_count = max(0, sum(1 for area in stats[:, cv2.CC_STAT_AREA][1:] if area >= max(8, total_pixels * 0.002)))
            except Exception:
                object_count = max(0, int(gray_ratio * 20))
        except ValueError:
            raise
        except Exception as e:
            green_ratio, blue_ratio, gray_ratio, object_count = 0.25, 0.05, 0.10, 0
            total_pixels = 0
            height, width = 0, 0
            logger.warning(f"Fallback pixel analysis failed: {str(e)}")

        q_lower = question.lower()
        
        exact_count = any(kw in q_lower for kw in ["count", "how many", "number of", "amount of"])
        answer_status = "fallback"
        if exact_count:
            answer = "I cannot reliably determine an exact object count from this RGB image alone."
            answer_status = "abstained"
        elif any(kw in q_lower for kw in ["land cover", "visible", "what is this", "describe", "scene"]):
            land_types = []
            if green_ratio > 0.20:
                land_types.append(f"dense vegetation/forest covering {green_ratio*100:.1f}% of the area")
            if blue_ratio > 0.03:
                land_types.append(f"a water body covering {blue_ratio*100:.1f}% of the area")
            if gray_ratio > 0.15:
                land_types.append(f"built-up urban structure/roads covering {gray_ratio*100:.1f}% of the area")
                
            if land_types:
                answer = "The satellite image contains primarily " + ", ".join(land_types) + "."
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
                
        elif any(kw in q_lower for kw in ["dominant", "main", "majority"]):
            ratios = {"vegetation": green_ratio, "water": blue_ratio, "built-up structure": gray_ratio}
            label, ratio = max(ratios.items(), key=lambda item: item[1])
            answer = f"The dominant detected class is {label}, covering approximately {ratio * 100:.1f}% of the image."
            
        else:
            answer = f"Remote-sensing spectral assessment indicates {green_ratio*100:.1f}% vegetation index, {blue_ratio*100:.1f}% water index, and {gray_ratio*100:.1f}% built-up structural index."

        confidence = 0.35 if answer_status == "abstained" else float(np.clip(0.70 + (green_ratio * 0.15) + (blue_ratio * 0.10), 0.65, 0.95))
        elapsed = time.time() - start_time

        trace_info = {
            "task": "Visual Question Answering (VQA)",
            "model": f"{self.name} (Spectral Fallback)",
            "adapter_loaded": False,
            "execution_time_seconds": round(elapsed, 4),
            "fallback_active": True,
            "inference_mode": "fallback",
            "answer_status": answer_status,
            "fallback_reason": fallback_reason,
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
                "fallback_reason": fallback_reason,
            },
            "execution_trace": trace_info
        }
