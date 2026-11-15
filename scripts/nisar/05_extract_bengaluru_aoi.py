#!/usr/bin/env python3
"""Extract the Bengaluru AOI from the two NISAR L2 GCOV frequency-A grids."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.warp import transform

LOG = logging.getLogger("nisar_extract_aoi")
CRS = "EPSG:32643"
GRID_PATH = "science/LSAR/GCOV/grids/frequencyA"
AOI = {"west": 77.40, "east": 77.80, "south": 12.80, "north": 13.15}
OBSERVATIONS = (
    (
        "20261029",
        "NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001.h5",
    ),
    (
        "20261110",
        "NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001.h5",
    ),
)


def _scalar(value: Any) -> str:
    value = value.item() if isinstance(value, np.generic) else value
    if isinstance(value, bytes):
        return value.decode("utf-8").rstrip("\x00")
    return str(value)


def calculate_window(grid: h5py.Group) -> tuple[slice, slice, Affine, dict[str, float]]:
    """Return the pixel-edge window enclosing the projected geographic AOI."""
    xs = grid["xCoordinates"][:]
    ys = grid["yCoordinates"][:]
    dx = float(grid["xCoordinateSpacing"][()])
    dy = float(grid["yCoordinateSpacing"][()])
    projection = int(grid["projection"].attrs["epsg_code"])
    if f"EPSG:{projection}" != CRS:
        raise ValueError(f"Unexpected grid CRS: EPSG:{projection}")
    if not np.allclose(np.diff(xs), dx) or not np.allclose(np.diff(ys), dy):
        raise ValueError("HDF5 coordinate axes are not regular at their declared spacing")
    if dx <= 0 or dy >= 0:
        raise ValueError(f"Unexpected axis direction: dx={dx}, dy={dy}")

    lon = [AOI["west"], AOI["east"], AOI["east"], AOI["west"]]
    lat = [AOI["south"], AOI["south"], AOI["north"], AOI["north"]]
    eastings, northings = transform("EPSG:4326", CRS, lon, lat)
    min_x, max_x = min(eastings), max(eastings)
    min_y, max_y = min(northings), max(northings)

    # Coordinate arrays are pixel centers. Convert the first center to its edge.
    left = xs[0] - dx / 2
    top = ys[0] - dy / 2
    col_start = max(0, int(np.floor((min_x - left) / dx)))
    col_stop = min(xs.size, int(np.ceil((max_x - left) / dx)))
    row_start = max(0, int(np.floor((top - max_y) / abs(dy))))
    row_stop = min(ys.size, int(np.ceil((top - min_y) / abs(dy))))
    if col_start >= col_stop or row_start >= row_stop:
        raise ValueError("AOI does not intersect the frequency-A grid")

    window_transform = Affine(
        dx,
        0,
        xs[col_start] - dx / 2,
        0,
        dy,
        ys[row_start] - dy / 2,
    )
    bounds = {
        "west": window_transform.c,
        "east": window_transform.c + (col_stop - col_start) * dx,
        "south": window_transform.f + (row_stop - row_start) * dy,
        "north": window_transform.f,
    }
    LOG.info(
        "AOI projected bounds x=[%.3f, %.3f], y=[%.3f, %.3f]; "
        "window rows=%d:%d cols=%d:%d (%dx%d)",
        min_x, max_x, min_y, max_y, row_start, row_stop, col_start, col_stop,
        row_stop - row_start, col_stop - col_start,
    )
    return slice(row_start, row_stop), slice(col_start, col_stop), window_transform, bounds


def metadata_tags(h5: h5py.File, date: str, polarization: str, term: str) -> dict[str, str]:
    ident = h5["science/LSAR/identification"]
    source = h5["science/LSAR/GCOV/metadata/sourceData/swaths/frequencyA"]
    names = (
        "platformName", "instrumentName", "productLevel", "productType", "granuleId",
        "trackNumber", "frameNumber", "absoluteOrbitNumber", "orbitPassDirection",
        "lookDirection", "zeroDopplerStartTime", "zeroDopplerEndTime",
        "processingDateTime", "processingCenter", "productSpecificationVersion",
        "productVersion", "compositeReleaseId",
    )
    tags = {name.upper(): _scalar(ident[name][()]) for name in names}
    tags.update(
        {
            "ACQUISITION_DATE": date,
            "FREQUENCY_GRID": "frequencyA",
            "POLARIZATION": polarization,
            "COVARIANCE_TERM": term,
            "MEASUREMENT_QUANTITY": "RTC gamma-zero (gamma0) power",
            "MEASUREMENT_UNITS": "linear power (unitless)",
            "CRS": CRS,
            "PIXEL_SIZE_METRES": "10",
            "AOI_BBOX_WGS84": "77.40,12.80,77.80,13.15",
            "CENTER_FREQUENCY_HZ": _scalar(source["centerFrequency"][()]),
            "PROCESSED_RANGE_BANDWIDTH_HZ": _scalar(source["processedRangeBandwidth"][()]),
        }
    )
    return tags


def write_raster(
    path: Path,
    data: np.ndarray,
    transform_: Affine,
    dtype: str,
    nodata: int | float,
    tags: dict[str, str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": dtype,
        "crs": CRS,
        "transform": transform_,
        "nodata": nodata,
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags)


def process(date: str, filename: str, raw_dir: Path, output_dir: Path) -> None:
    source_path = raw_dir / filename
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    with h5py.File(source_path, "r") as h5:
        grid = h5[GRID_PATH]
        required = ("HHHH", "HVHV", "mask", "inputDataExceptionMask")
        missing = [name for name in required if name not in grid]
        if missing:
            raise KeyError(f"Missing datasets in {GRID_PATH}: {missing}")
        row_slice, col_slice, transform_, bounds = calculate_window(grid)
        arrays = {
            "HH": np.asarray(grid["HHHH"][row_slice, col_slice], dtype=np.float32),
            "HV": np.asarray(grid["HVHV"][row_slice, col_slice], dtype=np.float32),
            "quality": np.asarray(grid["mask"][row_slice, col_slice], dtype=np.uint8),
            "exception": np.asarray(
                grid["inputDataExceptionMask"][row_slice, col_slice], dtype=np.uint16
            ),
        }
        shape = arrays["HH"].shape
        if any(array.shape != shape for array in arrays.values()):
            raise ValueError("Measurement and mask windows do not have identical shapes")
        for pol, term in (("HH", "HHHH"), ("HV", "HVHV")):
            write_raster(
                output_dir / f"nisar_{pol.lower()}_{date}.tif",
                arrays[pol],
                transform_,
                "float32",
                np.nan,
                metadata_tags(h5, date, pol, term),
            )
        quality_tags = {
            "MISSION": "NISAR",
            "PRODUCT_TYPE": "GCOV",
            "GRANULE_ID": _scalar(h5["science/LSAR/identification/granuleId"][()]),
            "MASK_TYPE": "Valid samples subswath mask",
            "MASK_DEFINITION": "0=partially focused or invalid; 1..n=valid subswath; 255=outside acquisition extent",
            "SOURCE_DATASET": f"{GRID_PATH}/mask",
        }
        exception_tags = {
            "MISSION": "NISAR",
            "PRODUCT_TYPE": "GCOV",
            "GRANULE_ID": _scalar(h5["science/LSAR/identification/granuleId"][()]),
            "MASK_TYPE": "inputDataExceptionMask",
            "MASK_DEFINITION": "Bitwise OR of input exceptions and polarization validity bits; 65535=fill",
            "SOURCE_DATASET": f"{GRID_PATH}/inputDataExceptionMask",
        }
        write_raster(output_dir / "masks" / f"quality_mask_{date}.tif", arrays["quality"], transform_, "uint8", 255, quality_tags)
        write_raster(output_dir / "masks" / f"exception_mask_{date}.tif", arrays["exception"], transform_, "uint16", 65535, exception_tags)
        LOG.info("Wrote %s AOI rasters with bounds %s", date, bounds)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", stream=sys.stdout)
    root = Path(__file__).resolve().parents[2]
    raw_dir = root / "datasets" / "raw"
    output_dir = root / "datasets" / "processed" / "bengaluru"
    for date, filename in OBSERVATIONS:
        process(date, filename, raw_dir, output_dir)


if __name__ == "__main__":
    main()
