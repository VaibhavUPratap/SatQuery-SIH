"""Optional, metadata-preserving inspection of local corroboration datasets."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import rasterio
from rasterio.warp import transform_bounds


DEFAULT_EXTERNAL_SOURCES = (
    ("Sentinel-2", "Optical vegetation, water, and built-surface context"),
    ("OpenStreetMap", "Buildings, roads, and infrastructure context"),
    ("NASA GPM IMERG", "Precipitation context"),
    ("NASA SMAP", "Soil-moisture context"),
    ("Land-cover", "Vegetation, urban, and water-body context"),
    ("Population", "Population exposure and urban-growth context"),
)


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _coordinate_bounds(value: Any) -> tuple[float, float, float, float] | None:
    points: list[tuple[float, float]] = []

    def visit(node: Any) -> None:
        if isinstance(node, (list, tuple)):
            if len(node) >= 2 and all(isinstance(item, (int, float)) for item in node[:2]):
                points.append((float(node[0]), float(node[1])))
            else:
                for child in node:
                    visit(child)

    visit(value)
    if not points:
        return None
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _overlaps(first: tuple[float, float, float, float], second: list[float]) -> bool:
    return (
        max(first[0], second[0]) < min(first[2], second[2])
        and max(first[1], second[1]) < min(first[3], second[3])
    )


def inspect_external_evidence(
    specifications: list[dict[str, Any]] | None,
    aoi_bbox: list[float] | None,
    allowed_roots: list[Path],
) -> dict[str, Any]:
    """Inspect explicitly supplied local datasets without downloading or inferring causes."""
    sources: list[dict[str, Any]] = [
        {"source": name, "purpose": purpose, "status": "not_verified", "reason": "No local source supplied."}
        for name, purpose in DEFAULT_EXTERNAL_SOURCES
    ]

    for specification in specifications or []:
        if not isinstance(specification, dict):
            raise ValueError("Each external source must be an object.")
        name = str(specification.get("source") or specification.get("name") or "").strip()
        raw_path = str(specification.get("path") or "").strip()
        if not name or not raw_path:
            raise ValueError("Each external source requires source and path.")

        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = allowed_roots[0] / path
        path = path.resolve()
        if not path.is_file() or not any(_within(path, root.resolve()) for root in allowed_roots):
            raise ValueError(f"External source '{name}' is not an existing file in an approved data root.")

        item: dict[str, Any] = {
            "source": name,
            "purpose": specification.get("purpose") or "User-supplied corroboration dataset",
            "source_date": specification.get("source_date"),
            "source_url": specification.get("source_url"),
            "path": path.name,
            "status": "available",
        }
        suffix = path.suffix.lower()
        if suffix in {".tif", ".tiff"}:
            with rasterio.open(path) as dataset:
                if dataset.crs is None:
                    item.update(status="unusable", reason="Raster has no CRS.")
                else:
                    bounds = tuple(dataset.bounds)
                    if aoi_bbox:
                        aoi_in_crs = transform_bounds("EPSG:4326", dataset.crs, *aoi_bbox, densify_pts=21)
                        item["coverage"] = "overlap" if _overlaps(bounds, list(aoi_in_crs)) else "outside_aoi"
                        if item["coverage"] == "outside_aoi":
                            item["status"] = "outside_aoi"
                    else:
                        item["coverage"] = "not_assessed"
                    item["crs"] = str(dataset.crs)
                    item["dimensions"] = [dataset.width, dataset.height]
        elif suffix in {".json", ".geojson"}:
            with path.open(encoding="utf-8") as handle:
                document = json.load(handle)
            coordinate_bounds = _coordinate_bounds(document.get("geometry", {}).get("coordinates") if document.get("type") == "Feature" else document.get("coordinates"))
            if coordinate_bounds and aoi_bbox:
                item["coverage"] = "overlap" if _overlaps(coordinate_bounds, aoi_bbox) else "outside_aoi"
                if item["coverage"] == "outside_aoi":
                    item["status"] = "outside_aoi"
            else:
                item["coverage"] = "not_assessed"
        else:
            item["coverage"] = "not_assessed"
            item["reason"] = "Metadata recorded; spatial coverage was not assessed for this file type."

        sources = [existing for existing in sources if existing["source"].lower() != name.lower()]
        sources.append(item)

    return {
        "status": "available" if any(item["status"] == "available" for item in sources) else "not_verified",
        "sources": sources,
        "causal_interpretation": "Unavailable: corroboration does not establish causality or confirm an environmental event.",
    }
