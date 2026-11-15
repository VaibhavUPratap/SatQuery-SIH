"""Reusable processing service for real NISAR observation pairs.

The service resolves only locally available products, validates them before
processing, and delegates detection/report generation to the existing
validator, specialist models, and LangGraph workflow.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Literal

import h5py
import numpy as np
import rasterio
from pydantic import BaseModel, Field, field_validator
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds

from backend.agent.graph import agent_graph
from backend.config import settings
from backend.models.nisar.change_detection import NISARChangeDetectionModel
from backend.models.nisar.flood_inundation import NISARFloodInundationModel
from backend.preprocessing.nisar_reader import NISARProductReader
from backend.services.external_evidence import inspect_external_evidence
from backend.validation.nisar_validator import NISARValidator


class NISARProcessRequest(BaseModel):
    """Public request contract for a real two-observation NISAR analysis."""

    observation_1: str = Field(..., min_length=1, description="Local product identifier or approved local path.")
    observation_2: str = Field(..., min_length=1, description="Local product identifier or approved local path.")
    product_type: str = Field("GCOV", min_length=1)
    polarizations: list[str] = Field(default_factory=lambda: ["HH", "HV"], min_length=1)
    analysis_type: Literal["change", "flood"] = "change"
    aoi_bbox: list[float] | None = Field(
        default=None,
        min_length=4,
        max_length=4,
        description="[west, south, east, north] in WGS84.",
    )
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("product_type")
    @classmethod
    def normalize_product_type(cls, value: str) -> str:
        normalized = value.upper().replace("L2-", "")
        if normalized != "GCOV":
            raise ValueError("The generalized processing workflow currently supports L2-GCOV products only.")
        return normalized

    @field_validator("polarizations")
    @classmethod
    def normalize_polarizations(cls, values: list[str]) -> list[str]:
        aliases = {"HH": "HHHH", "HV": "HVHV", "HHHH": "HHHH", "HVHV": "HVHV"}
        normalized = [aliases.get(value.upper(), "") for value in values]
        if not normalized or any(not value for value in normalized):
            raise ValueError("Polarizations must be HH, HV, HHHH, or HVHV.")
        return list(dict.fromkeys(normalized))

    @field_validator("aoi_bbox")
    @classmethod
    def validate_bbox(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return None
        west, south, east, north = value
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("aoi_bbox must be a valid WGS84 [west, south, east, north] extent.")
        return value


class NISARProcessError(ValueError):
    """Raised when a requested NISAR workflow cannot be safely executed."""


class NISARProcessingService:
    """Resolve, validate, optionally clip, and process real NISAR products."""

    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        configured_root = os.getenv("NISAR_DATA_ROOT")
        self.allowed_roots = [
            Path(configured_root).expanduser().resolve() if configured_root else repo_root / "datasets",
            repo_root / "datasets",
        ]
    def resolve_observation(self, identifier: str) -> Path:
        """Resolve an identifier to an existing local product without fabricating data."""
        candidate = Path(identifier).expanduser()
        if candidate.is_file():
            resolved = candidate.resolve()
            if settings.DEBUG or any(self._within(resolved, root.resolve()) for root in self.allowed_roots):
                return resolved
            raise NISARProcessError("Local observation paths are restricted to configured NISAR data roots.")

        basename = Path(identifier).name
        for root in self.allowed_roots:
            if not root.exists():
                continue
            matches = list(root.rglob(basename))
            if matches:
                return matches[0].resolve()

        raise NISARProcessError(
            f"Observation '{identifier}' was not found in configured local NISAR data roots. "
            "Search metadata does not substitute for a downloaded product."
        )

    @staticmethod
    def _within(path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False

    def _validate_pair(self, path_1: Path, path_2: Path, polarizations: list[str]) -> dict[str, Any]:
        hdf5_pair = NISARProductReader.is_hdf5_file(str(path_1)) and NISARProductReader.is_hdf5_file(str(path_2))
        if hdf5_pair:
            valid, error, pair = NISARValidator.validate_temporal_pair(str(path_1), str(path_2))
            if not valid:
                raise NISARProcessError(error)
            available = set(pair.get("common_polarizations", []))
            missing = [pol for pol in polarizations if pol not in available]
            if missing:
                raise NISARProcessError(f"Requested polarization(s) unavailable in both products: {', '.join(missing)}.")
            return {"validation": "NISAR HDF5 temporal pair", "pair": pair}

        if path_1.suffix.lower() not in {".tif", ".tiff"} or path_2.suffix.lower() not in {".tif", ".tiff"}:
            raise NISARProcessError("Processing requires two validated NISAR HDF5 products or GeoTIFF extracts.")

        with rasterio.open(path_1) as first, rasterio.open(path_2) as second:
            if first.crs is None or second.crs is None:
                raise NISARProcessError("Both raster products must have a CRS.")
            if first.crs != second.crs or first.width != second.width or first.height != second.height:
                raise NISARProcessError("NISAR raster products must share CRS and dimensions.")
            bounds_1 = list(first.bounds)
            bounds_2 = list(second.bounds)
            if not (
                max(bounds_1[0], bounds_2[0]) < min(bounds_1[2], bounds_2[2])
                and max(bounds_1[1], bounds_2[1]) < min(bounds_1[3], bounds_2[3])
            ):
                raise NISARProcessError("NISAR raster products do not overlap spatially.")
            return {
                "validation": "GeoTIFF extract compatibility",
                "pair": {
                    "crs": str(first.crs),
                    "width": first.width,
                    "height": first.height,
                    "bounds": bounds_1,
                    "status": "compatible",
                },
            }

    def _clip_raster(self, path: Path, bbox: list[float], output_dir: Path) -> Path:
        with rasterio.open(path) as source:
            if source.crs is None:
                raise NISARProcessError(f"Raster '{path.name}' has no CRS.")
            projected = transform_bounds("EPSG:4326", source.crs, *bbox, densify_pts=21)
            window = source.window(*projected).round_offsets().round_lengths()
            window = window.intersection(rasterio.windows.Window(0, 0, source.width, source.height))
            if window.width < 1 or window.height < 1:
                raise NISARProcessError(f"AOI does not overlap raster '{path.name}'.")
            profile = source.profile.copy()
            profile.update(
                height=int(window.height),
                width=int(window.width),
                transform=source.window_transform(window),
                driver="GTiff",
                compress="deflate",
            )
            if window.width >= 256 and window.height >= 256:
                profile.update(tiled=True, blockxsize=256, blockysize=256)
            target = output_dir / path.name
            with rasterio.open(target, "w", **profile) as destination:
                destination.write(source.read(window=window))
                if destination.width >= 256 and destination.height >= 256:
                    levels = [level for level in (2, 4, 8, 16) if destination.width // level >= 32 and destination.height // level >= 32]
                    if levels:
                        destination.build_overviews(levels, rasterio.enums.Resampling.average)
                        destination.update_tags(ns="rio_overview", resampling="average")
        return target

    def _extract_hdf5_aoi(self, path: Path, polarization: str, bbox: list[float], output_dir: Path) -> Path:
        """Window-read one HDF5 measurement and materialize an AOI GeoTIFF."""
        metadata = NISARProductReader.inspect_metadata(str(path))
        crs = metadata.get("crs")
        if not crs:
            raise NISARProcessError(f"NISAR product '{path.name}' has no projected CRS.")
        projected = transform_bounds("EPSG:4326", crs, *bbox, densify_pts=21)
        dataset_name = polarization
        with h5py.File(path, "r") as handle:
            group_path = "/science/LSAR/GCOV/grids/frequencyA"
            if group_path not in handle:
                raise NISARProcessError("Expected NISAR GCOV frequencyA group is missing.")
            group = handle[group_path]
            if dataset_name not in group:
                raise NISARProcessError(f"Requested polarization '{dataset_name}' is not present.")
            x = np.asarray(group["xCoordinates"][()])
            y = np.asarray(group["yCoordinates"][()])
            cols = np.flatnonzero((x >= projected[0]) & (x <= projected[2]))
            rows = np.flatnonzero((y >= projected[1]) & (y <= projected[3]))
            if not len(cols) or not len(rows):
                raise NISARProcessError(f"AOI does not overlap product '{path.name}'.")
            dataset = group[dataset_name]
            data = np.asarray(dataset[rows.min():rows.max() + 1, cols.min():cols.max() + 1], dtype=np.float32)
            x0 = float(x[cols.min()])
            y0 = float(y[rows.min()])
            x_spacing = abs(float(np.median(np.diff(x))))
            y_spacing = abs(float(np.median(np.diff(y))))
            profile = {
                "driver": "GTiff",
                "height": data.shape[0],
                "width": data.shape[1],
                "count": 1,
                "dtype": "float32",
                "crs": crs,
                "transform": from_origin(x0, y0, x_spacing, y_spacing),
                "nodata": np.nan,
                "compress": "deflate",
            }
            if data.shape[1] >= 256 and data.shape[0] >= 256:
                profile.update(tiled=True, blockxsize=256, blockysize=256)
            target = output_dir / f"{path.stem}_{polarization}_aoi.tif"
            with rasterio.open(target, "w", **profile) as destination:
                destination.write(data, 1)
                if destination.width >= 256 and destination.height >= 256:
                    levels = [level for level in (2, 4, 8, 16) if destination.width // level >= 32 and destination.height // level >= 32]
                    if levels:
                        destination.build_overviews(levels, rasterio.enums.Resampling.average)
                        destination.update_tags(ns="rio_overview", resampling="average")
        return target

    def process(self, request: NISARProcessRequest) -> dict[str, Any]:
        """Execute a validated real-product workflow synchronously for a job worker."""
        if request.analysis_type == "flood" and "HHHH" not in request.polarizations:
            raise NISARProcessError("Flood analysis requires the HH polarization.")
        path_1 = self.resolve_observation(request.observation_1)
        path_2 = self.resolve_observation(request.observation_2)
        compatibility = self._validate_pair(path_1, path_2, request.polarizations)
        requested = request.polarizations
        work_dir = Path(tempfile.mkdtemp(prefix="terrapulse_nisar_"))
        try:
            results: dict[str, Any] = {}
            if request.analysis_type == "flood":
                if request.aoi_bbox:
                    if NISARProductReader.is_hdf5_file(str(path_1)):
                        t1 = self._extract_hdf5_aoi(path_1, "HHHH", request.aoi_bbox, work_dir)
                        t2 = self._extract_hdf5_aoi(path_2, "HHHH", request.aoi_bbox, work_dir)
                    else:
                        t1 = self._clip_raster(path_1, request.aoi_bbox, work_dir)
                        t2 = self._clip_raster(path_2, request.aoi_bbox, work_dir)
                else:
                    t1, t2 = path_1, path_2
                flood_result = NISARFloodInundationModel().run({
                    "t1_path": str(t1),
                    "t2_path": str(t2),
                    **request.parameters,
                })
                results["flood"] = flood_result
            else:
                for polarization in requested:
                    if request.aoi_bbox and NISARProductReader.is_hdf5_file(str(path_1)):
                        t1 = self._extract_hdf5_aoi(path_1, polarization, request.aoi_bbox, work_dir)
                        t2 = self._extract_hdf5_aoi(path_2, polarization, request.aoi_bbox, work_dir)
                    elif request.aoi_bbox:
                        t1 = self._clip_raster(path_1, request.aoi_bbox, work_dir)
                        t2 = self._clip_raster(path_2, request.aoi_bbox, work_dir)
                    else:
                        t1, t2 = path_1, path_2

                    tool = NISARChangeDetectionModel()
                    inputs = {
                        "image_path_a": str(t1),
                        "image_path_b": str(t2),
                        "polarization": polarization,
                        **request.parameters,
                    }
                    result = tool.run(inputs)
                    results[polarization] = result

            primary = results.get(requested[0]) or results["flood"]
            external_evidence = inspect_external_evidence(
                request.parameters.get("external_sources"),
                request.aoi_bbox,
                self.allowed_roots,
            )
            return {
                "status": "success",
                "analysis_type": request.analysis_type,
                "product_type": request.product_type,
                "polarizations": requested,
                "observations": [path_1.name, path_2.name],
                "aoi_bbox": request.aoi_bbox,
                "compatibility": compatibility,
                "results": results,
                "answer": (
                    "NISAR candidate backscatter analysis completed for the requested "
                    "polarization channels. These are potential-change indicators, not confirmed events."
                ),
                "confidence": primary.get("confidence"),
                "overlay_b64": primary.get("change_map_b64") or primary.get("flood_map_b64"),
                "change_summary": primary.get("change_summary"),
                "flood_summary": primary.get("flood_summary"),
                "changed_pixels": primary.get("changed_pixels"),
                "changed_area_hectares": primary.get("changed_area_hectares"),
                "evidence": {
                    "scientific_status": "candidate_radar_backscatter_anomaly",
                    "external_evidence": external_evidence,
                    "limitations": [
                        "Candidate regions are not independently confirmed flooding, construction, urbanization, or deforestation.",
                        "Physical interpretation requires contemporaneous independent evidence.",
                    ],
                    "channel_results": {
                        pol: {
                            "changed_pixels": item.get("changed_pixels"),
                            "changed_area_hectares": item.get("changed_area_hectares"),
                            "threshold_db": item.get("threshold_db"),
                        }
                        for pol, item in results.items()
                    },
                },
            }
        finally:
            for child in work_dir.iterdir():
                child.unlink(missing_ok=True)
            work_dir.rmdir()
