import os
import time
import logging
from typing import Any, Dict
import cv2
import numpy as np
from PIL import Image
from backend.models.base import BaseSpecialistModel

logger = logging.getLogger("satquery.change_vqa")


class ChangeVQAModel(BaseSpecialistModel):
    """
    Specialist model for Change-based Visual Question Answering.
    Takes a bi-temporal image pair and a natural-language question about
    changes, then produces a grounded textual answer.
    """

    @property
    def name(self) -> str:
        return "ChangeVQA"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Change VQA.

        Args:
            inputs: Dictionary containing:
                - image_path_a (str): Path to image at time T1.
                - image_path_b (str): Path to image at time T2.
                - question (str): Natural language question about change.

        Returns:
            Dict with answer, confidence, evidence, execution_trace.
        """
        image_path_a = inputs.get("image_path_a")
        image_path_b = inputs.get("image_path_b")
        question = inputs.get("question", "").strip()

        if not image_path_a or not os.path.exists(image_path_a):
            raise FileNotFoundError(f"Image A not found: {image_path_a}")
        if not image_path_b or not os.path.exists(image_path_b):
            raise FileNotFoundError(f"Image B not found: {image_path_b}")

        start_time = time.time()

        # Load and align
        img_a = cv2.imread(image_path_a)
        img_b = cv2.imread(image_path_b)

        if img_a is None or img_b is None:
            raise ValueError("Could not read one or both images.")

        if img_a.shape[:2] != img_b.shape[:2]:
            raise ValueError("Change VQA requires equal image dimensions; register or resample inputs before inference.")

        h, w = img_a.shape[:2]
        total_pixels = h * w

        # Extract per-channel statistics for both images
        b_a, g_a, r_a = cv2.split(img_a)
        b_b, g_b, r_b = cv2.split(img_b)

        # Vegetation metrics (green channel dominance)
        veg_mask_a = (g_a > (r_a.astype(int) + 10)) & (g_a > (b_a.astype(int) + 10))
        veg_mask_b = (g_b > (r_b.astype(int) + 10)) & (g_b > (b_b.astype(int) + 10))
        veg_ratio_a = float(np.sum(veg_mask_a) / total_pixels)
        veg_ratio_b = float(np.sum(veg_mask_b) / total_pixels)
        veg_change = veg_ratio_b - veg_ratio_a

        # Water metrics (blue channel dominance)
        water_mask_a = (b_a > (g_a.astype(int) + 15)) & (b_a > (r_a.astype(int) + 15)) & (b_a < 230)
        water_mask_b = (b_b > (g_b.astype(int) + 15)) & (b_b > (r_b.astype(int) + 15)) & (b_b < 230)
        water_ratio_a = float(np.sum(water_mask_a) / total_pixels)
        water_ratio_b = float(np.sum(water_mask_b) / total_pixels)
        water_change = water_ratio_b - water_ratio_a

        # Built-up metrics (gray structural)
        diff_rg_a = np.abs(r_a.astype(int) - g_a.astype(int))
        diff_gb_a = np.abs(g_a.astype(int) - b_a.astype(int))
        mean_a = (r_a.astype(int) + g_a.astype(int) + b_a.astype(int)) / 3.0
        built_mask_a = (diff_rg_a < 15) & (diff_gb_a < 15) & (mean_a > 80) & (mean_a < 200)

        diff_rg_b = np.abs(r_b.astype(int) - g_b.astype(int))
        diff_gb_b = np.abs(g_b.astype(int) - b_b.astype(int))
        mean_b = (r_b.astype(int) + g_b.astype(int) + b_b.astype(int)) / 3.0
        built_mask_b = (diff_rg_b < 15) & (diff_gb_b < 15) & (mean_b > 80) & (mean_b < 200)

        built_ratio_a = float(np.sum(built_mask_a) / total_pixels)
        built_ratio_b = float(np.sum(built_mask_b) / total_pixels)
        built_change = built_ratio_b - built_ratio_a

        # Overall change magnitude
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray_a, gray_b)
        overall_change = float(np.mean(diff))

        # Parse question and construct answer
        q_lower = question.lower()

        if any(kw in q_lower for kw in ["built-up", "urban", "building", "city", "construction"]):
            if built_change > 0.03:
                answer = (
                    f"Yes, the built-up area has increased. The structural coverage grew from "
                    f"{built_ratio_a*100:.1f}% to {built_ratio_b*100:.1f}% (a +{built_change*100:.1f}% increase)."
                )
            elif built_change < -0.03:
                answer = (
                    f"The built-up area has decreased, going from {built_ratio_a*100:.1f}% to "
                    f"{built_ratio_b*100:.1f}% (a {built_change*100:.1f}% reduction)."
                )
            else:
                answer = (
                    f"The built-up area has remained relatively unchanged at approximately "
                    f"{built_ratio_b*100:.1f}% coverage."
                )

        elif any(kw in q_lower for kw in ["vegetation", "forest", "green", "deforestation", "tree"]):
            if veg_change > 0.03:
                answer = (
                    f"Vegetation cover has increased from {veg_ratio_a*100:.1f}% to "
                    f"{veg_ratio_b*100:.1f}% (+{veg_change*100:.1f}%)."
                )
            elif veg_change < -0.03:
                answer = (
                    f"Vegetation cover has decreased from {veg_ratio_a*100:.1f}% to "
                    f"{veg_ratio_b*100:.1f}% ({veg_change*100:.1f}%), a vegetation-colour decrease that requires analyst confirmation."
                )
            else:
                answer = f"Vegetation cover has remained stable at approximately {veg_ratio_b*100:.1f}%."

        elif any(kw in q_lower for kw in ["water", "river", "lake", "flood", "ocean"]):
            if water_change > 0.02:
                answer = (
                    f"Water coverage has expanded from {water_ratio_a*100:.1f}% to "
                    f"{water_ratio_b*100:.1f}% (+{water_change*100:.1f}%), a blue-colour increase that requires analyst confirmation."
                )
            elif water_change < -0.02:
                answer = (
                    f"Water coverage has contracted from {water_ratio_a*100:.1f}% to "
                    f"{water_ratio_b*100:.1f}% ({water_change*100:.1f}%), a blue-colour decrease that requires analyst confirmation."
                )
            else:
                answer = f"Water coverage has remained stable at approximately {water_ratio_b*100:.1f}%."

        elif any(kw in q_lower for kw in ["change", "different", "what changed", "describe"]):
            changes = []
            if abs(veg_change) > 0.02:
                direction = "increased" if veg_change > 0 else "decreased"
                changes.append(f"vegetation {direction} by {abs(veg_change)*100:.1f}%")
            if abs(water_change) > 0.02:
                direction = "expanded" if water_change > 0 else "contracted"
                changes.append(f"water bodies {direction} by {abs(water_change)*100:.1f}%")
            if abs(built_change) > 0.02:
                direction = "increased" if built_change > 0 else "decreased"
                changes.append(f"built-up areas {direction} by {abs(built_change)*100:.1f}%")

            if changes:
                answer = f"Between the two dates, the following changes were detected: {'; '.join(changes)}."
            else:
                answer = "No significant changes were detected between the two temporal images."

        else:
            answer = (
                f"Temporal analysis: vegetation shifted by {veg_change*100:+.1f}%, "
                f"water shifted by {water_change*100:+.1f}%, "
                f"built-up shifted by {built_change*100:+.1f}%. "
                f"Overall mean pixel change intensity: {overall_change:.1f}/255."
            )

        elapsed = time.time() - start_time
        confidence = float(np.clip(0.72 + (overall_change / 255) * 0.20, 0.65, 0.95))

        return {
            "answer": answer,
            "confidence": round(confidence, 4),
            "evidence": {
                "temporal_metrics": {
                    "vegetation_t1": round(veg_ratio_a, 4),
                    "vegetation_t2": round(veg_ratio_b, 4),
                    "vegetation_change": round(veg_change, 4),
                    "water_t1": round(water_ratio_a, 4),
                    "water_t2": round(water_ratio_b, 4),
                    "water_change": round(water_change, 4),
                    "builtup_t1": round(built_ratio_a, 4),
                    "builtup_t2": round(built_ratio_b, 4),
                    "builtup_change": round(built_change, 4)
                },
                "overall_pixel_change_intensity": round(overall_change, 2)
            },
            "execution_trace": {
                "task": "Change-based Visual Question Answering",
                "model": f"{self.name} (Spectral Temporal Analysis)",
                "execution_time_seconds": round(elapsed, 4),
                "tools_used": [
                    "Per-channel spectral extraction",
                    "Vegetation/water/built-up masking (T1 & T2)",
                    "Temporal ratio comparison",
                    "Query-grounded answer generation"
                ]
            }
        }
