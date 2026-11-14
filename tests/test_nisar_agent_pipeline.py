"""End-to-End Test Suite for TerraPulse NISAR Agentic Intelligence & Specialist Models."""
import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.api.main import app
from backend.agent.graph import agent_graph
from backend.models.nisar.change_detection import NISARChangeDetectionModel
from backend.models.nisar.flood_inundation import NISARFloodInundationModel
from backend.preprocessing.nisar_reader import NISARProductReader


@pytest.fixture(scope="module")
def nisar_temporal_h5_pair():
    """Create a temporary bi-temporal pair of synthetic NISAR L2-GCOV files."""
    tmp_dir = tempfile.mkdtemp(prefix="nisar_agent_test_")
    t1_path = os.path.join(tmp_dir, "NISAR_GCOV_T1_Dry.h5")
    t2_path = os.path.join(tmp_dir, "NISAR_GCOV_T2_Flood.h5")

    NISARProductReader.create_synthetic_nisar_gcov(
        output_path=t1_path,
        width=128,
        height=128,
        with_flood=False,
        date_str="2026-06-01",
    )

    NISARProductReader.create_synthetic_nisar_gcov(
        output_path=t2_path,
        width=128,
        height=128,
        with_flood=True,
        date_str="2026-07-25",
    )

    yield t1_path, t2_path

    # Cleanup
    for p in [t1_path, t2_path]:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(tmp_dir):
        os.rmdir(tmp_dir)


def test_nisar_change_detection_model_direct(nisar_temporal_h5_pair):
    t1, t2 = nisar_temporal_h5_pair
    model = NISARChangeDetectionModel()
    res = model.run({
        "image_path_a": t1,
        "image_path_b": t2,
        "threshold_db": 3.0,
    })

    assert res["status"] == "success"
    assert res["task"] == "nisar_change_detection"
    assert res["changed_area_km2"] > 0
    assert res["changed_area_hectares"] > 0
    assert res["decreased_area_km2"] > 0  # Water expansion creates backscatter decrease
    assert "change_map_b64" in res
    assert len(res["change_map_b64"]) > 100


def test_nisar_flood_inundation_model_direct(nisar_temporal_h5_pair):
    t1, t2 = nisar_temporal_h5_pair
    model = NISARFloodInundationModel()
    res = model.run({
        "t1_path": t1,
        "t2_path": t2,
        "water_threshold_db": -17.5,
    })

    assert res["status"] == "success"
    assert res["task"] == "nisar_flood_inundation"
    assert res["new_flood_area_km2"] > 0
    assert res["permanent_water_area_km2"] > 0
    assert res["water_expansion_ratio"] > 0
    assert "flood_map_b64" in res
    assert "2026-06-01" in res["flood_summary"]
    assert "2026-07-25" in res["flood_summary"]


def test_agent_graph_nisar_flood_routing(nisar_temporal_h5_pair):
    t1, t2 = nisar_temporal_h5_pair

    initial_state = {
        "file_1_path": t1,
        "file_2_path": t2,
        "query": "Track flood inundation dynamics and calculate submerged area",
        "requested_task": "auto",
        "include_report": True,
        "thread_id": "test_flood_session",
    }

    final_state = agent_graph.invoke(initial_state)
    output = final_state.get("final_output", {})

    assert output.get("status") == "success"
    assert output.get("route", {}).get("task") == "nisar_flood"
    assert "flood" in output.get("answer", "").lower()
    assert output.get("new_flood_area_km2", 0) > 0
    assert "overlay_b64" in output
    assert "report_pdf_b64" in output
    assert len(output["report_pdf_b64"]) > 500


def test_agent_graph_nisar_change_routing(nisar_temporal_h5_pair):
    t1, t2 = nisar_temporal_h5_pair

    initial_state = {
        "file_1_path": t1,
        "file_2_path": t2,
        "query": "Analyze NISAR radar backscatter change across observation dates",
        "requested_task": "auto",
        "include_report": False,
        "thread_id": "test_change_session",
    }

    final_state = agent_graph.invoke(initial_state)
    output = final_state.get("final_output", {})

    assert output.get("status") == "success"
    assert output.get("route", {}).get("task") == "nisar_change"
    assert output.get("changed_area_km2", 0) > 0
    assert "overlay_b64" in output


def test_agent_api_nisar_flood_inundation_e2e(nisar_temporal_h5_pair):
    t1, t2 = nisar_temporal_h5_pair

    with TestClient(app) as client:
        with open(t1, "rb") as f1, open(t2, "rb") as f2:
            res = client.post(
                "/api/v1/agent",
                files={
                    "file_1": ("NISAR_T1.h5", f1, "application/x-hdf5"),
                    "file_2": ("NISAR_T2.h5", f2, "application/x-hdf5"),
                },
                data={
                    "query": "Identify flood inundation changes and map water extent",
                    "include_report": "true",
                    "thread_id": "e2e_nisar_flood",
                },
            )

        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        assert data["route"]["task"] == "nisar_flood"
        assert "flood" in data["answer"].lower()
        assert "new_flood_area_km2" in data
        assert "overlay_b64" in data
        assert "report_pdf_b64" in data
