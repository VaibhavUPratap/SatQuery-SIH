"""Comprehensive test suite for Optical and SAR data uploads and pairing verification."""
import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient
from PIL import Image
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.api.main import app
from backend.validation.validator import InputValidator
from backend.preprocessing.registration import ImageRegistration
from backend.config import settings

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OPTICAL_SAMPLE = os.path.join(ROOT, "samples", "optical", "sentinel2_lake_suburb_optical.png")
SAR_SAMPLE = os.path.join(ROOT, "samples", "sar", "sentinel1_coastal_port_sar.png")
PAIR_OPT = os.path.join(ROOT, "samples", "optical_sar", "pair1_coastal_port_sentinel2_optical.png")
PAIR_SAR = os.path.join(ROOT, "samples", "optical_sar", "pair1_coastal_port_sentinel1_sar.png")
S2_12BAND = os.path.join(ROOT, "samples", "optical", "sentinel2_12band_multispectral.tif")


def test_validator_detects_optical_sensor():
    """Verify that InputValidator identifies Sentinel-2 Optical metadata."""
    valid, err, meta = InputValidator.validate_image(OPTICAL_SAMPLE)
    assert valid is True
    assert meta["sensor"] == "Sentinel-2 MSI"
    assert "Optical" in meta["modality"]
    assert meta["bands"] == 3


def test_validator_detects_sar_sensor():
    """Verify that InputValidator identifies Sentinel-1 SAR metadata and polarization."""
    valid, err, meta = InputValidator.validate_image(SAR_SAMPLE)
    assert valid is True
    assert "Sentinel-1" in meta["sensor"] or "SAR" in meta["sensor"]
    assert meta["modality"] == "SAR"
    assert "polarization" in meta


def test_optical_only_upload_vqa_and_agent():
    """Test single optical image workflow via API."""
    with TestClient(app) as client, open(OPTICAL_SAMPLE, "rb") as f:
        res = client.post(
            "/api/v1/agent",
            files={"file_1": ("sentinel2_lake_suburb_optical.png", f, "image/png")},
            data={"query": "Is there a river or water body present?", "analysis_type": "vqa"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["route"]["task"] == "vqa"
    assert "answer" in data


def test_sar_only_upload_agent():
    """Test single SAR image upload workflow."""
    with TestClient(app) as client, open(SAR_SAMPLE, "rb") as f:
        res = client.post(
            "/api/v1/agent",
            files={"file_1": ("sentinel1_coastal_port_sar.png", f, "image/png")},
            data={"query": "Describe the radar backscatter intensity and structures", "analysis_type": "caption"},
        )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["route"]["task"] == "caption"


def test_optical_and_sar_paired_upload_success():
    """Test co-registered Optical + SAR dual upload via /api/v1/optical-sar."""
    with TestClient(app) as client:
        with open(PAIR_OPT, "rb") as f_opt, open(PAIR_SAR, "rb") as f_sar:
            res = client.post(
                "/api/v1/optical-sar",
                files={
                    "optical_file": ("coastal_optical.png", f_opt, "image/png"),
                    "sar_file": ("coastal_sar.png", f_sar, "image/png"),
                },
                data={"query": "Identify water and built-up areas using both optical and SAR."},
            )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert "class_coverage" in data
    assert "water" in data["class_coverage"]
    assert "built_up" in data["class_coverage"]
    assert data["evidence"]["coregistration"]["spatial_alignment"] == "Co-registered"


def test_optical_and_sar_missing_sar_error():
    """Test optical-sar endpoint with missing SAR file raises 422."""
    with TestClient(app) as client:
        with open(PAIR_OPT, "rb") as f_opt:
            res = client.post(
                "/api/v1/optical-sar",
                files={"optical_file": ("optical.png", f_opt, "image/png")},
                data={"query": "Identify features"},
            )
    assert res.status_code == 422  # Missing required multipart field


def test_optical_and_sar_missing_optical_error():
    """Test optical-sar endpoint with missing optical file raises 422."""
    with TestClient(app) as client:
        with open(PAIR_SAR, "rb") as f_sar:
            res = client.post(
                "/api/v1/optical-sar",
                files={"sar_file": ("sar.png", f_sar, "image/png")},
                data={"query": "Identify features"},
            )
    assert res.status_code == 422


def test_incompatible_spatial_dimensions_rejection():
    """Verify that images with mismatched dimensions return 'Optical and SAR inputs are not spatially compatible.'"""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_mismatch:
        arr_mismatch = np.zeros((200, 300, 3), dtype=np.uint8)
        Image.fromarray(arr_mismatch).save(f_mismatch.name)
        mismatch_path = f_mismatch.name

    try:
        with TestClient(app) as client:
            with open(PAIR_OPT, "rb") as f_opt, open(mismatch_path, "rb") as f_bad_sar:
                res = client.post(
                    "/api/v1/optical-sar",
                    files={
                        "optical_file": ("optical.png", f_opt, "image/png"),
                        "sar_file": ("bad_sar.png", f_bad_sar, "image/png"),
                    },
                    data={"query": "Fuse optical and SAR"},
                )
            assert res.status_code == 400
            data = res.json()
            assert "Optical and SAR inputs are not spatially compatible." in data["detail"]
    finally:
        if os.path.exists(mismatch_path):
            os.remove(mismatch_path)


def test_invalid_corrupted_file_rejection():
    """Verify that a corrupted image file is rejected with HTTP 400."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_corrupt:
        f_corrupt.write(b"CORRUPTED_DATA_HEADER_NOT_A_REAL_IMAGE")
        corrupt_path = f_corrupt.name

    try:
        with TestClient(app) as client:
            with open(corrupt_path, "rb") as f:
                res = client.post(
                    "/api/v1/vqa",
                    files={"file": ("corrupt.png", f, "image/png")},
                    data={"question": "What is this?"},
                )
            assert res.status_code == 400
            assert "validation failed" in res.json()["detail"].lower()
    finally:
        if os.path.exists(corrupt_path):
            os.remove(corrupt_path)


def test_unsupported_file_extension_rejection():
    """Verify that unsupported extensions (.txt, .exe, .csv) are rejected with HTTP 400."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f_txt:
        f_txt.write(b"plain text file")
        txt_path = f_txt.name

    try:
        with TestClient(app) as client:
            with open(txt_path, "rb") as f:
                res = client.post(
                    "/api/v1/vqa",
                    files={"file": ("data.txt", f, "text/plain")},
                    data={"question": "What is this?"},
                )
            assert res.status_code == 400
            assert "Unsupported upload format" in res.json()["detail"]
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)


def test_bigearthnet_rejects_rgb():
    """Verify that BigEarthNet /api/v1/land-cover strictly rejects 3-band RGB imagery."""
    with TestClient(app) as client:
        with open(OPTICAL_SAMPLE, "rb") as f_rgb:
            res = client.post(
                "/api/v1/land-cover",
                files={"file": ("rgb.png", f_rgb, "image/png")},
            )
        assert res.status_code == 422
        assert "BigEarthNet requires a 12-band Sentinel-2 GeoTIFF" in res.json()["detail"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
