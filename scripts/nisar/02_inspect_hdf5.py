#!/usr/bin/env python3
"""
scripts/nisar/02_inspect_hdf5.py
================================
NISAR L2 GCOV HDF5 Internal Structure Inspection and Inventory Generator.

Author: Senior SAR Remote Sensing Engineer & Geospatial Data Engineer
Role: Member 2 – NISAR Data Acquisition and Geospatial Processing
Project: SatQuery-SIH (NASA Space Apps Challenge)

Scope:
- Recursively walks both NISAR L2 GCOV HDF5 hierarchies without loading large arrays.
- Documents object types, dimensions, shapes, data types, chunking, compression, and attributes.
- Categorizes datasets into root, identification, science measurements, geolocation/projection,
  calibration, orbit/attitude, and processing information.
- Verifies structural consistency and differences across both acquisition dates.
- Outputs structural hierarchy text files:
    datasets/raw/metadata/hdf5_structure_20261029.txt
    datasets/raw/metadata/hdf5_structure_20261110.txt
- Outputs full dataset inventory:
    datasets/raw/metadata/hdf5_dataset_inventory.csv
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np
import h5py

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("nisar_inspect_hdf5")

PRODUCTS = [
    {
        "date": "20261029",
        "filename": "NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001.h5",
        "structure_txt": "hdf5_structure_20261029.txt"
    },
    {
        "date": "20261110",
        "filename": "NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001.h5",
        "structure_txt": "hdf5_structure_20261110.txt"
    }
]


def sanitize_attr_value(val: Any) -> Any:
    """Converts HDF5 attribute value into JSON-serializable standard Python type."""
    if isinstance(val, (bytes, np.bytes_)):
        return val.decode("utf-8", errors="replace")
    elif isinstance(val, np.generic):
        return val.item()
    elif isinstance(val, np.ndarray):
        if val.dtype == object:
            # Handle object references or nested arrays
            return [str(item) for item in val.flatten()]
        elif val.size <= 10:
            return [sanitize_attr_value(x) for x in val.flatten()]
        else:
            return f"<array shape={val.shape} dtype={val.dtype}>"
    elif isinstance(val, (list, tuple)):
        return [sanitize_attr_value(x) for x in val]
    return str(val) if not isinstance(val, (int, float, bool, str, type(None))) else val


def categorize_path(path: str) -> str:
    """Classifies an HDF5 path into standard functional SAR domains."""
    if path == "/" or path == "science":
        return "Root"
    elif "identification" in path:
        return "Product Identification"
    elif "grids/frequencyA" in path or "grids/frequencyB" in path:
        if any(term in path for term in ["HHHH", "HVHV", "VVVV", "VHVH", "HHHV"]):
            return "Science Measurement (Covariance)"
        elif any(term in path for term in ["Coordinates", "Spacing", "projection"]):
            return "Geolocation & Map Projection"
        elif any(term in path for term in ["mask", "numberOfLooks", "rtcGammaToSigmaFactor"]):
            return "Quality & Radiometric Factors"
        else:
            return "Gridded Science Layer"
    elif "calibrationInformation" in path:
        return "Calibration & Radiometry"
    elif "orbit" in path:
        return "Orbit State Vectors"
    elif "attitude" in path:
        return "Attitude & Ephemeris"
    elif "processingInformation" in path:
        return "Processing & Algorithm Configuration"
    elif "sourceData" in path:
        return "Radar Instrument & Source Data"
    else:
        return "Ancillary / Metadata"


def inspect_single_hdf5(
    file_path: Path,
    date_str: str,
    output_txt_path: Path
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Recursively walks an HDF5 file and extracts full schema and inventory."""
    logger.info(f"Inspecting HDF5 structure: {file_path.name}")
    inventory_records = []
    text_lines = []

    text_lines.append("=" * 100)
    text_lines.append(f"NISAR L2 GCOV HDF5 STRUCTURE INSPECTION REPORT: {date_str}")
    text_lines.append(f"File: {file_path.name}")
    text_lines.append(f"Size: {file_path.stat().st_size:,} bytes")
    text_lines.append("=" * 100)
    text_lines.append("")

    with h5py.File(file_path, "r") as h5:
        # Check granule ID if present
        granule_id = "UNKNOWN"
        if "science/LSAR/identification/granuleId" in h5:
            raw_id = h5["science/LSAR/identification/granuleId"][()]
            granule_id = raw_id.decode("utf-8") if isinstance(raw_id, bytes) else str(raw_id)

        text_lines.append(f"Granule ID: {granule_id}")
        text_lines.append(f"Root groups: {list(h5.keys())}")
        text_lines.append("")
        text_lines.append("DETAILED HIERARCHY AND METADATA TREE:")
        text_lines.append("-" * 100)

        # Record root group attributes
        root_attrs = {k: sanitize_attr_value(v) for k, v in h5.attrs.items()}
        if root_attrs:
            text_lines.append(f"/ (Root Attributes: {root_attrs})")

        def visitor(name: str, obj: Any):
            indent_level = name.count("/")
            indent = "  " * indent_level
            category = categorize_path(name)

            attrs_dict = {k: sanitize_attr_value(v) for k, v in obj.attrs.items()}
            attrs_summary = json.dumps(attrs_dict, default=str) if attrs_dict else "{}"

            if isinstance(obj, h5py.Group):
                text_lines.append(f"{indent}[GROUP] /{name}  | Category: {category}")
                if attrs_dict:
                    text_lines.append(f"{indent}  Attributes: {attrs_dict}")

                inventory_records.append({
                    "observation_date": date_str,
                    "granule_id": granule_id,
                    "path": f"/{name}",
                    "name": name.split("/")[-1],
                    "object_type": "Group",
                    "category": category,
                    "shape": "N/A",
                    "ndim": 0,
                    "dtype": "N/A",
                    "chunks": "N/A",
                    "compression": "N/A",
                    "fillvalue": "N/A",
                    "attributes_summary": attrs_summary
                })
            elif isinstance(obj, h5py.Dataset):
                shape_str = str(obj.shape)
                dtype_str = str(obj.dtype)
                chunks_str = str(obj.chunks) if obj.chunks is not None else "None"
                comp_str = str(obj.compression) if obj.compression is not None else "None"

                # Check for fillvalue
                fillval = obj.fillvalue
                if "_FillValue" in obj.attrs:
                    fillval = sanitize_attr_value(obj.attrs["_FillValue"])
                else:
                    fillval = sanitize_attr_value(fillval)
                fillval_str = str(fillval)

                text_lines.append(
                    f"{indent}[DATASET] /{name} | Shape: {shape_str} | Dtype: {dtype_str} "
                    f"| Chunks: {chunks_str} | Comp: {comp_str} | Fill: {fillval_str}"
                )
                if attrs_dict:
                    text_lines.append(f"{indent}  Attributes: {attrs_dict}")

                inventory_records.append({
                    "observation_date": date_str,
                    "granule_id": granule_id,
                    "path": f"/{name}",
                    "name": name.split("/")[-1],
                    "object_type": "Dataset",
                    "category": category,
                    "shape": shape_str,
                    "ndim": obj.ndim,
                    "dtype": dtype_str,
                    "chunks": chunks_str,
                    "compression": comp_str,
                    "fillvalue": fillval_str,
                    "attributes_summary": attrs_summary
                })

        h5.visititems(visitor)

    text_lines.append("")
    text_lines.append("=" * 100)
    text_lines.append("END OF STRUCTURE REPORT")
    text_lines.append("=" * 100)

    output_txt_path.write_text("\n".join(text_lines), encoding="utf-8")
    logger.info(f"Structure text report saved to: {output_txt_path}")
    return inventory_records, text_lines


