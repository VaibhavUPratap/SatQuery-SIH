#!/usr/bin/env python3
"""
scripts/nisar/01_verify_downloads.py
===================================
NISAR L2 GCOV Download Verification and File Integrity Check.

Author: Senior SAR Remote Sensing Engineer & Geospatial Data Engineer
Role: Member 2 – NISAR Data Acquisition and Geospatial Processing
Project: SatQuery-SIH (NASA Space Apps Challenge)

Scope:
- Verifies physical presence and exact filenames of NISAR L2 GCOV HDF5 products.
- Computes exact file sizes (bytes, MB, GiB) and compares with ASF catalog metadata.
- Computes SHA-256 checksums via buffered streaming.
- Checks HDF5 readability and structural completeness using h5py.
- Exports verification metrics to datasets/raw/metadata/download_verification.csv.
"""

import sys
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import h5py

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("nisar_verify_downloads")

# Known catalog expectations
CATALOG_OBSERVATIONS = [
    {
        "granule_name": "NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001",
        "filename": "NISAR_L2_PR_GCOV_034_077_D_082_4005_DHDH_A_20261029T131919_20261029T131954_P05036_N_F_J_001.h5",
        "date": "2026-10-29",
        "expected_mb_asf": 6815.74
    },
    {
        "granule_name": "NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001",
        "filename": "NISAR_L2_PR_GCOV_035_077_D_082_4005_DHDH_A_20261110T131920_20261110T131954_P05036_N_F_J_001.h5",
        "date": "2026-11-10",
        "expected_mb_asf": 6627.00
    }
]


def compute_sha256(filepath: Path, chunk_size_mb: int = 64) -> str:
    """Computes SHA-256 hash using chunked streaming to prevent high memory usage."""
    hasher = hashlib.sha256()
    chunk_bytes = chunk_size_mb * 1024 * 1024
    with open(filepath, "rb") as f:
        while chunk := f.read(chunk_bytes):
            hasher.update(chunk)
    return hasher.hexdigest()


def test_hdf5_integrity(filepath: Path) -> Dict[str, Any]:
    """
    Validates HDF5 container completeness and readability using h5py.
    Checks root structure, presence of identification group, grids, and probes raster datasets.
    """
    result = {
        "h5py_readable": False,
        "root_groups": [],
        "has_identification": False,
        "has_gcov_grids": False,
        "probe_read_freqA_HHHH": False,
        "probe_read_freqA_HVHV": False,
        "integrity_error": None
    }

    try:
        with h5py.File(filepath, "r") as h5:
            result["h5py_readable"] = True
            result["root_groups"] = list(h5.keys())

            # Check standard NISAR GCOV groups
            if "science/LSAR/identification" in h5:
                result["has_identification"] = True

            if "science/LSAR/GCOV/grids" in h5:
                result["has_gcov_grids"] = True

            # Probe read small slices without loading large arrays
            freqA_path = "science/LSAR/GCOV/grids/frequencyA"
            if freqA_path in h5:
                freqA = h5[freqA_path]
                if "HHHH" in freqA:
                    _ = freqA["HHHH"][0:5, 0:5]
                    result["probe_read_freqA_HHHH"] = True
                if "HVHV" in freqA:
                    _ = freqA["HVHV"][0:5, 0:5]
                    result["probe_read_freqA_HVHV"] = True

    except Exception as exc:
        logger.error(f"Integrity check failed for {filepath.name}: {exc}")
        result["integrity_error"] = str(exc)

    return result


def load_asf_metadata(metadata_dir: Path) -> Dict[str, float]:
    """Finds and parses the ASF CSV download catalog if present."""
    asf_sizes = {}
    csv_files = list(metadata_dir.glob("asf-datapool-results*.csv"))
    if not csv_files:
        logger.warning(f"No ASF catalog CSV found in {metadata_dir}")
        return asf_sizes

    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file)
            if "Granule Name" in df.columns and "Size (MB)" in df.columns:
                for _, row in df.iterrows():
                    granule = str(row["Granule Name"]).strip()
                    try:
                        size_mb = float(str(row["Size (MB)"]).strip())
                        asf_sizes[granule] = size_mb
                    except ValueError:
                        pass
        except Exception as e:
            logger.error(f"Error reading ASF CSV {csv_file}: {e}")

    return asf_sizes


