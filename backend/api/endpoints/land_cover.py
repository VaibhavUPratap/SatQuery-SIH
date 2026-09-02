"""HTTP endpoint for BigEarthNet v2.0 multi-label land-cover classification."""

import logging
import os

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from backend.agent.tool_registry import tool_registry
from backend.config import settings
from backend.validation.validator import InputValidator
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.land_cover")
router = APIRouter()


@router.post("/land-cover", status_code=status.HTTP_200_OK)
async def classify_land_cover(file: UploadFile = File(..., description="14-band Sentinel-1/Sentinel-2 GeoTIFF")):
    """Classify a reBEN-compatible Sentinel-1/Sentinel-2 image chip."""
    path = None
    try:
        path = await persist_upload(file, "land_cover")
        valid, error, metadata = InputValidator.validate_image(path)
        if not valid:
            raise HTTPException(status_code=400, detail=f"Image validation failed: {error}")
        if metadata.get("bands") != settings.BIGEARTHNET_EXPECTED_BANDS:
            raise HTTPException(status_code=422, detail=(
                f"BigEarthNet requires a {settings.BIGEARTHNET_EXPECTED_BANDS}-band Sentinel-2 GeoTIFF; "
                f"received {metadata.get('bands')} band(s). RGB images are not supported."
            ))
        tool = tool_registry.get_tool("land_cover")
        if not tool:
            raise HTTPException(status_code=503, detail="BigEarthNet land-cover specialist is not registered.")
        result = tool.run({"image_path": path})
        result["status"] = "success"
        result["evidence"]["image_metadata"] = metadata
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        logger.warning("BigEarthNet input rejected: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        logger.warning("BigEarthNet inference rejected: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("BigEarthNet inference failed")
        raise HTTPException(status_code=500, detail=f"Land-cover classification failed: {exc}") from exc
    finally:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                logger.warning("Failed to remove temporary file %s", path)
