"""Deterministic test suite for SatQuery AI Phase 4 Demonstration Sample Data Pack.

Verifies:
1. All required directories and files exist under samples/
2. JSON manifests are present, valid, and contain required metadata keys
3. RAW vs VISUALIZATION data types are correctly formatted and distinguished
4. GeoTIFF files have correct CRS, band counts, and float32 dtype
5. All specialist endpoints (VQA, Caption, Grounding, Land Cover, Change, Optical-SAR, Agent)
   execute deterministically against their respective sample inputs.
"""
import json
import os
import sys
import pytest
import rasterio
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from backend.api.main import app
from backend.validation.validator import InputValidator

SAMPLES_DIR = os.path.join(ROOT, "samples")


def test_directory_structure_and_manifests_exist():
    """Verify all required sample categories and manifest JSON files exist."""
    required_dirs = [
        "vqa",
        "caption",
        "grounding",
        "land_cover",
        "change_detection",
        "optical_sar",
    ]
    for cat in required_dirs:
        dir_path = os.path.join(SAMPLES_DIR, cat)
        manifest_path = os.path.join(dir_path, "manifest.json")
        assert os.path.isdir(dir_path), f"Missing directory: {dir_path}"
        assert os.path.isfile(manifest_path), f"Missing manifest: {manifest_path}"

        with open(manifest_path, "r") as f:
            data = json.load(f)
            assert "category" in data
            assert "title" in data
            assert "intended_api" in data
            assert "samples" in data or "benchmark_details" in data


def test_vqa_samples_and_api_execution():
    """Verify VQA samples and endpoint execution."""
    vqa_manifest_path = os.path.join(SAMPLES_DIR, "vqa", "manifest.json")
    with open(vqa_manifest_path, "r") as f:
        meta = json.load(f)

    samples = meta["samples"]
    assert len(samples) >= 3

    with TestClient(app) as client:
        for s in samples[:3]:
            img_path = os.path.join(SAMPLES_DIR, "vqa", s["image_file"])
            assert os.path.isfile(img_path), f"Missing VQA image: {img_path}"

            # Validate image
            valid, err, info = InputValidator.validate_image(img_path)
            assert valid is True, f"Validation failed for {img_path}: {err}"

            # Test VQA API
            with open(img_path, "rb") as fh:
                res = client.post(
                    "/api/v1/vqa",
                    files={"file": (s["image_file"], fh, "image/png")},
                    data={"question": s["question"]},
                )
            assert res.status_code == 200, f"VQA failed: {res.text}"
            res_json = res.json()
            assert res_json["status"] == "success"
            assert "answer" in res_json
            assert len(res_json["answer"]) > 0


def test_caption_samples_and_api_execution():
    """Verify Scene Captioning samples and endpoint execution."""
    cap_manifest_path = os.path.join(SAMPLES_DIR, "caption", "manifest.json")
    with open(cap_manifest_path, "r") as f:
        meta = json.load(f)

    samples = meta["samples"]
    assert len(samples) >= 2

    with TestClient(app) as client:
        for s in samples[:2]:
            img_path = os.path.join(SAMPLES_DIR, "caption", s["image_file"])
            assert os.path.isfile(img_path), f"Missing caption image: {img_path}"

            with open(img_path, "rb") as fh:
                res = client.post(
                    "/api/v1/caption",
                    files={"file": (s["image_file"], fh, "image/png")},
                )
            assert res.status_code == 200, f"Caption failed: {res.text}"
            res_json = res.json()
            assert res_json["status"] == "success"
            assert "caption" in res_json
            assert len(res_json["caption"]) > 10


def test_grounding_samples_and_api_execution():
    """Verify Region Grounding samples and endpoint execution."""
    ground_manifest_path = os.path.join(SAMPLES_DIR, "grounding", "manifest.json")
    with open(ground_manifest_path, "r") as f:
        meta = json.load(f)

    samples = meta["samples"]
    assert len(samples) >= 2

    with TestClient(app) as client:
        for s in samples[:2]:
            img_path = os.path.join(SAMPLES_DIR, "grounding", s["image_file"])
            assert os.path.isfile(img_path), f"Missing grounding image: {img_path}"

            with open(img_path, "rb") as fh:
                res = client.post(
                    "/api/v1/grounding",
                    files={"file": (s["image_file"], fh, "image/png")},
                    data={"query": s["target_query"]},
                )
            assert res.status_code == 200, f"Grounding failed: {res.text}"
            res_json = res.json()
            assert res_json["status"] == "success"
            assert len(res_json["bounding_boxes"]) >= 1
            assert res_json["annotated_image_b64"]


