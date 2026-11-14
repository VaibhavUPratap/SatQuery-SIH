"""NASA-ISRO NISAR Mission Radar Product Ingestion & Processing Engine.

Supports NISAR L2-GCOV (Geocoded Polarimetric Covariance), L2-GSLC,
and associated L-band / S-band SAR hierarchical HDF5 data structures.
"""
from __future__ import annotations

import base64
import datetime
import io
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import h5py
import numpy as np
from scipy.ndimage import uniform_filter

logger = logging.getLogger("terrapulse.nisar.reader")


class NISARProductReader:
    """Reader, validator, and extractor for NASA-ISRO NISAR HDF5 data products."""

    # Official NISAR product types
    SUPPORTED_PRODUCTS = {
        "GCOV": "Geocoded Polarimetric Covariance",
        "GSLC": "Geocoded Single-Look Complex",
        "RSLC": "Range-Doppler Single-Look Complex",
        "GUNW": "Geocoded Unwrapped Interferogram",
        "RIFG": "Range-Doppler Interferogram",
        "SME2": "Soil Moisture Estimation",
    }

    @staticmethod
    def is_hdf5_file(file_path: str) -> bool:
        """Check if file is a valid HDF5 file."""
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 512:
            return False
        return h5py.is_hdf5(file_path)

    @classmethod
    def inspect_metadata(cls, file_path: str) -> Dict[str, Any]:
        """Extract comprehensive scientific and geospatial metadata from a NISAR HDF5 file."""
        if not cls.is_hdf5_file(file_path):
            raise ValueError(f"File '{file_path}' is not a valid HDF5 file.")

        metadata: Dict[str, Any] = {
            "file_name": os.path.basename(file_path),
            "file_size_bytes": os.path.getsize(file_path),
            "format": "HDF5",
            "is_nisar": False,
            "sensor": "NISAR L-band SAR",
            "modality": "SAR",
            "polarizations": [],
            "geospatial": False,
        }

        with h5py.File(file_path, "r") as h5:
            # 1. Detect NISAR root group: /science/LSAR or /science/SSAR or fallback
            radar_group = None
            for candidate in ["/science/LSAR", "/science/SSAR", "/science/SAR", "/"]:
                if candidate in h5:
                    radar_group = h5[candidate]
                    break

            if radar_group is None:
                metadata["warning"] = "Non-standard HDF5 hierarchy. Expected '/science/LSAR'."
                return metadata

            # Check product type from group name (GCOV, GSLC, etc.)
            product_type = None
            product_group = None
            for p_type in cls.SUPPORTED_PRODUCTS:
                if p_type in radar_group:
                    product_type = p_type
                    product_group = radar_group[p_type]
                    break

            if product_group is None:
                # Might be directly under radar_group
                product_group = radar_group
                product_type = "GCOV"

            metadata["is_nisar"] = True
            metadata["product_type"] = f"L2-{product_type}" if product_type in {"GCOV", "GSLC", "GUNW"} else f"L1-{product_type}"
            metadata["product_description"] = cls.SUPPORTED_PRODUCTS.get(product_type, "Radar Product")

            # 2. Extract Identification Attributes
            ident_group = product_group.get("identification")
            if ident_group:
                for key in [
                    "missionId", "productType", "absoluteOrbitNumber", "trackNumber",
                    "frameNumber", "boundingPolygon", "lookDirection",
                    "orbitPassDirection", "zeroDopplerStartTime", "zeroDopplerEndTime"
                ]:
                    if key in ident_group:
                        val = ident_group[key][()]
                        if isinstance(val, (bytes, np.bytes_)):
                            val = val.decode("utf-8", errors="replace")
                        metadata[key] = str(val)

                if "zeroDopplerStartTime" in metadata:
                    raw_dt = metadata["zeroDopplerStartTime"]
                    match = re.search(r"(\d{4}-\d{2}-\d{2})", raw_dt)
                    if match:
                        metadata["acquisition_date"] = match.group(1)

            # 3. Extract Grid & Georeferencing Information
            grids_group = product_group.get("grids")
            freq_group = None
            if grids_group:
                for f_name in ["frequencyA", "frequencyB", "freqA"]:
                    if f_name in grids_group:
                        freq_group = grids_group[f_name]
                        metadata["frequency_band"] = "Frequency A (L-band 1.25 GHz)"
                        break

            if freq_group:
                # Polarizations
                pols: List[str] = []
                if "listOfPolarizations" in freq_group:
                    raw_pols = freq_group["listOfPolarizations"][()]
                    for p in raw_pols:
                        if isinstance(p, (bytes, np.bytes_)):
                            p = p.decode("utf-8", errors="replace")
                        pols.append(str(p))
                else:
                    # Discover dataset keys matching polarization names
                    for k in freq_group.keys():
                        if k in {"HHHH", "HVHV", "VVVV", "VHVH", "HH", "HV", "VV", "VH"}:
                            pols.append(k)

                metadata["polarizations"] = pols
                metadata["polarization"] = "+".join(pols) if pols else "L-band Dual-Pol"

                # Spatial coordinates & CRS
                if "projection" in freq_group:
                    proj = freq_group["projection"][()]
                    if isinstance(proj, (bytes, np.bytes_)):
                        proj = proj.decode("utf-8", errors="replace")
                    metadata["crs"] = str(proj)
                    metadata["geospatial"] = True

                if "xCoordinates" in freq_group and "yCoordinates" in freq_group:
                    x_coords = freq_group["xCoordinates"]
                    y_coords = freq_group["yCoordinates"]
                    metadata["width"] = int(len(x_coords))
                    metadata["height"] = int(len(y_coords))
                    x_min, x_max = float(x_coords[0]), float(x_coords[-1])
                    y_max, y_min = float(y_coords[0]), float(y_coords[-1])
                    metadata["bounds"] = [min(x_min, x_max), min(y_min, y_max), max(x_min, x_max), max(y_min, y_max)]
                    metadata["geospatial"] = True

                    if "coordinateSpacing" in freq_group:
                        spacing = freq_group["coordinateSpacing"][()]
                        metadata["pixel_spacing_meters"] = [float(s) for s in spacing] if hasattr(spacing, "__iter__") else [float(spacing)]

        return metadata

    @classmethod
    def read_backscatter(
        cls,
        file_path: str,
        polarization: str = "HHHH",
        to_db: bool = True,
        clip_percentiles: Tuple[float, float] = (1.0, 99.0),
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Read a single polarization backscatter layer from NISAR HDF5.

        Args:
            file_path: Path to NISAR HDF5 file.
            polarization: Layer key (e.g., 'HHHH', 'HVHV', 'HH', 'HV').
            to_db: If True, convert linear power to decibels (10*log10(power)).
            clip_percentiles: (min_p, max_p) percentiles for numerical stability.

        Returns:
            Tuple of (2D numpy array, layer metadata dict).
        """
        metadata = cls.inspect_metadata(file_path)

        with h5py.File(file_path, "r") as h5:
            # Find dataset
            dataset = None
            found_pol = None

            # Look in standard NISAR hierarchy
            for root in ["/science/LSAR/GCOV/grids/frequencyA", "/science/LSAR/GSLC/grids/frequencyA", "/"]:
                if root in h5:
                    grp = h5[root]
                    # Direct match or alias
                    candidates = [polarization, polarization.upper(), polarization.replace("HH", "HHHH"), polarization[:2]]
                    for c in candidates:
                        if c in grp:
                            dataset = grp[c]
                            found_pol = c
                            break
                if dataset is not None:
                    break

            if dataset is None:
                raise KeyError(
                    f"Polarization '{polarization}' not found in '{file_path}'. "
                    f"Available polarizations: {metadata.get('polarizations')}"
                )

            data = np.array(dataset[()], dtype=np.float32)

            # Complex data handling (GSLC) -> calculate intensity
            if np.iscomplexobj(data):
                data = np.abs(data) ** 2

            # Replace NaNs or infinite values
            valid_mask = np.isfinite(data) & (data > 0)
            if not np.any(valid_mask):
                raise ValueError(f"Polarization layer '{polarization}' contains no valid positive pixels.")

            # Replace invalid with minimum valid positive value
            min_val = float(np.min(data[valid_mask]))
            data[~valid_mask] = min_val

            if to_db:
                # Sigma0 in dB: 10 * log10(power)
                data_db = 10.0 * np.log10(np.maximum(data, 1e-7))
                if clip_percentiles:
                    p_low, p_high = np.percentile(data_db, clip_percentiles)
                    data_db = np.clip(data_db, p_low, p_high)
                result = data_db
            else:
                result = data

            layer_info = {
                "polarization": found_pol,
                "unit": "dB (sigma-nought)" if to_db else "linear backscatter power",
                "shape": list(result.shape),
                "min": float(np.min(result)),
                "max": float(np.max(result)),
                "mean": float(np.mean(result)),
                "std": float(np.std(result)),
            }

            return result, layer_info

    @classmethod
    def read_dual_pol(
        cls,
        file_path: str,
        co_pol: str = "HHHH",
        cross_pol: str = "HVHV",
        to_db: bool = True,
    ) -> Dict[str, Any]:
        """Read both Co-Pol (HH) and Cross-Pol (HV) layers and compute polarimetric cross-ratio.

        Returns:
            Dict with 'co_pol', 'cross_pol', 'ratio', and summary metrics.
        """
        arr_co, info_co = cls.read_backscatter(file_path, co_pol, to_db=to_db)
        arr_cross, info_cross = cls.read_backscatter(file_path, cross_pol, to_db=to_db)

        if arr_co.shape != arr_cross.shape:
            raise ValueError(f"Co-pol shape {arr_co.shape} != cross-pol shape {arr_cross.shape}")

        if to_db:
            # In dB: Cross/Co ratio is difference (HV_dB - HH_dB)
            ratio = arr_cross - arr_co
        else:
            ratio = arr_cross / np.maximum(arr_co, 1e-6)

        return {
            "co_pol": arr_co,
            "cross_pol": arr_cross,
            "ratio": ratio,
            "co_info": info_co,
            "cross_info": info_cross,
            "mean_co_pol_db": float(np.mean(arr_co)) if to_db else float(10 * np.log10(max(np.mean(arr_co), 1e-6))),
            "mean_cross_pol_db": float(np.mean(arr_cross)) if to_db else float(10 * np.log10(max(np.mean(arr_cross), 1e-6))),
            "mean_ratio_db": float(np.mean(ratio)) if to_db else float(10 * np.log10(max(np.mean(ratio), 1e-6))),
        }

    @staticmethod
    def apply_speckle_filter(raster: np.ndarray, method: str = "lee", window_size: int = 5) -> np.ndarray:
        """Apply spatial speckle reduction to radar backscatter raster.

        Supports Enhanced Lee filter and Spatial Boxcar filter.
        """
        if window_size % 2 == 0:
            window_size += 1

        if method.lower() == "boxcar":
            return uniform_filter(raster, size=window_size)

        # Enhanced Lee Filter
        mean = uniform_filter(raster, size=window_size)
        mean_sq = uniform_filter(raster ** 2, size=window_size)
        variance = np.maximum(mean_sq - mean ** 2, 0)

        # Estimate noise variance from local variance
        overall_variance = float(np.var(raster))
        if overall_variance <= 1e-8:
            return raster

        weights = variance / (variance + overall_variance + 1e-8)
        weights = np.clip(weights, 0.0, 1.0)

        filtered = mean + weights * (raster - mean)
        return filtered.astype(np.float32)

    @classmethod
    def generate_preview_png(
        cls,
        file_path: str,
        co_pol: str = "HHHH",
        cross_pol: str = "HVHV",
    ) -> Tuple[bytes, str]:
        """Generate a false-color polarimetric RGB composite preview from NISAR HDF5.

        RGB Mapping standard for SAR Polarimetry:
        - Red: Co-Pol HH backscatter (surface scattering / double-bounce)
        - Green: Cross-Pol HV backscatter (vegetation volume scattering)
        - Blue: Dual-Pol ratio (HH / HV)
        """
        try:
            dual = cls.read_dual_pol(file_path, co_pol=co_pol, cross_pol=cross_pol, to_db=True)
            r = dual["co_pol"]
            g = dual["cross_pol"]
            b = dual["co_pol"] - dual["cross_pol"]  # HH - HV ratio in dB
        except Exception:
            # Fallback to single polarization
            r, _ = cls.read_backscatter(file_path, polarization=co_pol, to_db=True)
            g = r.copy()
            b = r.copy()

        def norm8(arr: np.ndarray) -> np.ndarray:
            p2, p98 = np.percentile(arr, (2, 98))
            scaled = np.clip((arr - p2) / (p98 - p2 + 1e-6), 0.0, 1.0)
            return (scaled * 255).astype(np.uint8)

        r8 = norm8(r)
        g8 = norm8(g)
        b8 = norm8(b)

        # Compose BGR for OpenCV
        rgb = np.stack([b8, g8, r8], axis=-1)
        ok, buf = cv2.imencode(".png", rgb)
        if not ok:
            raise RuntimeError("Failed to encode preview image.")

        png_bytes = buf.tobytes()
        b64_str = base64.b64encode(png_bytes).decode("utf-8")
        return png_bytes, b64_str

    @classmethod
    def create_synthetic_nisar_gcov(
        cls,
        output_path: str,
        width: int = 256,
        height: int = 256,
        with_flood: bool = False,
        date_str: str = "2026-06-15",
        granule_id: str = "NISAR_L2_PR_GCOV_001_001_A_123_20260615T000000_20260615T000010_D00100_M_F_J_001.h5",
    ) -> str:
        """Create a scientifically valid synthetic NISAR L2-GCOV HDF5 granule for testing.

        Creates realistic L-band radar backscatter distributions:
        - Smooth water body: low backscatter (-22 to -26 dB in HH, -30 to -34 dB in HV)
        - Forest canopy: volume scattering (-10 to -14 dB in HH, -16 to -20 dB in HV)
        - Agricultural/Bare soil: -12 to -18 dB in HH
        - Urban built-up: double-bounce (0 to +5 dB in HH)
        - Flood condition: expanding the low-backscatter specular water zone
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Coordinates (centered around Bengaluru / Kaveri basin for local event context)
        # EPSG: 32643 (WGS 84 / UTM Zone 43N)
        x_min, x_max = 750000.0, 750000.0 + (width * 20.0)
        y_max, y_min = 1420000.0, 1420000.0 - (height * 20.0)
        x_coords = np.linspace(x_min, x_max, width, dtype=np.float64)
        y_coords = np.linspace(y_max, y_min, height, dtype=np.float64)

        # Generate terrain landscape
        np.random.seed(42 if not with_flood else 100)
        # Background: mixed vegetation and agriculture
        hh_db = -13.0 + np.random.normal(0, 1.8, (height, width)).astype(np.float32)
        hv_db = -19.0 + np.random.normal(0, 2.0, (height, width)).astype(np.float32)

        # Add a permanent river corridor (diagonal curve)
        y_grid, x_grid = np.ogrid[:height, :width]
        river_center = (width * 0.4) + 30.0 * np.sin(y_grid / 30.0)
        river_mask = np.abs(x_grid - river_center) < (8 if not with_flood else 28)

        # Add a flood inundation wetland / lake zone if with_flood is True
        if with_flood:
            flood_lake = ((x_grid - width * 0.6) ** 2 + (y_grid - height * 0.5) ** 2) < (45 ** 2)
            water_mask = river_mask | flood_lake
        else:
            water_mask = river_mask

        # Over water: specular reflection drops backscatter significantly
        hh_db[water_mask] = -24.0 + np.random.normal(0, 1.0, np.count_nonzero(water_mask)).astype(np.float32)
        hv_db[water_mask] = -32.0 + np.random.normal(0, 1.2, np.count_nonzero(water_mask)).astype(np.float32)

        # Add an urban cluster with strong double-bounce backscatter
        urban_mask = ((x_grid - width * 0.2) ** 2 + (y_grid - height * 0.25) ** 2) < (22 ** 2)
        hh_db[urban_mask] = 2.0 + np.random.normal(0, 2.5, np.count_nonzero(urban_mask)).astype(np.float32)
        hv_db[urban_mask] = -8.0 + np.random.normal(0, 2.0, np.count_nonzero(urban_mask)).astype(np.float32)

        # Convert dB to linear covariance power: 10^(dB/10)
        hhhh_power = 10.0 ** (hh_db / 10.0)
        hvhv_power = 10.0 ** (hv_db / 10.0)

        with h5py.File(output_path, "w") as h5:
            # 1. Structure: /science/LSAR/GCOV/
            gcov = h5.create_group("/science/LSAR/GCOV")

            # 2. Identification Group
            ident = gcov.create_group("identification")
            ident.create_dataset("missionId", data=np.bytes_("NISAR"))
            ident.create_dataset("productType", data=np.bytes_("GCOV"))
            ident.create_dataset("granuleId", data=np.bytes_(granule_id))
            ident.create_dataset("absoluteOrbitNumber", data=np.bytes_("01234"))
            ident.create_dataset("trackNumber", data=np.bytes_("123"))
            ident.create_dataset("frameNumber", data=np.bytes_("456"))
            ident.create_dataset("lookDirection", data=np.bytes_("Left"))
            ident.create_dataset("orbitPassDirection", data=np.bytes_("Ascending"))
            ident.create_dataset("zeroDopplerStartTime", data=np.bytes_(f"{date_str}T06:30:00.000000Z"))
            ident.create_dataset("zeroDopplerEndTime", data=np.bytes_(f"{date_str}T06:30:30.000000Z"))
            ident.create_dataset("boundingPolygon", data=np.bytes_(
                f"POLYGON(({x_min} {y_min}, {x_max} {y_min}, {x_max} {y_max}, {x_min} {y_max}, {x_min} {y_min}))"
            ))

            # 3. Grids / frequencyA Group
            freq_a = gcov.create_group("grids/frequencyA")
            freq_a.create_dataset("coordinateSpacing", data=np.array([20.0, 20.0], dtype=np.float64))
            freq_a.create_dataset("xCoordinates", data=x_coords)
            freq_a.create_dataset("yCoordinates", data=y_coords)
            freq_a.create_dataset("projection", data=np.bytes_("EPSG:32643"))
            freq_a.create_dataset("listOfPolarizations", data=np.array([b"HHHH", b"HVHV"]))

            # Polarimetric Covariance Datasets
            freq_a.create_dataset("HHHH", data=hhhh_power, compression="gzip", compression_opts=4)
            freq_a.create_dataset("HVHV", data=hvhv_power, compression="gzip", compression_opts=4)

        logger.info("Successfully synthesized NISAR L2-GCOV product: %s", output_path)
        return output_path
