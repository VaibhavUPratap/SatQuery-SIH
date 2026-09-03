from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.api.auth import current_user
from backend.api.jobs import create_job, get_job
from backend.api.upload import persist_upload

router = APIRouter()


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    file_1: UploadFile = File(...),
    file_2: UploadFile | None = File(None),
    query: str = Form(...),
    include_report: bool = Form(False),
    owner: str = Depends(current_user),
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    paths: list[str] = []
    try:
        paths.append(await persist_upload(file_1, "job_1"))
        if file_2:
            paths.append(await persist_upload(file_2, "job_2"))
        job_id = create_job(owner, paths, query, include_report)
        if not job_id:
            raise HTTPException(status_code=429, detail="Analysis capacity is full. Please try again shortly.")
        return {"job_id": job_id, "status": "QUEUED"}
    except Exception:
        for path in paths:
            import os
            if os.path.exists(path):
                os.remove(path)
        raise


@router.get("/jobs/{job_id}")
def job_status(job_id: str, owner: str = Depends(current_user)):
    job = get_job(job_id, owner)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.pop("owner", None)
    return job
