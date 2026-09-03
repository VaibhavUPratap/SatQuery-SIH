"""In-process thread-safe job coordinator with user isolation and resource queue management."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
import os
import shutil
import threading
import uuid
from typing import Any

from backend.agent.graph import agent_graph
from backend.agent.state import AgentState
from backend.config import settings

logger = logging.getLogger("satquery.jobs")

MAX_CONCURRENT_JOBS = int(os.getenv("SATQUERY_MAX_CONCURRENT_JOBS", "2"))
_executor = ThreadPoolExecutor(max_workers=max(1, MAX_CONCURRENT_JOBS))
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(
    owner: str,
    paths: list[str],
    query: str,
    include_report: bool,
    analysis_type: str = "auto",
    job_id: str | None = None,
    job_dir: str | None = None,
) -> str:
    job_uuid = job_id or str(uuid.uuid4())
    with _lock:
        active = sum(job["status"] in {"QUEUED", "PROCESSING"} for job in _jobs.values())
        if active >= settings.MAX_QUEUED_JOBS:
            logger.warning("Job creation rejected: queue capacity full (%d active/queued).", active)
            return ""
        _jobs[job_uuid] = {
            "job_id": job_uuid,
            "owner": owner,
            "status": "QUEUED",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    _executor.submit(_run_job, job_uuid, owner, paths, query, include_report, analysis_type, job_dir)
    return job_uuid


def sanitize_result_paths(obj: Any) -> Any:
    """Removes server absolute filesystem paths from result objects to prevent path disclosure."""
    if isinstance(obj, dict):
        sanitized = {}
        for k, v in obj.items():
            if k in {"file_1_path", "file_2_path", "image_path", "optical_path", "sar_path"} and isinstance(v, str):
                sanitized[k] = os.path.basename(v)
            else:
                sanitized[k] = sanitize_result_paths(v)
        return sanitized
    elif isinstance(obj, list):
        return [sanitize_result_paths(item) for item in obj]
    return obj


def _run_job(
    job_id: str,
    owner: str,
    paths: list[str],
    query: str,
    include_report: bool,
    analysis_type: str = "auto",
    job_dir: str | None = None,
) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id]["status"] = "PROCESSING"
    try:
        state: AgentState = {
            "query": query,
            "image_count": len(paths),
            "requested_task": analysis_type,
            "file_1_path": paths[0],
            "file_2_path": paths[1] if len(paths) > 1 else None,
            "include_report": include_report,
            "thread_id": job_id,
        }
        raw_result = agent_graph.invoke(state, config={"configurable": {"thread_id": job_id}}).get("final_output", {})
        result = sanitize_result_paths(raw_result)
        result["job_id"] = job_id

        with _lock:
            if job_id in _jobs:
                status_str = "COMPLETED" if result.get("status") == "success" else "FAILED"
                _jobs[job_id].update({"status": status_str, "result": result})
    except Exception as exc:
        logger.exception("Error executing job %s", job_id)
        with _lock:
            if job_id in _jobs:
                _jobs[job_id].update({"status": "FAILED", "error": "Analysis job failed."})
    finally:
        # Mandatory temporary file & isolated directory cleanup
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        if job_dir and os.path.exists(job_dir):
            shutil.rmtree(job_dir, ignore_errors=True)
        elif paths:
            parent_dir = os.path.dirname(paths[0])
            if os.path.basename(parent_dir).startswith("job_") and os.path.exists(parent_dir):
                shutil.rmtree(parent_dir, ignore_errors=True)


def get_job(job_id: str, owner: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["owner"] != owner:
            return None
        return dict(job)


def list_user_jobs(owner: str) -> list[dict[str, Any]]:
    with _lock:
        user_jobs = [dict(j) for j in _jobs.values() if j.get("owner") == owner]
        for j in user_jobs:
            j.pop("owner", None)
        return user_jobs