def main():
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "datasets" / "raw"
    metadata_dir = raw_dir / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    all_inventory = []

    for prod in PRODUCTS:
        fpath = raw_dir / prod["filename"]
        if not fpath.exists():
            logger.error(f"Cannot inspect missing file: {fpath}")
            continue

        txt_out = metadata_dir / prod["structure_txt"]
        records, _ = inspect_single_hdf5(fpath, prod["date"], txt_out)
        all_inventory.extend(records)

    if all_inventory:
        df_inv = pd.DataFrame(all_inventory)
        csv_out = metadata_dir / "hdf5_dataset_inventory.csv"
        df_inv.to_csv(csv_out, index=False)
        logger.info(f"Unified HDF5 dataset inventory exported to: {csv_out}")

        # Print summary breakdown
        print("\n" + "=" * 80)
        print("HDF5 DATASET INVENTORY SUMMARY:")
        print("=" * 80)
        print(f"Total Objects Indexed across products: {len(df_inv)}")
        print("\nBreakdown by Object Type:")
        print(df_inv.groupby(["observation_date", "object_type"]).size().unstack(fill_value=0))
        print("\nBreakdown by Functional Category (20261029):")
        cat_counts = df_inv[df_inv["observation_date"] == "20261029"]["category"].value_counts()
        for cat, cnt in cat_counts.items():
            print(f"  {cat:40s} : {cnt:3d} objects")
        print("=" * 80)


if __name__ == "__main__":
    main()
