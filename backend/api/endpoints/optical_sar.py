import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.agent.tool_registry import tool_registry
from backend.config import settings
from backend.preprocessing.registration import ImageRegistration
from backend.validation.validator import InputValidator
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.optical_sar")
router = APIRouter()


@router.post("/optical-sar", status_code=status.HTTP_200_OK)
async def execute_optical_sar(
    optical_file: UploadFile = File(..., description="Co-registered optical or multispectral image"),
    sar_file: UploadFile = File(..., description="Co-registered SAR intensity image"),
    query: str = Form("Identify water-covered and built-up regions."),
):
    """Fuse a co-registered optical/SAR pair into water and built-up evidence."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    paths = []
    try:
        optical_path = await persist_upload(optical_file, "optical")
        paths.append(optical_path)
        sar_path = await persist_upload(sar_file, "sar")
        paths.append(sar_path)
        optical_ok, optical_error, optical_metadata = InputValidator.validate_image(optical_path)
        sar_ok, sar_error, sar_metadata = InputValidator.validate_image(sar_path)
        if not optical_ok or not sar_ok:
            error = optical_error if not optical_ok else sar_error
            raise HTTPException(status_code=400, detail=f"Image validation failed: {error}")
        compatible, pair_error, pair_metadata = ImageRegistration.validate_optical_sar_pair(optical_path, sar_path)
        if not compatible:
            raise HTTPException(status_code=400, detail=f"Optical-SAR validation failed: {pair_error}")
        tool = tool_registry.get_tool("optical_sar")
        if not tool:
            raise HTTPException(status_code=503, detail="Optical-SAR fusion tool is not registered.")
        result = tool.run({"optical_path": optical_path, "sar_path": sar_path, "query": query})
        result["status"] = "success"
        result["evidence"]["optical_metadata"] = optical_metadata
        result["evidence"]["sar_metadata"] = sar_metadata
        result["evidence"]["coregistration"] = pair_metadata
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Optical-SAR fusion failed")
        raise HTTPException(status_code=500, detail=f"Optical-SAR fusion failed: {exc}") from exc
    finally:
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as cleanup_error:
                    logger.warning("Failed to remove temporary file %s: %s", path, cleanup_error)
