"""Download two real Sentinel-2 GeoTIFF visual assets for temporal smoke tests.

The script uses the public Earth Search STAC API and stores the source URLs in a
manifest. It is intended for test fixtures, not production data acquisition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests

STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"


def download_pair(output_dir: Path, bbox: list[float], start: str, end: str, size: int) -> None:
    datetime_range = f"{start}T00:00:00Z/{end}T23:59:59Z"
    response = requests.post(
        STAC_SEARCH,
        json={
            "collections": ["sentinel-2-l2a"],
            "bbox": bbox,
            "datetime": datetime_range,
            "limit": 20,
            "query": {"eo:cloud_cover": {"lt": 20}},
            "sortby": [{"field": "properties.datetime", "direction": "asc"}],
        },
        timeout=60,
    )
    response.raise_for_status()
    items = response.json().get("features", [])
    if len(items) < 2:
        raise RuntimeError("Fewer than two cloud-limited Sentinel-2 acquisitions were found.")

    # Prefer two dates far apart so the pair is useful for a smoke test.
    selected = [items[0]]
    for item in items[1:]:
        if item["properties"].get("datetime", "")[:10] != selected[0]["properties"].get("datetime", "")[:10]:
            selected.append(item)
            break
    if len(selected) < 2:
        selected = items[:2]

    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for index, item in enumerate(selected, start=1):
        visual = item.get("assets", {}).get("visual")
        if not visual or not visual.get("href"):
            raise RuntimeError("Selected Sentinel-2 item has no visual GeoTIFF asset.")
        target = output_dir / f"sentinel2_temporal_t{index}.tif"
        full_target = output_dir / f".full_{target.name}"
        with requests.get(visual["href"], stream=True, timeout=180) as download:
            download.raise_for_status()
            with full_target.open("wb") as handle:
                for chunk in download.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        handle.write(chunk)
        import rasterio
        from rasterio.windows import Window
        with rasterio.open(full_target) as source:
            width = min(size, source.width)
            height = min(size, source.height)
            window = Window(0, 0, width, height)
            profile = source.profile.copy()
            profile.update(width=width, height=height, transform=source.window_transform(window), compress="deflate")
            with rasterio.open(target, "w", **profile) as clipped:
                clipped.write(source.read(window=window))
        full_target.unlink()
        records.append({
            "file": target.name,
            "source_url": visual["href"],
            "scene_id": item.get("id"),
            "acquired": item["properties"].get("datetime"),
            "cloud_cover": item["properties"].get("eo:cloud_cover"),
        })

    (output_dir / "manifest.json").write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Downloaded {len(records)} real Sentinel-2 GeoTIFFs to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("datasets/real_temporal_tiffs"))
    parser.add_argument("--bbox", nargs=4, type=float, default=(-122.55, 37.70, -122.35, 37.85), metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"))
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2024-12-31")
    parser.add_argument("--size", type=int, default=512, help="Pixel width/height of the clipped test window.")
    args = parser.parse_args()
    if args.size < 64:
        parser.error("--size must be at least 64 pixels")
    download_pair(args.output_dir, list(args.bbox), args.start, args.end, args.size)
