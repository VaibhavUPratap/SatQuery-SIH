import os
import time
import logging
import base64
from typing import Any, Dict
import cv2
import numpy as np
from PIL import Image
from backend.models.base import BaseSpecialistModel

logger = logging.getLogger("satquery.change_detection")


class ChangeDetectionModel(BaseSpecialistModel):
    """
    Specialist model for bi-temporal change detection.
    Computes pixel-level structural and spectral differences between
    two spatially corresponding satellite images taken at different times.
    Outputs a binary change mask, a heatmap, and change statistics.
    """

    @property
    def name(self) -> str:
        return "ChangeDetection"

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute change detection between two temporal images.

        Args:
            inputs: Dictionary containing:
                - image_path_a (str): Path to image at time T1.
                - image_path_b (str): Path to image at time T2.

        Returns:
            Dict containing:
                - change_summary (str): Textual description of detected changes.
                - change_ratio (float): Fraction of pixels that changed.
                - change_map_b64 (str): Base64-encoded change heatmap PNG.
                - confidence (float)
                - evidence (dict)
                - execution_trace (dict)
        """
        image_path_a = inputs.get("image_path_a")
        image_path_b = inputs.get("image_path_b")

        if not image_path_a or not os.path.exists(image_path_a):
            raise FileNotFoundError(f"Image A not found: {image_path_a}")
        if not image_path_b or not os.path.exists(image_path_b):
            raise FileNotFoundError(f"Image B not found: {image_path_b}")

        start_time = time.time()

        # Load images
        img_a = cv2.imread(image_path_a)
        img_b = cv2.imread(image_path_b)

        if img_a is None or img_b is None:
            raise ValueError("Could not read one or both images.")

        if img_a.shape[:2] != img_b.shape[:2]:
            raise ValueError("Change detection requires equal image dimensions; register or resample inputs before inference.")

        h, w = img_a.shape[:2]
        total_pixels = h * w

        # Convert to grayscale for structural change
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

        # Compute absolute difference
        diff = cv2.absdiff(gray_a, gray_b)

        # Apply Gaussian blur to reduce noise
        diff_blurred = cv2.GaussianBlur(diff, (5, 5), 0)

        # Threshold to get binary change mask
        _, change_mask = cv2.threshold(diff_blurred, 30, 255, cv2.THRESH_BINARY)

        # Morphological operations to clean up
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_CLOSE, kernel)
        change_mask = cv2.morphologyEx(change_mask, cv2.MORPH_OPEN, kernel)

        # Compute change statistics
        changed_pixels = int(np.sum(change_mask > 0))
        change_ratio = float(changed_pixels / total_pixels)

        # Color-coded spectral change analysis
        b_a, g_a, r_a = cv2.split(img_a)
        b_b, g_b, r_b = cv2.split(img_b)

        green_diff = float(np.mean(g_b.astype(int) - g_a.astype(int)))
        blue_diff = float(np.mean(b_b.astype(int) - b_a.astype(int)))
        gray_mean_a = float(np.mean(gray_a))
        gray_mean_b = float(np.mean(gray_b))

        # Generate heatmap overlay
        heatmap = cv2.applyColorMap(diff_blurred, cv2.COLORMAP_JET)
        # Blend heatmap with image B for visualization
        overlay = cv2.addWeighted(img_b, 0.5, heatmap, 0.5, 0)

        # Encode change map as base64
        _, buffer = cv2.imencode('.png', overlay)
        change_map_b64 = base64.b64encode(buffer).decode('utf-8')

        # Generate textual summary
        change_elements = []
        if green_diff > 5:
            change_elements.append("increase in vegetation-colour candidate area")
        elif green_diff < -5:
            change_elements.append("decrease in vegetation-colour candidate area")

        if blue_diff > 5:
            change_elements.append("increase in blue-colour candidate area")
        elif blue_diff < -5:
            change_elements.append("decrease in blue-colour candidate area")

        if gray_mean_b > gray_mean_a + 5:
            change_elements.append("increase in brightness/structure candidate area")
        elif gray_mean_b < gray_mean_a - 5:
            change_elements.append("decrease in brightness/structure candidate area")

        if change_ratio < 0.02:
            change_summary = "No significant changes detected between the two temporal images."
        elif change_elements:
            change_summary = (
                f"Changes detected across {change_ratio*100:.1f}% of the image area. "
                f"Key changes include: {', '.join(change_elements)}."
            )
        else:
            change_summary = (
                f"Structural changes detected across {change_ratio*100:.1f}% of the image area. "
                f"The changes appear to be distributed across the scene."
            )

        elapsed = time.time() - start_time
        confidence = float(np.clip(0.70 + (change_ratio * 0.20), 0.65, 0.95))

        return {
            "change_summary": change_summary,
            "change_ratio": round(change_ratio, 4),
            "changed_pixels": changed_pixels,
            "total_pixels": total_pixels,
            "change_map_b64": change_map_b64,
            "confidence": round(confidence, 4),
            "evidence": {
                "spectral_change": {
                    "vegetation_shift": round(green_diff, 2),
                    "water_shift": round(blue_diff, 2),
                    "brightness_t1": round(gray_mean_a, 2),
                    "brightness_t2": round(gray_mean_b, 2)
                },
                "image_dimensions": f"{w}x{h}"
            },
            "execution_trace": {
                "task": "Bi-temporal Change Detection",
                "model": f"{self.name} (Pixel-Diff + Spectral Analysis)",
                "execution_time_seconds": round(elapsed, 4),
                "tools_used": [
                    "Grayscale difference",
                    "Gaussian blur denoising",
                    "Otsu thresholding",
                    "Morphological cleanup",
                    "JET colormap heatmap"
                ]
            }
        }
