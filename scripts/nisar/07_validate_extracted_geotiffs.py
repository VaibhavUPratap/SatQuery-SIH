#!/usr/bin/env python3
"""Exhaustively validate the extracted Bengaluru GeoTIFFs and their grids."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import rasterio

LOG = logging.getLogger("nisar_validate")
MEASUREMENTS = (
    ("20261029", "HH"), ("20261029", "HV"),
    ("20261110", "HH"), ("20261110", "HV"),
)
MASKS = (
    ("20261029", "quality", "uint8"), ("20261110", "quality", "uint8"),
    ("20261029", "exception", "uint16"), ("20261110", "exception", "uint16"),
)


def _stats(data: np.ndarray, valid: np.ndarray) -> dict[str, Any]:
    count = int(data.size)
    valid_count = int(valid.sum())
    values = data[valid]
    result: dict[str, Any] = {
        "total_pixels": count,
        "valid_pixel_count": valid_count,
        "invalid_pixel_count": count - valid_count,
        "valid_percentage": round(100 * valid_count / count, 6),
        "min": None,
        "max": None,
        "mean": None,
        "stddev": None,
    }
    if values.size:
        result.update(
            min=float(np.min(values)),
            max=float(np.max(values)),
            mean=float(np.mean(values, dtype=np.float64)),
            stddev=float(np.std(values, dtype=np.float64)),
        )
    return result


def audit(path: Path, category: str, root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path.relative_to(root)),
        "category": category,
        "exists": path.is_file(),
        "readable": False,
    }
    if not path.is_file():
        return result
    with rasterio.open(path) as src:
        data = src.read(1)
        result.update(
            readable=True,
            height=src.height,
            width=src.width,
            dtype=src.dtypes[0],
            crs=str(src.crs),
            nodata=str(src.nodata),
            transform=str(src.transform),
            resolution=f"{src.res[0]},{src.res[1]}",
            bounds=f"{src.bounds.left},{src.bounds.bottom},{src.bounds.right},{src.bounds.top}",
        )
        if category == "measurement":
            valid = np.isfinite(data) & (data > 0)
        elif category == "quality":
            valid = (data != 0) & (data != 255)
        else:
            valid = data != 65535
        result.update(_stats(data, valid))
        if category == "measurement" and valid.any():
            result["min_db"] = float(10 * np.log10(np.min(data[valid])))
            result["max_db"] = float(10 * np.log10(np.max(data[valid])))
            result["mean_db"] = float(np.mean(10 * np.log10(data[valid]), dtype=np.float64))
        else:
            result.update(min_db=None, max_db=None, mean_db=None)
    return result


def geometry(path: Path) -> tuple[Any, ...]:
    with rasterio.open(path) as src:
        return (src.crs, src.width, src.height, src.transform, src.bounds, src.res)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = Path(__file__).resolve().parents[2]
    base = root / "datasets" / "processed" / "bengaluru"
    records: list[dict[str, Any]] = []
    for date, pol in MEASUREMENTS:
        records.append(audit(base / f"nisar_{pol.lower()}_{date}.tif", "measurement", root))
    for date, kind, _dtype in MASKS:
        records.append(audit(base / "masks" / f"{kind}_mask_{date}.tif", kind, root))

    missing = [item["path"] for item in records if not item["exists"]]
    unreadable = [item["path"] for item in records if item["exists"] and not item["readable"]]
    if missing or unreadable:
        raise RuntimeError(f"Missing files: {missing}; unreadable files: {unreadable}")

    reference = geometry(base / "nisar_hh_20261029.tif")
    geometry_checks: dict[str, Any] = {}
    for date, pol in MEASUREMENTS:
        path = base / f"nisar_{pol.lower()}_{date}.tif"
        geometry_checks[f"{pol}_{date}"] = geometry(path) == reference
    for date, kind, _dtype in MASKS:
        path = base / "masks" / f"{kind}_mask_{date}.tif"
        geometry_checks[f"{kind}_{date}"] = geometry(path) == reference
    cross_date = {
        "grid_compatible": geometry(base / "nisar_hh_20261110.tif") == reference,
        "details": geometry_checks,
    }
    output = base / "validation_summary.csv"
    pd.DataFrame(records).to_csv(output, index=False)
    (base / "validation_grid_compatibility.json").write_text(json.dumps(cross_date, indent=2) + "\n")
    LOG.info("Wrote %s", output)
    LOG.info("Cross-date grid compatible: %s", cross_date["grid_compatible"])
    print(pd.DataFrame(records)[["path", "valid_percentage", "min", "max", "mean", "stddev"]].to_string(index=False))
    print(json.dumps(cross_date, indent=2, default=str))


if __name__ == "__main__":
    main()
