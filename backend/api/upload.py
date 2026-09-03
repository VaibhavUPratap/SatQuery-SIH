"""Shared bounded temporary-upload handling for API routes with strict security checks."""
import os
import shutil
import uuid
from typing import Tuple

from fastapi import HTTPException, UploadFile, status

from backend.config import settings
from backend.validation.validator import InputValidator

ALLOWED_MIME_TYPES = {
    "image/tiff",
    "image/x-tiff",
    "image/geotiff",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/octet-stream",
}


async def persist_upload(upload: UploadFile, label: str, job_id: str | None = None) -> Tuple[str, str]:
    """
    Persists an uploaded raster to an isolated, unguessable temporary job directory.
    Validates MIME type, extension, size limits, and raster integrity.
    
    Returns:
        Tuple of (file_path, job_dir)
    """
    filename = upload.filename or ""
    extension = os.path.splitext(filename)[1].lower()
    
    # 1. Format Extension Check
    if extension not in InputValidator.SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{extension}'. Allowed extensions: {', '.join(InputValidator.SUPPORTED_FORMATS)}"
        )
    
    # 2. MIME Type Validation
    content_type = (upload.content_type or "").lower()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type '{content_type}' for remote sensing raster."
        )

    # 3. Create Unguessable Isolated Job Directory: uploads/job_<UUID>/
    dir_id = job_id or str(uuid.uuid4())
    job_dir = os.path.join(settings.UPLOAD_DIR, f"job_{dir_id}")
    os.makedirs(job_dir, exist_ok=True)
    
    # 4. Generate Unpredictable Filename
    file_path = os.path.join(job_dir, f"{uuid.uuid4()}_{label}{extension}")
    
    total_bytes = 0
    try:
        # 5. Stream write with file size limit check
        with open(file_path, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Uploaded file exceeds the maximum size limit of {settings.MAX_UPLOAD_BYTES // (1024*1024)} MB."
                    )
                output.write(chunk)
        
        # 6. Immediate Raster Integrity & Corruption Check
        is_valid, err_msg, _ = InputValidator.validate_image(file_path)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file failed raster validation: {err_msg}"
            )

        return file_path, job_dir
    except Exception:
        # Clean up temporary directory on failure
        if os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        raise

