"""FastAPI endpoints for NASA-ISRO NISAR radar products."""
from __future__ import annotations

import logging
import os
import tempfile
import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from rasterio.warp import transform_geom

from backend.api.upload import persist_upload
from backend.preprocessing.nisar_reader import NISARProductReader
from backend.preprocessing.nisar_search import search_nisar_granules
from backend.validation.nisar_validator import NISARValidator
from backend.api.auth import current_user
from backend.api.nisar_jobs import create_nisar_job, get_nisar_job
from backend.services.nisar_processing import NISARProcessRequest

logger = logging.getLogger("terrapulse.api.nisar")
router = APIRouter(prefix="/nisar", tags=["NISAR Earth Observation"])
CASE_STUDY_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "processed" / "bengaluru"
CASE_STUDY_ANALYSIS = CASE_STUDY_ROOT / "change_analysis"
CASE_STUDY_CONTEXT = CASE_STUDY_ANALYSIS / "geospatial_interpretation"


class SearchRequest(BaseModel):
    bbox: Optional[List[float]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    product_type: str = "GCOV"
    max_results: int = 10


class SynthesizeRequest(BaseModel):
    target_date: str = "2026-07-15"
    with_flood: bool = True
    width: int = 256
    height: int = 256


@router.post("/process", status_code=status.HTTP_202_ACCEPTED)
async def process_nisar_observations(
    request: NISARProcessRequest,
    owner: str = Depends(current_user),
):
    """Queue processing for two locally available, real NISAR observations."""
    try:
        job_id = create_nisar_job(request, owner)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    return {
        "job_id": job_id,
        "status": "queued",
        "message": "NISAR processing queued. Poll the job status endpoint for progress.",
    }


@router.get("/jobs/{job_id}", status_code=status.HTTP_200_OK)
async def nisar_job_status(job_id: str, owner: str = Depends(current_user)):
    """Return owned NISAR processing status, progress, and failure details."""
    job = get_nisar_job(job_id, owner)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NISAR job not found.")
    return job


@router.get("/jobs/{job_id}/results", status_code=status.HTTP_200_OK)
async def nisar_job_results(job_id: str, owner: str = Depends(current_user)):
    """Return results only after an owned NISAR job has completed."""
    job = get_nisar_job(job_id, owner)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NISAR job not found.")
    if job["status"] == "failed":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=job.get("error"))
    if job["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="NISAR job is not complete.")
    return {"job_id": job_id, "status": job["status"], "result": job.get("result")}


@router.get("/jobs/{job_id}/trace", status_code=status.HTTP_200_OK)
async def nisar_job_trace(job_id: str, owner: str = Depends(current_user)):
    """Return the auditable execution trace for an owned NISAR job."""
    job = get_nisar_job(job_id, owner)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="NISAR job not found.")
    return {"job_id": job_id, "status": job["status"], "trace": job.get("trace", [])}


@router.get("/bengaluru/case-study", status_code=status.HTTP_200_OK)
async def get_bengaluru_case_study():
    """Return the verified, read-only Bengaluru NISAR case-study catalog."""
    summary_path = CASE_STUDY_CONTEXT / "candidate_area_summary.csv"
    compatibility_path = CASE_STUDY_ROOT / "validation_grid_compatibility.json"
    context_path = CASE_STUDY_CONTEXT / "data_context_status.json"
    required = (summary_path, compatibility_path, context_path)
    if not all(path.is_file() for path in required):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Verified Bengaluru NISAR case-study outputs are not available.",
        )

    with summary_path.open(newline="", encoding="utf-8") as handle:
        area_summary = list(csv.DictReader(handle))
    with compatibility_path.open(encoding="utf-8") as handle:
        grid_validation = json.load(handle)
    with context_path.open(encoding="utf-8") as handle:
        context_status = json.load(handle)

    return {
        "study_area": {
            "name": "Bengaluru, Karnataka, India",
            "bbox_wgs84": [77.40, 12.80, 77.80, 13.15],
            "crs": "EPSG:32643",
            "resolution_m": 10,
        },
        "observations": [
            {
                "date": "2026-10-29",
                "label": "29 October 2026",
                "granule_id": "NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001",
            },
            {
                "date": "2026-11-10",
                "label": "10 November 2026",
                "granule_id": "NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001",
            },
        ],
        "measurements": {
            "quantity": "RTC gamma-zero (linear power)",
            "polarizations": ["HH", "HV"],
            "sensor": "NASA-ISRO NISAR L-SAR",
            "frequency": "L-band, center frequency 1.239 GHz",
            "product": "L2 GCOV",
            "track": 77,
            "frame": 82,
            "orbit_direction": "Descending",
        },
        "processing_history": [
            "Phase 1: HDF5 integrity, metadata, measurement paths, and grid validation",
            "Phase 2: windowed HH/HV extraction with quality and exception masks",
            "Phase 3: common-valid temporal comparison and robust spatial screening",
            "Phase 4: projected candidate polygonization and area calculation",
        ],
        "limitations": [
            "Potential-change regions are statistical indicators, not confirmed environmental events.",
            "No contemporaneous external land-cover, rainfall, soil-moisture, optical, or field evidence was verified.",
            "Only two observations are available for this comparison.",
        ],
        "area_summary": area_summary,
        "grid_validation": grid_validation,
        "context_status": context_status,
        "external_evidence": [
            {
                "source": "Copernicus Sentinel-2",
                "purpose": "Optical vegetation, water, and built-surface context",
                "status": "not_verified",
            },
            {
                "source": "NASA GPM IMERG",
                "purpose": "Coarse precipitation context",
                "status": "not_verified",
            },
            {
                "source": "NASA SMAP",
                "purpose": "Coarse soil-moisture context",
                "status": "not_verified",
            },
            {
                "source": "OpenStreetMap",
                "purpose": "Buildings, roads, and infrastructure context",
                "status": "not_verified",
            },
        ],
        "assets": {
            "hh_candidates": "/api/v1/nisar/assets/change_analysis/geospatial_interpretation/hh_candidate_change_regions_epsg32643.geojson",
            "hv_candidates": "/api/v1/nisar/assets/change_analysis/geospatial_interpretation/hv_candidate_change_regions_epsg32643.geojson",
            "hh_candidates_wgs84": "/api/v1/nisar/bengaluru/candidate-regions/HH",
            "hv_candidates_wgs84": "/api/v1/nisar/bengaluru/candidate-regions/HV",
            "hh_difference": "/api/v1/nisar/assets/change_analysis/figures/hh_difference_db.png",
            "hv_difference": "/api/v1/nisar/assets/change_analysis/figures/hv_difference_db.png",
            "hh_potential_change": "/api/v1/nisar/assets/change_analysis/figures/hh_potential_change.png",
            "hv_potential_change": "/api/v1/nisar/assets/change_analysis/figures/hv_potential_change.png",
            "hh_preview_20261029": "/api/v1/nisar/assets/previews/nisar_hh_20261029_preview.png",
            "hh_preview_20261110": "/api/v1/nisar/assets/previews/nisar_hh_20261110_preview.png",
            "hv_preview_20261029": "/api/v1/nisar/assets/previews/nisar_hv_20261029_preview.png",
            "hv_preview_20261110": "/api/v1/nisar/assets/previews/nisar_hv_20261110_preview.png",
        },
    }


