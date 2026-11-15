"""Focused tests for the generalized real-product NISAR processing contract."""
from __future__ import annotations

import os
import tempfile
import time

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.preprocessing.nisar_reader import NISARProductReader


@pytest.fixture
def real_product_pair():
    directory = tempfile.mkdtemp(prefix="terrapulse_nisar_api_")
    first = os.path.join(directory, "NISAR_L2_GCOV_20261029.h5")
    second = os.path.join(directory, "NISAR_L2_GCOV_20261110.h5")
    NISARProductReader.create_synthetic_nisar_gcov(first, width=64, height=64, date_str="2026-10-29")
    NISARProductReader.create_synthetic_nisar_gcov(second, width=64, height=64, with_flood=True, date_str="2026-11-10")
    yield first, second
    for path in (first, second):
        if os.path.exists(path):
            os.remove(path)
    os.rmdir(directory)


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    for _ in range(80):
        response = client.get(f"/api/v1/nisar/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"completed", "failed"}:
            return job
        time.sleep(0.05)
    raise AssertionError("NISAR job did not finish within the test timeout.")


def test_process_contract_validates_polarization_and_queues_job(real_product_pair):
    first, second = real_product_pair
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/nisar/process",
            json={
                "observation_1": first,
                "observation_2": second,
                "product_type": "L2-GCOV",
                "polarizations": ["HH"],
                "analysis_type": "change",
            },
        )
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["job_id"])
        assert job["status"] == "completed", job
        result = client.get(f"/api/v1/nisar/jobs/{job['job_id']}/results")
        assert result.status_code == 200
        payload = result.json()["result"]
        assert payload["processing"]["polarizations"] == ["HHHH"]
        assert payload["processing"]["evidence"]["scientific_status"] == "candidate_radar_backscatter_anomaly"


def test_process_contract_rejects_unsupported_product_and_hides_unknown_jobs():
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/nisar/process",
            json={
                "observation_1": "missing-1.h5",
                "observation_2": "missing-2.h5",
                "product_type": "GUNW",
            },
        )
        assert response.status_code == 422
        assert client.get("/api/v1/nisar/jobs/not-a-job").status_code == 404
