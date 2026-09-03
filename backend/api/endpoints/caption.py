import os
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from backend.config import settings
from backend.validation.validator import InputValidator
from backend.agent.tool_registry import tool_registry
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.caption")
router = APIRouter()

@router.post("/caption", status_code=status.HTTP_200_OK)
async def execute_caption(
    file: UploadFile = File(..., description="Satellite image to describe (GeoTIFF/TIFF, PNG, JPEG)")
):
    """
    Upload a satellite image and generate a natural language description/caption of the scene.
    """
    file_path = None
    try:
        file_path = await persist_upload(file, "caption")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to write uploaded file: {str(e)}")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write uploaded file: {str(e)}"
        )

    # Validate image file
    is_valid, error_msg, metadata = InputValidator.validate_image(file_path)
    if not is_valid:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation failed: {error_msg}"
        )

    # Fetch tool
    caption_tool = tool_registry.get_tool("caption")
    if not caption_tool:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Caption specialist tool is not registered."
        )

    try:
        result = caption_tool.run({
            "image_path": file_path
        })
        result["evidence"]["image_metadata"] = metadata
        result["status"] = "success"
        return result
    except ValueError as e:
        logger.warning(f"Caption input rejected: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error during Caption execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(e)}"
        )
    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temporary file {file_path}: {str(cleanup_err)}")
