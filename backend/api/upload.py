"""Shared bounded temporary-upload handling for API routes."""
import os
import uuid

from fastapi import HTTPException, UploadFile, status

from backend.config import settings
from backend.validation.validator import InputValidator


async def persist_upload(upload: UploadFile, label: str) -> str:
    extension = os.path.splitext(upload.filename or "")[1].lower()
    if extension not in InputValidator.SUPPORTED_FORMATS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported upload format.")
    path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4()}_{label}{extension}")
    total = 0
    try:
        with open(path, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > settings.MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Uploaded file exceeds the configured size limit.")
                output.write(chunk)
        return path
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
