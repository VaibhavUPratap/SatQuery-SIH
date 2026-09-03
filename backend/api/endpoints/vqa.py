import os
import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from backend.config import settings
from backend.validation.validator import InputValidator
from backend.agent.tool_registry import tool_registry
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.vqa")
router = APIRouter()

@router.post("/vqa", status_code=status.HTTP_200_OK)
async def execute_vqa(
    file: UploadFile = File(..., description="Satellite image (GeoTIFF/TIFF, PNG, JPEG)"),
    question: str = Form(..., description="Natural language question about the image")
):
    """
    Upload a satellite image and submit a question.
    The query will be routed to the specialist Remote Sensing VQA tool.
    """
    if not question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question query parameter cannot be empty."
        )

    # Save uploaded file temporarily with a unique name
    file_path = None
    try:
        file_path = await persist_upload(file, "vqa")
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
        # Clean up invalid file
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        logger.warning(f"Validation failed for upload {file.filename}: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image validation failed: {error_msg}"
        )

    # Fetch tool from registry
    vqa_tool = tool_registry.get_tool("vqa")
    if not vqa_tool:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="VQA specialist tool is not registered in the system registry."
        )

    try:
        # Run tool
        result = vqa_tool.run({
            "image_path": file_path,
            "question": question
        })
        
        # Inject metadata into evidence
        result["evidence"]["image_metadata"] = metadata
        result["query"] = question
        result["status"] = "success"
        
        return result
        
    except ValueError as e:
        logger.warning(f"VQA input is incompatible with the model: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error during VQA execution: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(e)}"
        )
    finally:
        # Optional: delete file after run to prevent storage build up
        # For trace/evidence purposes, in a full app we'd keep it or upload to storage.
        # Let's delete it here to keep local run clean.
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as cleanup_err:
                logger.warning(f"Failed to delete temporary file {file_path}: {str(cleanup_err)}")
