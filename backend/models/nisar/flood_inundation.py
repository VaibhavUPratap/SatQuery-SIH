"""NISAR Radar Flood Inundation & Surface Water Dynamic Monitoring Specialist.

Applies L-band radar physics to detect:
1. Open water specular reflection drop.
2. Inundated vegetation double-bounce surge.
3. Multi-temporal water expansion and recession metrics.
"""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

from backend.models.base import BaseSpecialistModel
from backend.preprocessing.nisar_reader import NISARProductReader

logger = logging.getLogger("terrapulse.nisar.flood")


class NISARFloodInundationModel(BaseSpecialistModel):
    """Specialist model for radar-based flood inundation and surface water tracking."""

    # Standard L-band thresholds for specular surface water
    DEFAULT_WATER_THRESHOLD_HH_DB = -17.5
    DEFAULT_WATER_THRESHOLD_HV_DB = -25.0

    @property
    def name(self) -> str:
        return "NISARFloodInundation"

    @property
    def version(self) -> str:
        return "2.0.0"

    def _extract_radar_bands(self, path: str) -> Tuple[np.ndarray, Optional[np.ndarray], Dict[str, Any]]:
        """Extract HH and optional HV backscatter from NISAR HDF5 or raster."""
        if NISARProductReader.is_hdf5_file(path):
            meta = NISARProductReader.inspect_metadata(path)
            pols = meta.get("polarizations", [])
            hh_pol = "HHHH" if "HHHH" in pols else ("HH" if "HH" in pols else pols[0])
            hh, _ = NISARProductReader.read_backscatter(path, hh_pol, to_db=True)
            hv = None
            for cross in ["HVHV", "HV", "VHVH", "VH"]:
                if cross in pols:
                    hv, _ = NISARProductReader.read_backscatter(path, cross, to_db=True)
                    break
            return hh, hv, meta
        else:
            # Fallback to change detection loader
            from backend.models.nisar.change_detection import NISARChangeDetectionModel
            helper = NISARChangeDetectionModel()
            hh, meta = helper._load_raster_data(path, "HHHH")
            return hh, None, meta

    def run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scientific flood inundation and water body tracking.

        Args:
            inputs:
                - t1_path / image_path_a: Pre-event baseline NISAR observation.
                - t2_path / image_path_b: Post-event / during-flood NISAR observation.
                - water_threshold_db: Custom water threshold in dB (default: -17.5 dB).

        Returns:
            Dict containing detailed inundation metrics, area in km² and ha,
            water expansion ratio, confidence, and colored flood mask overlay.
        """
        path_t1 = inputs.get("t1_path") or inputs.get("image_path_a")
        path_t2 = inputs.get("t2_path") or inputs.get("image_path_b")
        water_thresh = float(inputs.get("water_threshold_db", self.DEFAULT_WATER_THRESHOLD_HH_DB))

        if not path_t1 or not os.path.exists(path_t1):
            raise FileNotFoundError(f"T1 observation not found: {path_t1}")
        if not path_t2 or not os.path.exists(path_t2):
            raise FileNotFoundError(f"T2 observation not found: {path_t2}")

        start_time = time.time()

        # 1. Read radar backscatter
        hh_t1, hv_t1, meta_t1 = self._extract_radar_bands(path_t1)
        hh_t2, hv_t2, meta_t2 = self._extract_radar_bands(path_t2)

        # Dimension alignment
        if hh_t1.shape != hh_t2.shape:
            hh_t2 = cv2.resize(hh_t2, (hh_t1.shape[1], hh_t1.shape[0]), interpolation=cv2.INTER_LINEAR)
            if hv_t2 is not None:
                hv_t2 = cv2.resize(hv_t2, (hh_t1.shape[1], hh_t1.shape[0]), interpolation=cv2.INTER_LINEAR)

        # 2. Speckle filtering
        hh_t1 = NISARProductReader.apply_speckle_filter(hh_t1, method="lee", window_size=5)
        hh_t2 = NISARProductReader.apply_speckle_filter(hh_t2, method="lee", window_size=5)

        # 3. Open Water Extraction (Specular Reflection Thresholding)
        water_t1 = hh_t1 < water_thresh
        water_t2 = hh_t2 < water_thresh

        # Clean small speckle noise
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        water_t1 = cv2.morphologyEx(water_t1.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
        water_t2 = cv2.morphologyEx(water_t2.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)

        # 4. Classify Water Dynamics
        permanent_water = water_t1 & water_t2
        new_inundation = water_t2 & (~water_t1)
        receded_water = water_t1 & (~water_t2)

        # 5. Inundated Vegetation Double-Bounce (Backscatter surge over vegetation)
        # Vegetation typically has moderate backscatter (-15 to -10 dB) in pre-flood,
        # and double-bounce reflection with standing water increases HH by > 3 dB
        delta_hh = hh_t2 - hh_t1
        veg_candidate = (hh_t1 >= water_thresh) & (hh_t1 < -8.0)
        inundated_veg = veg_candidate & (delta_hh > 3.0) & (~water_t2)
        inundated_veg = cv2.morphologyEx(inundated_veg.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)

        # 6. Spatial Area Quantification
        spacing = meta_t1.get("pixel_spacing_meters", [20.0, 20.0])
        px_area_m2 = abs(spacing[0] * spacing[1])
        px_to_km2 = px_area_m2 / 1_000_000.0
        px_to_ha = px_area_m2 / 10_000.0

        n_perm = int(np.count_nonzero(permanent_water))
        n_new = int(np.count_nonzero(new_inundation))
        n_receded = int(np.count_nonzero(receded_water))
        n_inund_veg = int(np.count_nonzero(inundated_veg))
        n_total_t2 = n_perm + n_new + n_inund_veg

        area_perm_km2 = float(n_perm * px_to_km2)
        area_new_km2 = float(n_new * px_to_km2)
        area_receded_km2 = float(n_receded * px_to_km2)
        area_inund_veg_km2 = float(n_inund_veg * px_to_km2)
        area_total_water_km2 = float(n_total_t2 * px_to_km2)
        area_new_ha = float(n_new * px_to_ha)

        expansion_ratio = float((n_new + n_inund_veg) / max(n_perm, 1))

        # 7. Render Geospatial Visual Overlay
        # Background: grayscale T2 radar image
        norm_t2 = np.clip((hh_t2 + 28.0) / 32.0, 0.0, 1.0)
        bg = (norm_t2 * 255.0).astype(np.uint8)
        rendered = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)

        # Layer Coloring (BGR format):
        rendered[permanent_water] = [210, 110, 20]    # Deep Blue / Navy (Permanent Water)
        rendered[new_inundation] = [240, 220, 0]     # Bright Cyan (New Open Flood Water)
        rendered[inundated_veg] = [200, 20, 220]     # Magenta (Inundated Vegetation)
        rendered[receded_water] = [80, 200, 80]      # Green (Receded / Dry Waterbed)

        final_composite = cv2.addWeighted(cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR), 0.40, rendered, 0.60, 0)
        ok, buf = cv2.imencode(".png", final_composite)
        flood_map_b64 = base64.b64encode(buf.tobytes()).decode("utf-8") if ok else ""

        # Summary Explanation
        t1_date = meta_t1.get("acquisition_date", "T1")
        t2_date = meta_t2.get("acquisition_date", "T2")
        summary = (
            f"NISAR L-band flood inundation analysis between {t1_date} and {t2_date}: "
            f"Detected {area_new_km2:.2f} km² ({area_new_ha:.1f} ha) of newly flooded open terrain "
            f"and {area_inund_veg_km2:.2f} km² of candidate inundated vegetation. "
            f"Baseline permanent water extent was {area_perm_km2:.2f} km², representing a "
            f"{expansion_ratio*100:.1f}% expansion in total surface water."
        )

        confidence = float(np.clip(0.80 + min(0.15, area_new_km2 * 0.05), 0.75, 0.96))

        return {
            "status": "success",
            "task": "nisar_flood_inundation",
            "flood_summary": summary,
            "new_flood_area_km2": round(area_new_km2, 3),
            "new_flood_area_hectares": round(area_new_ha, 1),
            "permanent_water_area_km2": round(area_perm_km2, 3),
            "inundated_vegetation_area_km2": round(area_inund_veg_km2, 3),
            "receded_water_area_km2": round(area_receded_km2, 3),
            "total_water_area_t2_km2": round(area_total_water_km2, 3),
            "water_expansion_ratio": round(expansion_ratio, 3),
            "confidence": confidence,
            "flood_map_b64": flood_map_b64,
            "evidence": {
                "water_threshold_hh_db": water_thresh,
                "t1_metadata": meta_t1,
                "t2_metadata": meta_t2,
                "pixel_spacing_m": spacing,
                "categories": {
                    "permanent_water_pixels": n_perm,
                    "new_inundation_pixels": n_new,
                    "inundated_vegetation_pixels": n_inund_veg,
                    "receded_water_pixels": n_receded,
                },
            },
            "execution_trace": {
                "model": self.name,
                "version": self.version,
                "latency_ms": round((time.time() - start_time) * 1000.0, 2),
            },
        }
