"""Validation and Quality Assurance for NASA-ISRO NISAR Radar Products."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import h5py
import numpy as np

from backend.config import settings
from backend.preprocessing.nisar_reader import NISARProductReader

logger = logging.getLogger("terrapulse.nisar.validator")


class NISARValidator:
    """Validator for NISAR HDF5 files and multi-temporal NISAR observation pairs."""

    @classmethod
    def validate_product(cls, file_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate a single NISAR HDF5 product file.

        Returns:
            Tuple of (is_valid: bool, error_message: str, metadata: dict).
        """
        if not file_path or not os.path.exists(file_path):
            return False, f"File does not exist: {file_path}", {}

        if not NISARProductReader.is_hdf5_file(file_path):
            return False, f"File '{os.path.basename(file_path)}' is not a valid HDF5 archive.", {}

        try:
            metadata = NISARProductReader.inspect_metadata(file_path)
        except Exception as exc:
            return False, f"Failed to inspect NISAR HDF5 structure: {str(exc)}", {}

        if not metadata.get("is_nisar", False):
            return False, "File is an HDF5 archive but lacks the official NISAR /science/LSAR hierarchy.", metadata

        # Check polarizations
        pols = metadata.get("polarizations", [])
        if not pols:
            return False, "NISAR product contains no polarimetric radar layers.", metadata

        # Check dimension limits
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)
        if width <= 0 or height <= 0:
            return False, f"Invalid NISAR grid dimensions: width={width}, height={height}.", metadata

        if width * height > settings.MAX_IMAGE_PIXELS:
            return False, f"NISAR grid pixels ({width*height}) exceed system maximum limit ({settings.MAX_IMAGE_PIXELS}).", metadata

        # Inspect data sample for NaN or corrupt arrays
        try:
            primary_pol = pols[0]
            arr, layer_info = NISARProductReader.read_backscatter(file_path, primary_pol, to_db=False)
            nan_ratio = float(np.count_nonzero(~np.isfinite(arr)) / arr.size)
            if nan_ratio > 0.60:
                return False, f"High missing/corrupted data ratio ({nan_ratio:.1%}) in NISAR band {primary_pol}.", metadata
            metadata["sample_quality"] = {
                "nan_ratio": nan_ratio,
                "mean_linear_power": layer_info["mean"],
                "std_linear_power": layer_info["std"],
            }
        except Exception as exc:
            return False, f"Failed reading polarization layer '{primary_pol}': {str(exc)}", metadata

        return True, "", metadata

    @classmethod
    def validate_temporal_pair(
        cls,
        file_path_t1: str,
        file_path_t2: str,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """Validate two NISAR observations for bi-temporal surface change detection.

        Checks:
        1. Both files are individually valid NISAR products.
        2. Observations have distinct acquisition dates ($T1 \ne T2$).
        3. Common polarizations exist (e.g., both contain HH or both contain HV).
        4. Spatial grids match or have high geographic overlap.
        """
        ok1, err1, meta1 = cls.validate_product(file_path_t1)
        if not ok1:
            return False, f"T1 Product Validation Failed: {err1}", {"t1": meta1}

        ok2, err2, meta2 = cls.validate_product(file_path_t2)
        if not ok2:
            return False, f"T2 Product Validation Failed: {err2}", {"t1": meta1, "t2": meta2}

        pair_meta: Dict[str, Any] = {
            "t1_product": meta1.get("product_type"),
            "t2_product": meta2.get("product_type"),
            "t1_date": meta1.get("acquisition_date"),
            "t2_date": meta2.get("acquisition_date"),
            "t1_bounds": meta1.get("bounds"),
            "t2_bounds": meta2.get("bounds"),
        }

        # Check date difference
        t1_date = meta1.get("acquisition_date")
        t2_date = meta2.get("acquisition_date")
        if t1_date and t2_date and t1_date == t2_date:
            logger.warning("Temporal pair shares the same acquisition date: %s", t1_date)
            pair_meta["warning"] = "Same-day observations; ensure different passes or orbit tracks."

        # Check shared polarizations
        pols1 = set(meta1.get("polarizations", []))
        pols2 = set(meta2.get("polarizations", []))
        common_pols = sorted(list(pols1.intersection(pols2)))
        if not common_pols:
            return False, f"No common polarization between T1 ({pols1}) and T2 ({pols2}).", pair_meta
        pair_meta["common_polarizations"] = common_pols

        # Check spatial dimensions
        w1, h1 = meta1.get("width", 0), meta1.get("height", 0)
        w2, h2 = meta2.get("width", 0), meta2.get("height", 0)
        if (w1, h1) != (w2, h2):
            return False, (
                f"NISAR grid dimension mismatch: T1 is {w1}x{h1}, T2 is {w2}x{h2}. "
                "Co-registration / re-gridding required before temporal change detection."
            ), pair_meta

        if meta1.get("crs") and meta2.get("crs") and meta1["crs"] != meta2["crs"]:
            return False, f"NISAR CRS mismatch: T1 is {meta1['crs']}, T2 is {meta2['crs']}.", pair_meta

        spacing1 = meta1.get("pixel_spacing_meters") or []
        spacing2 = meta2.get("pixel_spacing_meters") or []
        if spacing1 and spacing2 and not np.allclose(spacing1, spacing2, rtol=0, atol=1e-6):
            return False, (
                f"NISAR pixel spacing mismatch: T1 is {spacing1}, T2 is {spacing2}. "
                "Common-grid resampling is required before temporal change detection."
            ), pair_meta

        # Calculate bounding box intersection
        b1, b2 = meta1.get("bounds"), meta2.get("bounds")
        if b1 and b2:
            ix_min = max(b1[0], b2[0])
            iy_min = max(b1[1], b2[1])
            ix_max = min(b1[2], b2[2])
            iy_max = min(b1[3], b2[3])
            if ix_min >= ix_max or iy_min >= iy_max:
                return False, "Spatial bounds of T1 and T2 do not overlap.", pair_meta

            inter_area = (ix_max - ix_min) * (iy_max - iy_min)
            area1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
            area2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
            iou = inter_area / (area1 + area2 - inter_area + 1e-9)
            pair_meta["spatial_overlap_iou"] = round(float(iou), 4)

        pair_meta["status"] = "compatible"
        return True, "", pair_meta
