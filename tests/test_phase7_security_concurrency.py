"""Phase 7 Security, User Isolation, and Concurrency Test Suite."""
import asyncio
import io
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.main import app
from backend.api.auth import create_access_token
from backend.api.jobs import _jobs, create_job, get_job, list_user_jobs
from backend.config import settings

client = TestClient(app)


def create_dummy_png_bytes(width=100, height=100, color=(0, 255, 0)):
    """Generate in-memory valid PNG image bytes for testing."""
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color)
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def test_user_isolation():
    """Verify User A cannot access User B's jobs or results."""
    token_a = create_access_token({"sub": "user_a"})
    token_b = create_access_token({"sub": "user_b"})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Submit job as User A
    png_bytes = create_dummy_png_bytes()
    response_a = client.post(
        "/api/v1/jobs",
        files={"file_1": ("user_a_scene.png", png_bytes, "image/png")},
        data={"query": "User A scene analysis query"},
        headers=headers_a,
    )
    assert response_a.status_code == 202
    job_id_a = response_a.json()["job_id"]

    # User A should successfully retrieve their own job
    res_own = client.get(f"/api/v1/jobs/{job_id_a}", headers=headers_a)
    assert res_own.status_code == 200

    # User B attempting to access User A's job must receive 404 Not Found
    res_cross = client.get(f"/api/v1/jobs/{job_id_a}", headers=headers_b)
    assert res_cross.status_code == 404

    # Check user job listings isolation
    list_a = client.get("/api/v1/jobs", headers=headers_a).json()["jobs"]
    list_b = client.get("/api/v1/jobs", headers=headers_b).json()["jobs"]

    assert any(j["job_id"] == job_id_a for j in list_a)
    assert not any(j["job_id"] == job_id_a for j in list_b)


def test_upload_security_mime_and_corruption():
    """Verify invalid format, bad MIME, and corrupted files are rejected."""
    token = create_access_token({"sub": "security_tester"})
    headers = {"Authorization": f"Bearer {token}"}

    # Test 1: Bad extension
    bad_ext_res = client.post(
        "/api/v1/jobs",
        files={"file_1": ("malicious.exe", b"MZ...", "application/octet-stream")},
        data={"query": "Test query"},
        headers=headers,
    )
    assert bad_ext_res.status_code == 400
    assert "Unsupported format" in bad_ext_res.json()["detail"]

    # Test 2: Invalid MIME type
    bad_mime_res = client.post(
        "/api/v1/jobs",
        files={"file_1": ("fake_image.png", b"Not a real image header", "text/plain")},
        data={"query": "Test query"},
        headers=headers,
    )
    assert bad_mime_res.status_code == 400
    assert "Invalid MIME type" in bad_mime_res.json()["detail"]

    # Test 3: Corrupted raster data with image/png MIME
    corrupted_res = client.post(
        "/api/v1/jobs",
        files={"file_1": ("corrupt.png", b"Corrupted bytes sequence", "image/png")},
        data={"query": "Test query"},
        headers=headers,
    )
    assert corrupted_res.status_code == 400
    assert "failed raster validation" in corrupted_res.json()["detail"] or "Invalid or corrupted image" in corrupted_res.json()["detail"]


def test_no_path_leakage():
    """Verify internal absolute server filesystem paths are sanitized from public API responses."""
    token = create_access_token({"sub": "path_tester"})
    headers = {"Authorization": f"Bearer {token}"}

    png_bytes = create_dummy_png_bytes()
    response = client.post(
        "/api/v1/agent",
        files={"file_1": ("input_scene.png", png_bytes, "image/png")},
        data={"query": "Describe scene features"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()

    # file_1_path must be a basename or safe string, never containing absolute drives like C:\ or /home/
    file_path = data.get("file_1_path")
    if file_path:
        assert not file_path.startswith("C:\\")
        assert not file_path.startswith("/")
        assert "\\" not in file_path and "/" not in file_path


def test_concurrency_queue_limit():
    """Verify capacity limit enforcement returns 429 Too Many Requests when queue is full."""
    token = create_access_token({"sub": "queue_tester"})
    headers = {"Authorization": f"Bearer {token}"}

    # Simulate filled queue by setting active jobs to max
    original_max = settings.MAX_QUEUED_JOBS
    settings.MAX_QUEUED_JOBS = 1

    try:
        # Fill queue
        dummy_job_id = "test_queue_fill_id"
        _jobs[dummy_job_id] = {"job_id": dummy_job_id, "owner": "queue_tester", "status": "QUEUED"}

        png_bytes = create_dummy_png_bytes()
        res_busy = client.post(
            "/api/v1/jobs",
            files={"file_1": ("test.png", png_bytes, "image/png")},
            data={"query": "Test queue limit"},
            headers=headers,
        )
        assert res_busy.status_code == 429
        assert "capacity limit reached" in res_busy.json()["detail"].lower()
    finally:
        settings.MAX_QUEUED_JOBS = original_max
        _jobs.pop("test_queue_fill_id", None)
