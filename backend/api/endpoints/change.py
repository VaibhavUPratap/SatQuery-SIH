import logging
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from backend.agent.tool_registry import tool_registry
from backend.config import settings
from backend.preprocessing.registration import ImageRegistration
from backend.validation.validator import InputValidator
from backend.api.upload import persist_upload

logger = logging.getLogger("satquery.api.change")
router = APIRouter()


@router.post("/change", status_code=status.HTTP_200_OK)
async def execute_change(
    file_t1: UploadFile = File(..., description="Earlier satellite image (T1)"),
    file_t2: UploadFile = File(..., description="Later satellite image (T2)"),
    question: str = Form(
        "What changed between the two images?",
        description="Optional question about the temporal change.",
    ),
):
    """Detect bi-temporal change and answer a grounded question about it."""
    if not question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    paths = []
    try:
        path_t1 = await persist_upload(file_t1, "change_t1")
        paths.append(path_t1)
        path_t2 = await persist_upload(file_t2, "change_t2")
        paths.append(path_t2)

        valid_t1, error_t1, metadata_t1 = InputValidator.validate_image(path_t1)
        valid_t2, error_t2, metadata_t2 = InputValidator.validate_image(path_t2)
        if not valid_t1 or not valid_t2:
            detail = error_t1 if not valid_t1 else error_t2
            raise HTTPException(status_code=400, detail=f"Image validation failed: {detail}")

        pair_valid, pair_error, pair_metadata = ImageRegistration.validate_pair(path_t1, path_t2)
        if not pair_valid:
            raise HTTPException(status_code=400, detail=f"Image pair validation failed: {pair_error}")

        detection_tool = tool_registry.get_tool("change_detection")
        vqa_tool = tool_registry.get_tool("change_vqa")
        if not detection_tool or not vqa_tool:
            raise HTTPException(status_code=503, detail="Change specialist tools are not registered.")

        model_inputs = {"image_path_a": path_t1, "image_path_b": path_t2}
        detection = detection_tool.run(model_inputs)
        answer = vqa_tool.run({**model_inputs, "question": question})

        return {
            "status": "success",
            "query": question,
            "answer": answer["answer"],
            "confidence": answer["confidence"],
            "change_summary": detection["change_summary"],
            "change_ratio": detection["change_ratio"],
            "changed_pixels": detection["changed_pixels"],
            "total_pixels": detection["total_pixels"],
            "change_map_b64": detection["change_map_b64"],
            "evidence": {
                "image_t1_metadata": metadata_t1,
                "image_t2_metadata": metadata_t2,
                "registration": pair_metadata,
                "change_detection": detection["evidence"],
                "change_vqa": answer["evidence"],
            },
            "execution_trace": {
                "task": "Bi-temporal Change Analysis",
                "steps": [detection["execution_trace"], answer["execution_trace"]],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error during change analysis")
        raise HTTPException(status_code=500, detail=f"Change analysis failed: {exc}") from exc
    finally:
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as cleanup_error:
                    logger.warning("Failed to remove temporary file %s: %s", path, cleanup_error)
