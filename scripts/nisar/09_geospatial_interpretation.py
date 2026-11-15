#!/usr/bin/env python3
"""Geospatially summarize Phase 3 candidate regions without inventing context."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.features import rasterize, shapes
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape
from shapely.ops import transform as transform_geometry
from pyproj import Transformer

LOG = logging.getLogger("nisar_geospatial_interpretation")
CRS = "EPSG:32643"
WGS84 = "EPSG:4326"
POLARIZATIONS = ("HH", "HV")
AOI_BOUNDS = (760170.0, 1416220.0, 803990.0, 1455420.0)


def polygonize(base: Path, polarization: str, output: Path) -> list[dict[str, Any]]:
    mask_path = base / f"{polarization.lower()}_potential_change_mask.tif"
    difference_path = base / f"{polarization.lower()}_difference_db.tif"
    with rasterio.open(mask_path) as mask_src, rasterio.open(difference_path) as diff_src:
        mask = mask_src.read(1)
        difference = diff_src.read(1)
        if mask_src.crs != rasterio.crs.CRS.from_string(CRS) or diff_src.crs != mask_src.crs:
            raise ValueError(f"Unexpected CRS for {polarization} candidate inputs")
        if mask_src.transform != diff_src.transform or mask_src.shape != diff_src.shape:
            raise ValueError(f"Candidate mask and difference grid mismatch for {polarization}")
        transform = mask_src.transform

    transformer = Transformer.from_crs(CRS, WGS84, always_xy=True)
    features: list[dict[str, Any]] = []
    region_id = 1
    for class_value, direction in ((1, "decrease"), (2, "increase")):
        class_mask = mask == class_value
        for geometry_json, value in shapes(mask.astype(np.uint8), mask=class_mask, transform=transform):
            if int(value) != class_value:
                continue
            geometry = shape(geometry_json)
            window = from_bounds(*geometry.bounds, transform=transform).round_offsets().round_lengths()
            row_start, col_start = int(window.row_off), int(window.col_off)
            height, width = int(window.height), int(window.width)
            local_transform = rasterio.windows.transform(window, transform)
            local_region = rasterize(
                [(geometry_json, 1)],
                out_shape=(height, width),
                transform=local_transform,
                fill=0,
                dtype="uint8",
            ).astype(bool)
            window_values = difference[row_start:row_start + height, col_start:col_start + width][local_region]
            if window_values.size == 0:
                continue
            centroid_x, centroid_y = geometry.centroid.x, geometry.centroid.y
            centroid_lon, centroid_lat = transformer.transform(centroid_x, centroid_y)
            projected_area_m2 = geometry.area
            properties = {
                "region_id": f"{polarization}_{region_id:05d}",
                "polarization": polarization,
                "direction": direction,
                "pixel_count": int(window_values.size),
                "area_m2": float(projected_area_m2),
                "area_hectares": float(projected_area_m2 / 10000),
                "area_km2": float(projected_area_m2 / 1_000_000),
                "mean_difference_db": float(np.mean(window_values)),
                "minimum_difference_db": float(np.min(window_values)),
                "maximum_difference_db": float(np.max(window_values)),
                "centroid_easting_m": float(centroid_x),
                "centroid_northing_m": float(centroid_y),
                "centroid_longitude": float(centroid_lon),
                "centroid_latitude": float(centroid_lat),
                "land_cover_status": "not_assessed_external_data_unavailable",
            }
            features.append({"type": "Feature", "geometry": mapping(geometry), "properties": properties})
            region_id += 1

    collection = {
        "type": "FeatureCollection",
        "name": f"{polarization}_candidate_change_regions",
        "crs": {"type": "name", "properties": {"name": CRS}},
        "features": features,
    }
    output.write_text(json.dumps(collection) + "\n")
    LOG.info("Wrote %d %s candidate polygons to %s", len(features), polarization, output)
    return features


def write_summary(features: list[dict[str, Any]], output: Path) -> None:
    rows = [feature["properties"] for feature in features]
    if not rows:
        output.write_text("polarization,direction,region_count,pixel_count,area_hectares,area_km2\n")
        return
    import pandas as pd

    frame = pd.DataFrame(rows)
    summary = (
        frame.groupby(["polarization", "direction"], as_index=False)
        .agg(
            region_count=("region_id", "count"),
            pixel_count=("pixel_count", "sum"),
            area_hectares=("area_hectares", "sum"),
            area_km2=("area_km2", "sum"),
            mean_of_region_mean_difference_db=("mean_difference_db", "mean"),
            minimum_difference_db=("minimum_difference_db", "min"),
            maximum_difference_db=("maximum_difference_db", "max"),
        )
    )
    summary.to_csv(output, index=False)


def add_map_decorations(axis: Any) -> None:
    axis.set_xlabel("Easting (m)")
    axis.set_ylabel("Northing (m)")
    axis.add_patch(plt.Rectangle((AOI_BOUNDS[0], AOI_BOUNDS[1]), AOI_BOUNDS[2] - AOI_BOUNDS[0], AOI_BOUNDS[3] - AOI_BOUNDS[1], fill=False, edgecolor="black", linewidth=1.2, label="AOI bounds"))
    scale_x = AOI_BOUNDS[0] + 1000
    scale_y = AOI_BOUNDS[1] + 1000
    axis.plot([scale_x, scale_x + 10000], [scale_y, scale_y], color="black", linewidth=3)
    axis.text(scale_x + 5000, scale_y + 500, "10 km", ha="center", va="bottom", color="black")
    axis.annotate("N", xy=(0.97, 0.90), xytext=(0.97, 0.78), xycoords="axes fraction", ha="center", arrowprops={"arrowstyle": "-|>", "color": "black"})


def make_maps(base: Path, output: Path, collections: dict[str, list[dict[str, Any]]]) -> None:
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    for axis, polarization in zip(axes, POLARIZATIONS):
        with rasterio.open(base / f"{polarization.lower()}_difference_db.tif") as src:
            difference = src.read(1)
            bounds = src.bounds
        finite = difference[np.isfinite(difference)]
        limit = max(abs(float(np.percentile(finite, 1))), abs(float(np.percentile(finite, 99))))
        image = axis.imshow(difference, extent=(bounds.left, bounds.right, bounds.bottom, bounds.top), origin="upper", cmap="RdBu_r", vmin=-limit, vmax=limit)
        increase_x, increase_y = [], []
        decrease_x, decrease_y = [], []
        for feature in collections[polarization]:
            centroid = shape(feature["geometry"]).centroid
            if feature["properties"]["direction"] == "increase":
                increase_x.append(centroid.x)
                increase_y.append(centroid.y)
            else:
                decrease_x.append(centroid.x)
                decrease_y.append(centroid.y)
        axis.scatter(decrease_x, decrease_y, s=5, c="#2166ac", label="Candidate decrease")
        axis.scatter(increase_x, increase_y, s=5, c="#b2182b", label="Candidate increase")
        axis.set_title(f"{polarization} dB difference and candidate locations\nNo verified external land-cover layer loaded")
        add_map_decorations(axis)
        axis.legend(loc="lower right", fontsize=8)
        fig.colorbar(image, ax=axis, label="November - October (dB)")
    fig.savefig(figures / "candidate_change_geospatial_maps.png", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7), constrained_layout=True)
    for axis, polarization in zip(axes, POLARIZATIONS):
        with rasterio.open(base / f"{polarization.lower()}_potential_change_mask.tif") as src:
            mask = src.read(1).astype(float)
            bounds = src.bounds
        mask[mask == 255] = np.nan
        image = axis.imshow(mask, extent=(bounds.left, bounds.right, bounds.bottom, bounds.top), origin="upper", cmap=ListedColormap(["#d9d9d9", "#2166ac", "#b2182b"]), vmin=0, vmax=2)
        axis.set_title(f"{polarization} candidate regions\nUrban/agriculture/vegetation/water: not classified")
        add_map_decorations(axis)
        colorbar = fig.colorbar(image, ax=axis, ticks=[0, 1, 2])
        colorbar.ax.set_yticklabels(["No candidate", "Decrease", "Increase"])
    fig.savefig(figures / "candidate_change_context_status.png", dpi=180)
    plt.close(fig)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    root = Path(__file__).resolve().parents[2]
    base = root / "datasets" / "processed" / "bengaluru" / "change_analysis"
    output = base / "geospatial_interpretation"
    output.mkdir(parents=True, exist_ok=True)
    all_features: dict[str, list[dict[str, Any]]] = {}
    combined_features: list[dict[str, Any]] = []
    for polarization in POLARIZATIONS:
        features = polygonize(base, polarization, output / f"{polarization.lower()}_candidate_change_regions_epsg32643.geojson")
        all_features[polarization] = features
        combined_features.extend(features)
    write_summary(combined_features, output / "candidate_area_summary.csv")
    (output / "data_context_status.json").write_text(json.dumps({
        "external_land_cover_data_loaded": False,
        "urban_agriculture_vegetation_water_overlap_assessed": False,
        "reason": "No verified Bengaluru-specific supporting dataset exists in the repository; unrelated raster footprints were excluded.",
        "candidate_crs": CRS,
        "candidate_locations_are_wgs84_properties": True,
    }, indent=2) + "\n")
    make_maps(base, output, all_features)
    LOG.info("Geospatial interpretation outputs complete: %s", output)


if __name__ == "__main__":
    main()
