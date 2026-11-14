"""Scientifically Calibrated Multi-Temporal Radar Change Detection Engine.

Replaces naive RGB pixel subtraction with true radar log-ratio change detection,
speckle filtering, and backscatter anomaly quantification.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np
import rasterio

from backend.models.base import BaseSpecialistModel
from backend.preprocessing.nisar_reader import NISARProductReader

logger = logging.getLogger("terrapulse.nisar.change")


class NISARChangeDetectionModel(BaseSpecialistModel):
    """Specialist model for scientific SAR multi-temporal surface change detection.

    Computes decibel backscatter difference:
        Delta_sigma0 = sigma0_T2(dB) - sigma0_T1(dB)
    Applies spatial speckle reduction, adaptive thresholding, and geospatial area quantification.
    """

    @property
    def name(self) -> str:
        return "NISARChangeDetection"

    @property
    def version(self) -> str:
        return "2.0.0"

    def _load_raster_data(self, path: str, pol: str = "HHHH") -> Tuple[np.ndarray, Dict[str, Any]]:
        """Load calibrated radar backscatter in dB from either NISAR HDF5 or SAR GeoTIFF."""
        if NISARProductReader.is_hdf5_file(path):
            arr, info = NISARProductReader.read_backscatter(path, polarization=pol, to_db=True)
            meta = NISARProductReader.inspect_metadata(path)
            return arr, meta
        elif path.lower().endswith((".tif", ".tiff")):
            with rasterio.open(path) as src:
                arr = src.read(1).astype(np.float32)
                # If values are linear (> 0 and max > 1), convert to dB
                if np.nanmax(arr) > 1.0:
                    arr = 10.0 * np.log10(np.maximum(arr, 1e-6))
                meta = {
                    "width": src.width,
                    "height": src.height,
                    "bounds": list(src.bounds),
                    "crs": str(src.crs),
                    "pixel_spacing_meters": [abs(src.transform[0]), abs(src.transform[4])],
                    "acquisition_date": "Unknown Date",
                }
                return arr, meta
        else:
            # Fallback 8-bit image reading with synthetic SAR calibration
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise ValueError(f"Could not load image file: {path}")
            # Map [0, 255] to realistic dB range [-30 dB, +5 dB]
            arr = (img.astype(np.float32) / 255.0) * 35.0 - 30.0
            meta = {
                "width": img.shape[1],
                "height": img.shape[0],
                "pixel_spacing_meters": [20.0, 20.0],
                "acquisition_date": "Unknown Date",
            }
            return arr, meta

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calibrated radar change detection.

        Args:
            inputs:
                - image_path_a / t1_path (str): Observation T1.
                - image_path_b / t2_path (str): Observation T2.
                - polarization (str): 'HHHH' or 'HVHV' (default: 'HHHH').
                - threshold_db (float): Minimum absolute change in dB to flag (default: 3.0 dB).
                - filter_speckle (bool): Whether to apply Lee filtering (default: True).

        Returns:
            Dict containing change_summary, metrics, masks, and base64 overlays.
        """
        path_a = inputs.get("image_path_a") or inputs.get("t1_path")
        path_b = inputs.get("image_path_b") or inputs.get("t2_path")
        pol = inputs.get("polarization", "HHHH")
        threshold_db = float(inputs.get("threshold_db", 3.0))
        filter_speckle = bool(inputs.get("filter_speckle", True))

        if not path_a or not os.path.exists(path_a):
            raise FileNotFoundError(f"Observation T1 not found: {path_a}")
        if not path_b or not os.path.exists(path_b):
            raise FileNotFoundError(f"Observation T2 not found: {path_b}")

        start_time = time.time()

        # 1. Load calibrated dB backscatter
        arr_t1, meta_t1 = self._load_raster_data(path_a, pol)
        arr_t2, meta_t2 = self._load_raster_data(path_b, pol)

        if arr_t1.shape != arr_t2.shape:
            # Resample T2 to match T1 dimensions if needed
            arr_t2 = cv2.resize(arr_t2, (arr_t1.shape[1], arr_t1.shape[0]), interpolation=cv2.INTER_LINEAR)

        # 2. Speckle reduction
        if filter_speckle:
            arr_t1 = NISARProductReader.apply_speckle_filter(arr_t1, method="lee", window_size=5)
            arr_t2 = NISARProductReader.apply_speckle_filter(arr_t2, method="lee", window_size=5)

        # 3. Scientific Log-Ratio / Difference Calculation
        # Delta_sigma0 = T2(dB) - T1(dB) = 10 * log10(sigma0_T2 / sigma0_T1)
        diff_db = arr_t2 - arr_t1

        # 4. Change Segmentation
        decrease_mask = diff_db < -threshold_db  # Backscatter drop (e.g. water inundation, moisture)
        increase_mask = diff_db > threshold_db   # Backscatter rise (e.g. rough surfaces, construction)
        change_mask = decrease_mask | increase_mask

        # Morphological noise cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        change_mask_clean = cv2.morphologyEx(change_mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
        decrease_mask_clean = decrease_mask & change_mask_clean
        increase_mask_clean = increase_mask & change_mask_clean

        # 5. Geospatial Area Quantification
        spacing = meta_t1.get("pixel_spacing_meters", [20.0, 20.0])
        pixel_area_m2 = abs(spacing[0] * spacing[1])
        total_pixels = int(arr_t1.size)
        changed_pixels = int(np.count_nonzero(change_mask_clean))
        decreased_pixels = int(np.count_nonzero(decrease_mask_clean))
        increased_pixels = int(np.count_nonzero(increase_mask_clean))

        changed_area_km2 = float((changed_pixels * pixel_area_m2) / 1_000_000.0)
        changed_area_hectares = float((changed_pixels * pixel_area_m2) / 10_000.0)
        decreased_area_km2 = float((decreased_pixels * pixel_area_m2) / 1_000_000.0)
        increased_area_km2 = float((increased_pixels * pixel_area_m2) / 1_000_000.0)
        change_ratio = float(changed_pixels / total_pixels)

        # 6. Generate Colorized Change Map Overlay
        # Color coding:
        # Red / Magenta = Significant backscatter drop (water inundation / logging)
        # Cyan / Blue = Significant backscatter increase (rough surface / new structure)
        # Gray = Stable background
        norm_t2 = np.clip((arr_t2 + 28.0) / 32.0, 0.0, 1.0)
        bg = (norm_t2 * 255.0).astype(np.uint8)
        color_map = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)

        color_map[decrease_mask_clean] = [40, 50, 240]    # Vibrant Red (BGR)
        color_map[increase_mask_clean] = [230, 180, 20]   # Cyan / Blue (BGR)

        # Add visual legend / alpha blend
        rendered = cv2.addWeighted(cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR), 0.5, color_map, 0.5, 0)
        ok, buf = cv2.imencode(".png", rendered)
        change_map_b64 = base64.b64encode(buf.tobytes()).decode("utf-8") if ok else ""

        # Summary text
        t1_date = meta_t1.get("acquisition_date", "T1")
        t2_date = meta_t2.get("acquisition_date", "T2")
        mean_delta = float(np.mean(diff_db))
        std_delta = float(np.std(diff_db))

        summary = (
            f"Multi-temporal NISAR radar analysis between {t1_date} and {t2_date} detected "
            f"{changed_area_km2:.2f} km² ({changed_area_hectares:.1f} ha) of significant surface change "
            f"({change_ratio*100:.2f}% of monitored area at ±{threshold_db:.1f} dB threshold). "
            f"Backscatter decrease (inundation/smoothing): {decreased_area_km2:.2f} km². "
            f"Backscatter increase (roughness/growth): {increased_area_km2:.2f} km²."
        )

        confidence = float(np.clip(0.70 + (0.25 * min(1.0, std_delta / 2.0)), 0.70, 0.95))

        return {
            "status": "success",
            "task": "nisar_change_detection",
            "change_summary": summary,
            "change_ratio": change_ratio,
            "changed_pixels": changed_pixels,
            "changed_area_km2": changed_area_km2,
            "changed_area_hectares": changed_area_hectares,
            "decreased_area_km2": decreased_area_km2,
            "increased_area_km2": increased_area_km2,
            "mean_delta_db": round(mean_delta, 3),
            "std_delta_db": round(std_delta, 3),
            "threshold_db": threshold_db,
            "confidence": confidence,
            "change_map_b64": change_map_b64,
            "evidence": {
                "t1_metadata": meta_t1,
                "t2_metadata": meta_t2,
                "polarization": pol,
                "speckle_filter": "Enhanced Lee (5x5)" if filter_speckle else "None",
                "pixel_spacing_m": spacing,
            },
            "execution_trace": {
                "model": self.name,
                "version": self.version,
                "latency_ms": round((time.time() - start_time) * 1000.0, 2),
            },
        }
