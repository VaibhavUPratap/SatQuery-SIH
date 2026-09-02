"""Small in-process job coordinator for prototype concurrent analysis."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
import threading
import uuid
from typing import Any

from backend.agent.graph import agent_graph
from backend.agent.state import AgentState
from backend.config import settings

MAX_CONCURRENT_JOBS = int(os.getenv("SATQUERY_MAX_CONCURRENT_JOBS", "2"))
_executor = ThreadPoolExecutor(max_workers=max(1, MAX_CONCURRENT_JOBS))
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def create_job(owner: str, paths: list[str], query: str, include_report: bool) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        active = sum(job["status"] in {"QUEUED", "PROCESSING"} for job in _jobs.values())
        if active >= settings.MAX_QUEUED_JOBS:
            return ""
        _jobs[job_id] = {"job_id": job_id, "owner": owner, "status": "QUEUED", "created_at": datetime.now(timezone.utc).isoformat()}
    _executor.submit(_run_job, job_id, owner, paths, query, include_report)
    return job_id


def _run_job(job_id: str, owner: str, paths: list[str], query: str, include_report: bool) -> None:
    with _lock:
        _jobs[job_id]["status"] = "PROCESSING"
    try:
        state: AgentState = {"query": query, "image_count": len(paths), "requested_task": "auto", "file_1_path": paths[0], "file_2_path": paths[1] if len(paths) > 1 else None, "include_report": include_report, "thread_id": job_id}
        result = agent_graph.invoke(state, config={"configurable": {"thread_id": job_id}}).get("final_output", {})
        result["job_id"] = job_id
        with _lock:
            _jobs[job_id].update({"status": "COMPLETED" if result.get("status") == "success" else "FAILED", "result": result})
    except Exception:
        with _lock:
            _jobs[job_id].update({"status": "FAILED", "error": "Analysis job failed."})
    finally:
        for path in paths:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass


def get_job(job_id: str, owner: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["owner"] != owner:
            return None
        return dict(job)
