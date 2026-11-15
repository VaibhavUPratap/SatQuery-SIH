#!/usr/bin/env python3
"""Analyze and visualize temporal change between the two Bengaluru GCOV dates.

The script writes only derived products below ``change_analysis``. Original
Phase 2 measurement and mask GeoTIFFs are opened read-only and never changed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap

LOG = logging.getLogger("nisar_temporal_changes")
DATES = ("20261029", "20261110")
POLARIZATIONS = ("HH", "HV")
EXPECTED_SHAPE = (3920, 4382)
EXPECTED_CRS = "EPSG:32643"
PERCENTILES = (1, 2.5, 5, 25, 50, 75, 95, 97.5, 99)


def paths(base: Path, polarization: str, date: str) -> dict[str, Path]:
    pol = polarization.lower()
    return {
        "measurement": base / f"nisar_{pol}_{date}.tif",
        "quality": base / "masks" / f"quality_mask_{date}.tif",
        "exception": base / "masks" / f"exception_mask_{date}.tif",
    }


def validate_inputs(base: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], Any]:
    inputs: dict[tuple[str, str], dict[str, Any]] = {}
    reference = None
    for date in DATES:
        for polarization in POLARIZATIONS:
            p = paths(base, polarization, date)
            for kind, path in p.items():
                if not path.is_file():
                    raise FileNotFoundError(path)
                with rasterio.open(path) as src:
                    geometry = (src.crs, src.shape, src.transform, src.bounds, src.res)
                    if reference is None:
                        reference = geometry
                    if geometry != reference:
                        raise ValueError(f"Incompatible grid in {path}")
                    if src.crs != rasterio.crs.CRS.from_string(EXPECTED_CRS):
                        raise ValueError(f"Unexpected CRS in {path}: {src.crs}")
                    if src.shape != EXPECTED_SHAPE:
                        raise ValueError(f"Unexpected dimensions in {path}: {src.shape}")
                    if kind == "measurement":
                        tags = src.tags()
                        if "MEASUREMENT_UNITS" not in tags or "linear power" not in tags["MEASUREMENT_UNITS"]:
                            raise ValueError(f"Missing linear-power metadata in {path}")
            inputs[(date, polarization)] = p
    LOG.info("Validated four measurements and eight aligned mask references")
    return inputs, reference


def read_common_data(item: dict[str, Path], polarization: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with rasterio.open(item["measurement"]) as src:
        before = src.read(1).astype(np.float32, copy=False)
    with rasterio.open(item["quality"]) as src:
        quality = src.read(1)
    with rasterio.open(item["exception"]) as src:
        exception = src.read(1)
    required_bit = 256 if polarization == "HH" else 512
    valid = (
        np.isfinite(before)
        & (before > 0)
        & (quality != 0)
        & (quality != 255)
        & (exception != 65535)
        & ((exception & required_bit) != 0)
        & ((exception & 2) == 0)
    )
    return before, valid, exception


def write_derived(path: Path, data: np.ndarray, profile: dict[str, Any], tags: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output_profile = profile.copy()
    output_profile.update(dtype=str(data.dtype), nodata=np.nan if np.issubdtype(data.dtype, np.floating) else 255)
    with rasterio.open(path, "w", **output_profile) as dst:
        dst.write(data, 1)
        dst.update_tags(**tags)


def stats_row(date: str, polarization: str, values: np.ndarray, valid: np.ndarray) -> dict[str, Any]:
    selected = values[valid]
    percentiles = np.percentile(selected, PERCENTILES)
    row: dict[str, Any] = {
        "date": date,
        "polarization": polarization,
        "total_pixels": int(values.size),
        "valid_pixel_count": int(selected.size),
        "invalid_pixel_count": int(values.size - selected.size),
        "valid_percentage": float(100 * selected.size / values.size),
        "minimum": float(np.min(selected)),
        "maximum": float(np.max(selected)),
        "mean": float(np.mean(selected, dtype=np.float64)),
        "median": float(np.median(selected)),
        "standard_deviation": float(np.std(selected, dtype=np.float64)),
    }
    row.update({f"percentile_{str(p).replace('.', '_')}": float(v) for p, v in zip(PERCENTILES, percentiles)})
    return row


def neighborhood_count(candidate: np.ndarray) -> np.ndarray:
    padded = np.pad(candidate.astype(np.uint8), 1, mode="constant")
    count = np.zeros(candidate.shape, dtype=np.uint8)
    for row_offset in range(3):
        for col_offset in range(3):
            count += padded[row_offset:row_offset + candidate.shape[0], col_offset:col_offset + candidate.shape[1]]
    return count


def analyze_polarization(
    base: Path,
    output: Path,
    polarization: str,
    inputs: dict[tuple[str, str], dict[str, Path]],
    profile: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    values: dict[str, np.ndarray] = {}
    valid: dict[str, np.ndarray] = {}
    for date in DATES:
        values[date], valid[date], _ = read_common_data(inputs[(date, polarization)], polarization)
    common = valid[DATES[0]] & valid[DATES[1]]
    october = values[DATES[0]]
    november = values[DATES[1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        october_db = (10 * np.log10(october)).astype(np.float32)
        november_db = (10 * np.log10(november)).astype(np.float32)
        difference_db = (november_db - october_db).astype(np.float32)
        ratio = (november / october).astype(np.float32)
        percentage = ((ratio - 1) * 100).astype(np.float32)
    for array in (october_db, november_db, difference_db, ratio, percentage):
        array[~common] = np.nan

    common_difference = difference_db[common]
    median_difference = float(np.median(common_difference))
    mad = float(np.median(np.abs(common_difference - median_difference)))
    scaled_mad = 1.4826 * mad
    percentile_low, percentile_high = np.percentile(common_difference, [2.5, 97.5])
    threshold = max(3 * scaled_mad, np.finfo(np.float32).eps)
    candidate = common & (np.abs(difference_db - median_difference) > threshold)
    coherent = candidate & (neighborhood_count(candidate) >= 5)
    potential_mask = np.full(common.shape, 255, dtype=np.uint8)
    potential_mask[common] = 0
    potential_mask[coherent & (difference_db < median_difference)] = 1
    potential_mask[coherent & (difference_db > median_difference)] = 2

    tags = {
        "PRODUCT": "NISAR temporal change analysis",
        "POLARIZATION": polarization,
        "INPUT_DATES": "2026-10-29,2026-11-10",
        "COMMON_VALID_MASK": "quality mask valid; required polarization bit set; exception bit 2 clear; finite positive measurements",
        "CHANGE_DEFINITION": "November minus October",
        "ANOMALY_METHOD": "absolute dB difference from median exceeds 3 scaled MAD and has at least 5 of 9 candidate pixels in a 3x3 neighborhood",
        "INVALID_VALUE": "NaN for floating products; 255 for potential-change mask",
    }
    write_derived(output / f"{polarization.lower()}_20261029_db.tif", october_db, profile, {**tags, "PRODUCT_TYPE": "October gamma0 dB"})
    write_derived(output / f"{polarization.lower()}_20261110_db.tif", november_db, profile, {**tags, "PRODUCT_TYPE": "November gamma0 dB"})
    write_derived(output / f"{polarization.lower()}_difference_db.tif", difference_db, profile, {**tags, "PRODUCT_TYPE": "dB difference"})
    write_derived(output / f"{polarization.lower()}_change_ratio.tif", ratio, profile, {**tags, "PRODUCT_TYPE": "linear power ratio November/October"})
    write_derived(output / f"{polarization.lower()}_percentage_change.tif", percentage, profile, {**tags, "PRODUCT_TYPE": "linear power percentage change"})
    write_derived(output / f"{polarization.lower()}_potential_change_mask.tif", potential_mask, profile, {**tags, "PRODUCT_TYPE": "potential change mask; 0=no detected change, 1=decrease, 2=increase"})

    stats = [stats_row(date, polarization, values[date], valid[date]) for date in DATES]
    summary = {
        "polarization": polarization,
        "common_valid_pixel_count": int(common.sum()),
        "common_invalid_pixel_count": int(common.size - common.sum()),
        "common_valid_percentage": float(100 * common.sum() / common.size),
        "difference_db_median": median_difference,
        "difference_db_mad": mad,
        "difference_db_scaled_mad": scaled_mad,
        "distribution_p2_5_db": float(percentile_low),
        "distribution_p97_5_db": float(percentile_high),
        "robust_threshold_db": float(threshold),
        "distribution_tail_count_db": int(((common_difference < percentile_low) | (common_difference > percentile_high)).sum()),
        "potential_change_pixel_count": int(coherent.sum()),
        "potential_change_percentage_of_common": float(100 * coherent.sum() / common.sum()),
        "potential_decrease_pixels": int((potential_mask == 1).sum()),
        "potential_increase_pixels": int((potential_mask == 2).sum()),
    }
    return summary, stats


def visualize(
    output: Path,
    polarization: str,
    arrays: dict[str, np.ndarray],
    valid: np.ndarray,
    summary: dict[str, Any],
) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    low, high = (-20, 10) if polarization == "HH" else (-28, -4)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for axis, date in zip(axes, DATES):
        image = np.ma.masked_invalid(arrays[f"{date}_db"])
        axis.imshow(image, cmap="gray", vmin=low, vmax=high)
        axis.set_title(f"{polarization} {date[:4]}-{date[4:6]}-{date[6:]} gamma0 dB")
        axis.set_axis_off()
    fig.savefig(figures / f"{polarization.lower()}_october_vs_november.png", dpi=150)
    plt.close(fig)

    difference = np.ma.masked_invalid(arrays["difference_db"])
    limit = max(abs(float(np.percentile(difference.compressed(), [1, 99])[0])), abs(float(np.percentile(difference.compressed(), [1, 99])[1])))
    fig, axis = plt.subplots(figsize=(8, 6), constrained_layout=True)
    image = axis.imshow(difference, cmap="RdBu_r", vmin=-limit, vmax=limit)
    axis.set_title(f"{polarization} temporal difference (Nov - Oct), dB")
    axis.set_axis_off()
    fig.colorbar(image, ax=axis, label="dB; blue=decrease, red=increase")
    fig.savefig(figures / f"{polarization.lower()}_difference_db.png", dpi=150)
    plt.close(fig)

    mask = arrays["potential_mask"].copy().astype(float)
    mask[mask == 255] = np.nan
    fig, axis = plt.subplots(figsize=(8, 6), constrained_layout=True)
    image = axis.imshow(np.ma.masked_invalid(mask), cmap=ListedColormap(["#d9d9d9", "#2166ac", "#b2182b"]), vmin=0, vmax=2)
    axis.set_title(f"{polarization} potential change regions (robust + spatial test)")
    axis.set_axis_off()
    colorbar = fig.colorbar(image, ax=axis, ticks=[0, 1, 2])
    colorbar.ax.set_yticklabels(["No detected change", "Decrease", "Increase"])
    fig.savefig(figures / f"{polarization.lower()}_potential_change.png", dpi=150)
    plt.close(fig)

    common = valid
    fig, axis = plt.subplots(figsize=(9, 6), constrained_layout=True)
    axis.hist(arrays[f"{DATES[0]}_db"][common], bins=160, density=True, alpha=0.5, label="2026-10-29")
    axis.hist(arrays[f"{DATES[1]}_db"][common], bins=160, density=True, alpha=0.5, label="2026-11-10")
    axis.set_title(f"{polarization} gamma0 dB distributions on common valid pixels")
    axis.set_xlabel("gamma0 (dB)")
    axis.set_ylabel("Density")
    axis.legend()
    fig.savefig(figures / f"{polarization.lower()}_statistical_distributions.png", dpi=150)
    plt.close(fig)
    LOG.info("Generated figures for %s; robust threshold %.3f dB", polarization, summary["robust_threshold_db"])


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = Path(__file__).resolve().parents[2]
    base = root / "datasets" / "processed" / "bengaluru"
    output = base / "change_analysis"
    inputs, geometry = validate_inputs(base)
    profile = {
        "driver": "GTiff",
        "height": EXPECTED_SHAPE[0],
        "width": EXPECTED_SHAPE[1],
        "count": 1,
        "crs": geometry[0],
        "transform": geometry[2],
        "tiled": True,
        "blockxsize": 512,
        "blockysize": 512,
        "compress": "deflate",
    }
    summaries: list[dict[str, Any]] = []
    stats: list[dict[str, Any]] = []
    for polarization in POLARIZATIONS:
        summary, rows = analyze_polarization(base, output, polarization, inputs, profile)
        summaries.append(summary)
        stats.extend(rows)
        # Re-read derived products for plotting, keeping visualization independent of write buffers.
        arrays: dict[str, np.ndarray] = {}
        for date in DATES:
            with rasterio.open(output / f"{polarization.lower()}_{date}_db.tif") as src:
                arrays[f"{date}_db"] = src.read(1)
        with rasterio.open(output / f"{polarization.lower()}_difference_db.tif") as src:
            arrays["difference_db"] = src.read(1)
        with rasterio.open(output / f"{polarization.lower()}_potential_change_mask.tif") as src:
            arrays["potential_mask"] = src.read(1)
        valid = np.isfinite(arrays["difference_db"])
        visualize(output, polarization, arrays, valid, summary)
    pd.DataFrame(stats).to_csv(output / "temporal_statistics.csv", index=False)
    (output / "change_summary.json").write_text(json.dumps(summaries, indent=2) + "\n")
    LOG.info("Temporal analysis complete: %s", output)


if __name__ == "__main__":
    main()
