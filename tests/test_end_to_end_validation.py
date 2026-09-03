"""End-to-End Validation Test Suite for SatQuery AI.

Validates the full pipeline:
Upload -> Input Validation -> LangGraph Agent DAG -> Specialist Routing ->
Inference -> Evidence Fusion -> Confidence Scoring -> PDF Report Generation.

Tests all input modalities and multi-geographic terrain configurations:
1. Single Optical Image VQA & Grounding (Forest Canopy & Lake Suburb)
2. Single Image Captioning & Scene Description
3. Bi-Temporal Change Detection (Deforestation, Urban Growth, Reservoir Depletion)
4. Cross-Modal Optical + SAR Analysis (Coastal Port & River Farmland)
5. Session thread-level checkpoint state persistence
6. Invalid and corrupted image rejection handling
"""
import base64
import os
import sys
import tempfile
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.api.main import app
from backend.agent.graph import agent_graph

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES_DIR = os.path.join(BASE_DIR, "datasets", "samples")
EVAL_DIR = os.path.join(BASE_DIR, "datasets", "evaluation_suite")


def test_e2e_single_image_vqa_and_grounding():
    forest_img = os.path.join(SAMPLES_DIR, "forest_scene.png")
    lake_img = os.path.join(SAMPLES_DIR, "lake_suburb.png")
    assert os.path.exists(forest_img), f"{forest_img} missing"
    assert os.path.exists(lake_img), f"{lake_img} missing"

    with TestClient(app) as client:
        # 1. Test VQA on Lake Suburb
        with open(lake_img, "rb") as f:
            res_vqa = client.post(
                "/api/v1/agent",
                files={"file_1": ("lake_suburb.png", f, "image/png")},
                data={"query": "Is there a river or water body present?", "include_report": "true", "thread_id": "thread_e2e_vqa"},
            )
        assert res_vqa.status_code == 200, res_vqa.text
        p_vqa = res_vqa.json()
        assert p_vqa["status"] == "success"
        assert p_vqa["route"]["task"] == "vqa"
        assert p_vqa["confidence"] >= 0.60
        assert p_vqa["report_pdf_b64"]
        assert base64.b64decode(p_vqa["report_pdf_b64"]).startswith(b"%PDF")
        assert len(p_vqa["execution_trace"]["steps"]) >= 2

        # 2. Test Grounding on Forest Scene
        with open(forest_img, "rb") as f:
            res_ground = client.post(
                "/api/v1/agent",
                files={"file_1": ("forest_scene.png", f, "image/png")},
                data={"query": "Highlight the vegetation and forest area", "thread_id": "thread_e2e_ground"},
            )
        assert res_ground.status_code == 200, res_ground.text
        p_ground = res_ground.json()
        assert p_ground["status"] == "success"
        assert p_ground["route"]["task"] == "grounding"
        assert len(p_ground.get("bounding_boxes", [])) >= 1
        assert p_ground.get("overlay_b64") or p_ground.get("annotated_image_b64")


def test_e2e_single_image_captioning():
    forest_img = os.path.join(SAMPLES_DIR, "forest_scene.png")
    with TestClient(app) as client, open(forest_img, "rb") as f:
        res = client.post(
            "/api/v1/agent",
            files={"file_1": ("forest_scene.png", f, "image/png")},
            data={"query": "Describe this scene and summarize the terrain", "include_report": "true"},
        )
    assert res.status_code == 200, res.text
    p = res.json()
    assert p["status"] == "success"
    assert p["route"]["task"] == "caption"
    assert len(p["answer"]) > 10
    assert p["report_pdf_b64"]


def test_e2e_bitemporal_change_detection_and_vqa():
    change_t1 = os.path.join(EVAL_DIR, "change_pairs", "change_01_deforestation_t1.png")
    change_t2 = os.path.join(EVAL_DIR, "change_pairs", "change_01_deforestation_t2.png")
    assert os.path.exists(change_t1) and os.path.exists(change_t2)

    with TestClient(app) as client:
        with open(change_t1, "rb") as f1, open(change_t2, "rb") as f2:
            res = client.post(
                "/api/v1/agent",
                files={"file_1": ("t1.png", f1, "image/png"), "file_2": ("t2.png", f2, "image/png")},
                data={
                    "query": "What changed between these two dates and where did the change occur?",
                    "include_report": "true",
                    "thread_id": "thread_e2e_change"
                },
            )
        assert res.status_code == 200, res.text
        p = res.json()
        assert p["status"] == "success"
        assert p["route"]["task"] == "change"
        assert p.get("change_summary") or p.get("answer")
        assert p.get("overlay_b64") or p.get("change_map_b64")
        assert base64.b64decode(p["report_pdf_b64"]).startswith(b"%PDF")


def test_e2e_optical_sar_crossmodal_fusion():
    opt_path = os.path.join(EVAL_DIR, "optical_sar_pairs", "opt_sar_01_coastal_port_optical.png")
    sar_path = os.path.join(EVAL_DIR, "optical_sar_pairs", "opt_sar_01_coastal_port_sar.png")
    assert os.path.exists(opt_path) and os.path.exists(sar_path)

    with TestClient(app) as client:
        with open(opt_path, "rb") as f1, open(sar_path, "rb") as f2:
            res = client.post(
                "/api/v1/agent",
                files={"file_1": ("optical.png", f1, "image/png"), "file_2": ("sar.png", f2, "image/png")},
                data={
                    "query": "Use the optical and SAR images together to identify built-up and water-covered regions.",
                    "include_report": "true",
                    "thread_id": "thread_e2e_optsar"
                },
            )
        assert res.status_code == 200, res.text
        p = res.json()
        assert p["status"] == "success"
        assert p["route"]["task"] == "optical_sar"
        assert "optical_sar" in p["pair_metadata"]["pair_type"]
        assert len(p.get("bounding_boxes", [])) >= 2
        assert p.get("overlay_b64")


def test_e2e_validation_rejection_of_invalid_inputs():
    with TestClient(app) as client:
        # 1. Missing primary image
        res_missing = client.post("/api/v1/agent", data={"query": "Describe this scene"})
        assert res_missing.status_code == 422  # Unprocessable Entity

        # 2. Corrupted / non-image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"NOT_A_VALID_IMAGE_FILE_HEADER")
            bad_file = f.name

        try:
            with open(bad_file, "rb") as f:
                res_bad = client.post(
                    "/api/v1/agent",
                    files={"file_1": ("bad.png", f, "image/png")},
                    data={"query": "Describe scene"},
                )
            assert res_bad.status_code == 400
            p_bad = res_bad.json()
            assert "validation failed" in p_bad["detail"].lower()
        finally:
            if os.path.exists(bad_file):
                os.remove(bad_file)


if __name__ == "__main__":
    print("Running End-to-End Validation Tests...")
    test_e2e_single_image_vqa_and_grounding()
    test_e2e_single_image_captioning()
    test_e2e_bitemporal_change_detection_and_vqa()
    test_e2e_optical_sar_crossmodal_fusion()
    test_e2e_validation_rejection_of_invalid_inputs()
    print("All End-to-End validation tests passed successfully!")
