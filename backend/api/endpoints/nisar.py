"""FastAPI endpoints for NASA-ISRO NISAR radar products."""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from backend.api.upload import persist_upload
from backend.preprocessing.nisar_reader import NISARProductReader
from backend.preprocessing.nisar_search import search_nisar_granules
from backend.validation.nisar_validator import NISARValidator

logger = logging.getLogger("terrapulse.api.nisar")
router = APIRouter(prefix="/nisar", tags=["NISAR Earth Observation"])


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
