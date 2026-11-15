"""Owned asynchronous job coordinator for generalized NISAR processing."""
from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from backend.agent.graph import agent_graph
from backend.config import settings
from backend.services.nisar_processing import NISARProcessRequest, NISARProcessingService

logger = logging.getLogger("terrapulse.api.nisar_jobs")
_executor = ThreadPoolExecutor(max_workers=settings.MAX_CONCURRENT_JOBS)
_jobs: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()
_service = NISARProcessingService()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_nisar_job(request: NISARProcessRequest, owner: str) -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        active_jobs = sum(job["status"] in {"queued", "validating", "preprocessing", "analysing", "generating_evidence"} for job in _jobs.values())
        if active_jobs >= settings.MAX_QUEUED_JOBS:
            raise RuntimeError("NISAR processing queue is full; retry later.")
        _jobs[job_id] = {
            "job_id": job_id,
            "owner": owner,
            "status": "queued",
            "progress": 0,
            "created_at": _now(),
            "updated_at": _now(),
            "trace": [],
            "request": request.model_dump(exclude={"parameters"}),
        }
    _executor.submit(_run_nisar_job, job_id, request)
    return job_id


def _update(job_id: str, **values: Any) -> None:
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(values, updated_at=_now())


def _run_nisar_job(job_id: str, request: NISARProcessRequest) -> None:
    try:
        _update(job_id, status="validating", progress=15, trace=[{"node": "resolve_and_validate", "status": "running"}])
        _update(job_id, status="preprocessing", progress=35, trace=[{"node": "resolve_and_validate", "status": "passed"}, {"node": "preprocess_aoi", "status": "running"}])
        service_result = _service.process(request)
        _update(job_id, status="analysing", progress=60, trace=[{"node": "resolve_and_validate", "status": "passed"}, {"node": "preprocess_aoi", "status": "passed"}, {"node": "specialist_analysis", "status": "running"}])

        # Re-run through the existing typed StateGraph so the job has the same
        # routing, specialist, evidence, and report semantics as other analyses.
        path_1 = _service.resolve_observation(request.observation_1)
        path_2 = _service.resolve_observation(request.observation_2)
        graph_result = agent_graph.invoke(
            {
                "query": (
                    "Analyze NISAR flood inundation candidate evidence and preserve "
                    "candidate-anomaly limitations."
                    if request.analysis_type == "flood"
                    else "Analyze NISAR radar backscatter change and preserve candidate-anomaly limitations."
                ),
                "image_count": 2,
                "requested_task": "nisar_flood" if request.analysis_type == "flood" else "nisar_change",
                "file_1_path": str(path_1),
                "file_2_path": str(path_2),
                "include_report": True,
                "thread_id": job_id,
                "nisar_processing_result": service_result,
                "allow_large_nisar_grid": True,
            },
            config={"configurable": {"thread_id": job_id}},
        )
        output = graph_result.get("final_output") or {}
        if output.get("status") != "success":
            raise RuntimeError(output.get("detail", "NISAR LangGraph processing failed."))
        _update(
            job_id,
            status="generating_evidence",
            progress=85,
            result={"processing": service_result, "agent": output},
            trace=output.get("execution_trace", {}).get("steps", []),
        )
        _update(job_id, status="completed", progress=100, completed_at=_now())
    except Exception as exc:
        logger.exception("NISAR job %s failed", job_id)
        _update(job_id, status="failed", progress=100, error=str(exc), failed_at=_now())


def get_nisar_job(job_id: str, owner: str) -> dict[str, Any] | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["owner"] != owner:
            return None
        result = dict(job)
        result.pop("owner", None)
        result.pop("request", None)
        return result
