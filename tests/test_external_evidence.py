from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from backend.services.external_evidence import inspect_external_evidence


def test_local_external_raster_records_source_date_and_aoi_coverage(tmp_path: Path):
    source_path = tmp_path / "sentinel2_context.tif"
    with rasterio.open(
        source_path,
        "w",
        driver="GTiff",
        width=10,
        height=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(77.4, 13.2, 0.04, 0.04),
    ) as dataset:
        dataset.write(np.ones((1, 10, 10), dtype="float32"))

    evidence = inspect_external_evidence(
        [
            {
                "source": "Sentinel-2",
                "path": str(source_path),
                "source_date": "2026-11-09",
                "source_url": "https://dataspace.copernicus.eu/",
            }
        ],
        [77.45, 12.85, 77.75, 13.1],
        [tmp_path],
    )

    source = next(item for item in evidence["sources"] if item["source"] == "Sentinel-2")
    assert evidence["status"] == "available"
    assert source["source_date"] == "2026-11-09"
    assert source["coverage"] == "overlap"
    assert source["crs"] == "EPSG:4326"
