import os
import shutil
import uuid
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from backend.api.auth import current_user
from backend.api.jobs import create_job, get_job, list_user_jobs
from backend.api.upload import persist_upload

router = APIRouter()


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    file_1: UploadFile = File(...),
    file_2: UploadFile | None = File(None),
    query: str = Form(...),
    analysis_type: str = Form("auto"),
    include_report: bool = Form(False),
    owner: str = Depends(current_user),
):
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    
    job_id = str(uuid.uuid4())
    paths: list[str] = []
    job_dir: str | None = None
    
    try:
        path_1, job_dir = await persist_upload(file_1, "primary", job_id=job_id)
        paths.append(path_1)
        
        if file_2:
            path_2, _ = await persist_upload(file_2, "secondary", job_id=job_id)
            paths.append(path_2)

        created_id = create_job(
            owner=owner,
            paths=paths,
            query=query,
            include_report=include_report,
            analysis_type=analysis_type,
            job_id=job_id,
            job_dir=job_dir,
        )
        if not created_id:
            # Capacity full: clean up isolated directory
            if job_dir and os.path.exists(job_dir):
                shutil.rmtree(job_dir, ignore_errors=True)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Analysis capacity limit reached. Please try again shortly.",
            )
        return {"job_id": job_id, "status": "QUEUED"}
    except Exception:
        if job_dir and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        raise


@router.get("/jobs")
def list_jobs(owner: str = Depends(current_user)):
    """List all active and completed jobs belonging strictly to the authenticated user."""
    return {"jobs": list_user_jobs(owner)}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, owner: str = Depends(current_user)):
    """Retrieve details for a job owned by the authenticated user."""
    job = get_job(job_id, owner)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.pop("owner", None)
    return job