def verify_downloads(
    raw_dir: Path,
    metadata_dir: Path,
    output_csv: Path
) -> pd.DataFrame:
    """Verifies all NISAR observations in raw_dir against catalog and metadata."""
    logger.info(f"Scanning raw data directory: {raw_dir}")
    asf_catalog_sizes = load_asf_metadata(metadata_dir)

    records = []

    for obs in CATALOG_OBSERVATIONS:
        fname = obs["filename"]
        target_path = raw_dir / fname
        granule = obs["granule_name"]
        expected_mb = asf_catalog_sizes.get(granule, obs["expected_mb_asf"])

        logger.info(f"--- Verifying observation: {obs['date']} ({fname}) ---")

        if not target_path.exists():
            logger.error(f"CRITICAL: Target file does not exist: {target_path}")
            records.append({
                "granule_id": granule,
                "target_filename": fname,
                "file_path": str(target_path),
                "file_exists": False,
                "size_bytes": 0,
                "size_mb_decimal": 0.0,
                "size_gib_binary": 0.0,
                "asf_expected_size_mb": expected_mb,
                "size_diff_mb": -expected_mb,
                "size_match_flag": False,
                "sha256": "N/A",
                "h5py_readable": False,
                "root_groups": "N/A",
                "has_identification": False,
                "has_gcov_grids": False,
                "probe_freqA_HHHH_read": False,
                "probe_freqA_HVHV_read": False,
                "verification_status": "MISSING_FILE",
                "error_message": "File not found on disk"
            })
            continue

        # File exists
        size_bytes = target_path.stat().st_size
        size_mb_dec = size_bytes / 1e6
        size_gib = size_bytes / (1024 ** 3)
        size_diff = size_mb_dec - expected_mb
        # Check size agreement within 0.01 MB tolerance (due to decimal rounding in ASF table)
        size_match = abs(size_diff) < 0.05

        logger.info(f"File size: {size_bytes} bytes | {size_mb_dec:.2f} MB (decimal) | {size_gib:.2f} GiB")
        logger.info(f"ASF Catalog Size: {expected_mb:.2f} MB | Delta: {size_diff:+.4f} MB")

        # Checksum
        logger.info(f"Computing SHA-256 for {fname}...")
        sha256_hash = compute_sha256(target_path)
        logger.info(f"SHA-256: {sha256_hash}")

        # HDF5 Integrity
        logger.info(f"Validating HDF5 internal container structure for {fname}...")
        h5_check = test_hdf5_integrity(target_path)

        # Determine overall verification status
        is_verified = (
            size_match and
            h5_check["h5py_readable"] and
            h5_check["has_identification"] and
            h5_check["has_gcov_grids"] and
            h5_check["probe_read_freqA_HHHH"] and
            h5_check["probe_read_freqA_HVHV"] and
            h5_check["integrity_error"] is None
        )

        status_str = "VERIFIED_VALID" if is_verified else "CORRUPTED_OR_INCOMPLETE"

        records.append({
            "granule_id": granule,
            "target_filename": fname,
            "file_path": str(target_path.resolve()),
            "file_exists": True,
            "size_bytes": size_bytes,
            "size_mb_decimal": round(size_mb_dec, 2),
            "size_gib_binary": round(size_gib, 4),
            "asf_expected_size_mb": round(expected_mb, 2),
            "size_diff_mb": round(size_diff, 4),
            "size_match_flag": size_match,
            "sha256": sha256_hash,
            "h5py_readable": h5_check["h5py_readable"],
            "root_groups": ";".join(h5_check["root_groups"]),
            "has_identification": h5_check["has_identification"],
            "has_gcov_grids": h5_check["has_gcov_grids"],
            "probe_freqA_HHHH_read": h5_check["probe_read_freqA_HHHH"],
            "probe_freqA_HVHV_read": h5_check["probe_read_freqA_HVHV"],
            "verification_status": status_str,
            "error_message": h5_check["integrity_error"] or "None"
        })

    df_results = pd.DataFrame(records)
    metadata_dir.mkdir(parents=True, exist_ok=True)
    df_results.to_csv(output_csv, index=False)
    logger.info(f"Verification completed. Report written to {output_csv}")
    return df_results


def main():
    repo_root = Path(__file__).resolve().parents[2]
    raw_dir = repo_root / "datasets" / "raw"
    metadata_dir = raw_dir / "metadata"
    output_csv = metadata_dir / "download_verification.csv"

    df = verify_downloads(raw_dir, metadata_dir, output_csv)
    print("\n" + "=" * 80)
    print("DOWNLOAD VERIFICATION SUMMARY:")
    print("=" * 80)
    for _, r in df.iterrows():
        print(f"File: {r['target_filename']}")
        print(f"  Status       : {r['verification_status']}")
        print(f"  Size (Bytes) : {r['size_bytes']:,} ({r['size_mb_decimal']} MB / {r['size_gib_binary']} GiB)")
        print(f"  ASF Match    : {r['size_match_flag']} (diff: {r['size_diff_mb']} MB)")
        print(f"  SHA-256      : {r['sha256']}")
        print(f"  H5 Readable  : {r['h5py_readable']} (Identification: {r['has_identification']}, Grids: {r['has_gcov_grids']})")
        print(f"  Error        : {r['error_message']}")
        print("-" * 80)


if __name__ == "__main__":
    main()