@router.get("/bengaluru/candidate-regions/{polarization}", status_code=status.HTTP_200_OK)
async def get_bengaluru_candidate_regions(polarization: str):
    """Return candidate polygons transformed to WGS84 for web-map display."""
    normalized = polarization.upper()
    if normalized not in {"HH", "HV"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Polarization must be HH or HV.")

    source_path = CASE_STUDY_CONTEXT / f"{normalized.lower()}_candidate_change_regions_epsg32643.geojson"
    if not source_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate-region geometry is not available.")

    with source_path.open(encoding="utf-8") as handle:
        source = json.load(handle)
    transformed = {
        "type": "FeatureCollection",
        "features": [
            {
                **feature,
                "geometry": transform_geom("EPSG:32643", "EPSG:4326", feature["geometry"]),
            }
            for feature in source.get("features", [])
        ],
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
    }
    return transformed


@router.get("/search", status_code=status.HTTP_200_OK)
async def search_granules(
    min_lon: Optional[float] = Query(None, description="Minimum longitude"),
    min_lat: Optional[float] = Query(None, description="Minimum latitude"),
    max_lon: Optional[float] = Query(None, description="Maximum longitude"),
    max_lat: Optional[float] = Query(None, description="Maximum latitude"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    product_type: str = Query("GCOV", description="Product type (GCOV, GSLC, GUNW)"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search NASA/ISRO NISAR radar granule catalog by spatial extent and temporal window."""
    bbox = None
    if None not in (min_lon, min_lat, max_lon, max_lat):
        bbox = [min_lon, min_lat, max_lon, max_lat]

    results = search_nisar_granules(
        bbox=bbox,
        start_date=start_date,
        end_date=end_date,
        product_type=product_type,
        max_results=limit,
    )
    return results


@router.post("/validate", status_code=status.HTTP_200_OK)
async def validate_nisar_file(file: UploadFile = File(..., description="NISAR HDF5 data archive (.h5)")):
    """Validate a NISAR HDF5 product file and extract polarimetric & geospatial metadata."""
    file_path = None
    try:
        file_path, _ = await persist_upload(file, "nisar_upload")
        is_valid, err_msg, metadata = NISARValidator.validate_product(file_path)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"NISAR validation failed: {err_msg}")

        return {
            "status": "success",
            "is_valid": True,
            "metadata": metadata,
        }
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


@router.post("/preview", status_code=status.HTTP_200_OK)
async def preview_nisar_product(file: UploadFile = File(..., description="NISAR HDF5 data archive (.h5)")):
    """Render a false-color polarimetric RGB composite preview from a NISAR HDF5 product."""
    file_path = None
    try:
        file_path, _ = await persist_upload(file, "nisar_preview")
        is_valid, err_msg, metadata = NISARValidator.validate_product(file_path)
        if not is_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"NISAR validation failed: {err_msg}")

        _, b64_img = NISARProductReader.generate_preview_png(file_path)
        return {
            "status": "success",
            "metadata": metadata,
            "preview_png_b64": b64_img,
        }
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass


@router.post("/synthesize", status_code=status.HTTP_200_OK)
async def synthesize_nisar_demo(req: SynthesizeRequest):
    """Generate a realistic synthetic NISAR L2-GCOV HDF5 granule for demonstration & testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
    tmp_path = tmp.name
    tmp.close()

    try:
        NISARProductReader.create_synthetic_nisar_gcov(
            output_path=tmp_path,
            width=req.width,
            height=req.height,
            with_flood=req.with_flood,
            date_str=req.target_date,
        )
        _, _, metadata = NISARValidator.validate_product(tmp_path)
        _, b64_preview = NISARProductReader.generate_preview_png(tmp_path)

        return {
            "status": "success",
            "message": "Generated compliant NISAR L2-GCOV granule",
            "file_path": tmp_path,
            "metadata": metadata,
            "preview_b64": b64_preview,
        }
    except Exception as exc:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