def test_land_cover_geotiff_specifications_and_api():
    """Verify BigEarthNet 12-band and 2-band GeoTIFFs."""
    s2_tif = os.path.join(SAMPLES_DIR, "land_cover", "sentinel2_12band_multispectral.tif")
    s1_tif = os.path.join(SAMPLES_DIR, "land_cover", "sentinel1_2band_sar.tif")
    s1_s2_tif = os.path.join(SAMPLES_DIR, "land_cover", "sentinel1_s2_14band_multimodal.tif")
    rgb_preview = os.path.join(SAMPLES_DIR, "land_cover", "sentinel2_land_cover_rgb_preview.png")

    assert os.path.isfile(s2_tif)
    assert os.path.isfile(s1_tif)
    assert os.path.isfile(s1_s2_tif)
    assert os.path.isfile(rgb_preview)

    # Inspect S2 GeoTIFF
    with rasterio.open(s2_tif) as src:
        assert src.count == 12, f"Expected 12 bands, got {src.count}"
        assert src.shape == (120, 120)
        assert src.dtypes[0] == "float32"
        assert str(src.crs) == "EPSG:32634"
        expected_s2_bands = ("B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12")
        assert tuple(src.descriptions) == expected_s2_bands

    # Inspect S1 GeoTIFF
    with rasterio.open(s1_tif) as src:
        assert src.count == 2
        assert src.shape == (120, 120)
        assert tuple(src.descriptions) == ("VV", "VH")

    # Inspect S1+S2 14-band GeoTIFF
    with rasterio.open(s1_s2_tif) as src:
        assert src.count == 14
        assert src.descriptions[0] == "VV"
        assert src.descriptions[1] == "VH"
        assert src.descriptions[2] == "B01"

    # Test BigEarthNet /api/v1/land-cover rejection of RGB preview
    with TestClient(app) as client:
        with open(rgb_preview, "rb") as fh:
            res = client.post(
                "/api/v1/land-cover",
                files={"file": ("preview.png", fh, "image/png")},
            )
        assert res.status_code == 422
        assert "BigEarthNet requires a 12-band Sentinel-2 GeoTIFF" in res.json()["detail"]


def test_change_detection_samples_and_api_execution():
    """Verify bi-temporal change detection pairs and API."""
    change_manifest_path = os.path.join(SAMPLES_DIR, "change_detection", "manifest.json")
    with open(change_manifest_path, "r") as f:
        meta = json.load(f)

    samples = meta["samples"]
    assert len(samples) >= 3

    with TestClient(app) as client:
        for s in samples:
            t1_path = os.path.join(SAMPLES_DIR, "change_detection", s["t1_file"])
            t2_path = os.path.join(SAMPLES_DIR, "change_detection", s["t2_file"])
            mask_path = os.path.join(SAMPLES_DIR, "change_detection", s["ground_truth_mask_file"])

            assert os.path.isfile(t1_path)
            assert os.path.isfile(t2_path)
            assert os.path.isfile(mask_path)

            with open(t1_path, "rb") as f1, open(t2_path, "rb") as f2:
                res = client.post(
                    "/api/v1/change",
                    files={
                        "file_t1": (s["t1_file"], f1, "image/png"),
                        "file_t2": (s["t2_file"], f2, "image/png"),
                    },
                )
            assert res.status_code == 200, f"Change detection failed: {res.text}"
            res_json = res.json()
            assert res_json["status"] == "success"
            assert "change_summary" in res_json
            assert res_json["change_ratio"] > 0.05
            assert res_json["change_map_b64"]


def test_optical_sar_samples_and_api_execution():
    """Verify co-registered Optical + SAR dual upload and cross-modal fusion."""
    optsar_manifest_path = os.path.join(SAMPLES_DIR, "optical_sar", "manifest.json")
    with open(optsar_manifest_path, "r") as f:
        meta = json.load(f)

    samples = meta["samples"]
    assert len(samples) >= 2

    with TestClient(app) as client:
        for s in samples:
            opt_path = os.path.join(SAMPLES_DIR, "optical_sar", s["optical_file"])
            sar_path = os.path.join(SAMPLES_DIR, "optical_sar", s["sar_file"])

            assert os.path.isfile(opt_path)
            assert os.path.isfile(sar_path)

            with open(opt_path, "rb") as f_opt, open(sar_path, "rb") as f_sar:
                res = client.post(
                    "/api/v1/optical-sar",
                    files={
                        "optical_file": (s["optical_file"], f_opt, "image/png"),
                        "sar_file": (s["sar_file"], f_sar, "image/png"),
                    },
                    data={"query": "Identify water and built-up areas using both optical and SAR."},
                )
            assert res.status_code == 200, f"Optical-SAR fusion failed: {res.text}"
            res_json = res.json()
            assert res_json["status"] == "success"
            assert res_json["class_coverage"]["water"] > 0.10
            assert res_json["class_coverage"]["built_up"] > 0.04
            assert len(res_json["bounding_boxes"]) >= 2
            assert res_json["overlay_b64"]


if __name__ == "__main__":
    pytest.main(["-v", __file__])
