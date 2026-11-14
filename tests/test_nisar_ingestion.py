"""Tests for NASA-ISRO NISAR Product Reader, Validator, and API Endpoints."""
import os
import sys
import tempfile
import pytest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.preprocessing.nisar_reader import NISARProductReader
from backend.preprocessing.nisar_search import search_nisar_granules
from backend.validation.nisar_validator import NISARValidator


@pytest.fixture(scope="module")
def synthetic_nisar_pair():
    """Create a temporary bi-temporal pair of synthetic NISAR L2-GCOV products."""
    dir_path = tempfile.mkdtemp(prefix="nisar_test_")
    t1_path = os.path.join(dir_path, "NISAR_L2_GCOV_T1.h5")
    t2_path = os.path.join(dir_path, "NISAR_L2_GCOV_T2.h5")

    # T1: Baseline dry date
    NISARProductReader.create_synthetic_nisar_gcov(
        output_path=t1_path,
        width=128,
        height=128,
        with_flood=False,
        date_str="2026-06-01",
    )

    # T2: Post-monsoon flood date
    NISARProductReader.create_synthetic_nisar_gcov(
        output_path=t2_path,
        width=128,
        height=128,
        with_flood=True,
        date_str="2026-07-20",
    )

    yield t1_path, t2_path

    # Teardown
    for p in [t1_path, t2_path]:
        if os.path.exists(p):
            os.remove(p)
    if os.path.exists(dir_path):
        os.rmdir(dir_path)


def test_nisar_synthetic_creation_and_metadata(synthetic_nisar_pair):
    t1_path, _ = synthetic_nisar_pair
    assert NISARProductReader.is_hdf5_file(t1_path)

    metadata = NISARProductReader.inspect_metadata(t1_path)
    assert metadata["is_nisar"] is True
    assert metadata["product_type"] == "L2-GCOV"
    assert metadata["width"] == 128
    assert metadata["height"] == 128
    assert "HHHH" in metadata["polarizations"]
    assert "HVHV" in metadata["polarizations"]
    assert metadata["acquisition_date"] == "2026-06-01"


def test_nisar_read_backscatter_and_speckle_filtering(synthetic_nisar_pair):
    t1_path, _ = synthetic_nisar_pair
    # Read HH in dB
    arr_db, info_db = NISARProductReader.read_backscatter(t1_path, polarization="HHHH", to_db=True)
    assert arr_db.shape == (128, 128)
    assert info_db["unit"] == "dB (sigma-nought)"
    assert arr_db.mean() < 0  # Typical SAR backscatter is negative in dB

    # Read linear power
    arr_lin, info_lin = NISARProductReader.read_backscatter(t1_path, polarization="HHHH", to_db=False)
    assert np.all(arr_lin >= 0)

    # Test Lee speckle filter
    filtered = NISARProductReader.apply_speckle_filter(arr_db, method="lee", window_size=5)
    assert filtered.shape == arr_db.shape
    # Filtered array should have reduced local variance
    assert float(np.var(filtered)) <= float(np.var(arr_db)) + 1e-4


def test_nisar_dual_pol_ratio_and_preview(synthetic_nisar_pair):
    t1_path, _ = synthetic_nisar_pair
    dual = NISARProductReader.read_dual_pol(t1_path, to_db=True)
    assert "co_pol" in dual
    assert "cross_pol" in dual
    assert "ratio" in dual
    assert dual["co_pol"].shape == (128, 128)

    # Preview generation
    png_bytes, b64_str = NISARProductReader.generate_preview_png(t1_path)
    assert len(png_bytes) > 100
    assert len(b64_str) > 100


def test_nisar_validator_single_and_pair(synthetic_nisar_pair):
    t1_path, t2_path = synthetic_nisar_pair

    # Single product validation
    valid1, err1, meta1 = NISARValidator.validate_product(t1_path)
    assert valid1 is True
    assert err1 == ""
    assert meta1["width"] == 128

    # Temporal pair validation
    valid_pair, err_pair, pair_meta = NISARValidator.validate_temporal_pair(t1_path, t2_path)
    assert valid_pair is True
    assert err_pair == ""
    assert pair_meta["status"] == "compatible"
    assert "common_polarizations" in pair_meta
    assert pair_meta["spatial_overlap_iou"] == 1.0


def test_nisar_search_catalog():
    # Test bounding box search near Bengaluru
    res = search_nisar_granules(bbox=[77.0, 12.5, 77.8, 13.2], product_type="GCOV")
    assert res["status"] == "success"
    assert res["total_results"] >= 1
    assert any("Kaveri" in g.get("region_name", "") for g in res["granules"])


def test_nisar_api_endpoints(synthetic_nisar_pair):
    t1_path, _ = synthetic_nisar_pair

    with TestClient(app) as client:
        # 1. Search endpoint
        res_search = client.get("/api/v1/nisar/search?min_lon=76.8&min_lat=12.2&max_lon=77.9&max_lat=13.5")
        assert res_search.status_code == 200
        data = res_search.json()
        assert data["status"] == "success"

        # 2. Validation endpoint
        with open(t1_path, "rb") as f:
            res_val = client.post(
                "/api/v1/nisar/validate",
                files={"file": ("NISAR_T1.h5", f, "application/x-hdf5")},
            )
        assert res_val.status_code == 200
        val_data = res_val.json()
        assert val_data["status"] == "success"
        assert val_data["is_valid"] is True

        # 3. Preview endpoint
        with open(t1_path, "rb") as f:
            res_prev = client.post(
                "/api/v1/nisar/preview",
                files={"file": ("NISAR_T1.h5", f, "application/x-hdf5")},
            )
        assert res_prev.status_code == 200
        prev_data = res_prev.json()
        assert "preview_png_b64" in prev_data

        # 4. Synthesize demo endpoint
        res_syn = client.post(
            "/api/v1/nisar/synthesize",
            json={"target_date": "2026-08-15", "with_flood": True, "width": 64, "height": 64},
        )
        assert res_syn.status_code == 200
        syn_data = res_syn.json()
        assert syn_data["status"] == "success"
        assert "preview_b64" in syn_data
        # Cleanup synthesized temporary file
        if os.path.exists(syn_data["file_path"]):
            os.remove(syn_data["file_path"])
