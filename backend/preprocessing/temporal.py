"""Image loading helpers for temporal change analysis."""
from __future__ import annotations

import os
from typing import Any

import cv2
import numpy as np


def load_temporal_rgb(image_path: str) -> np.ndarray:
    """Load RGB/JPEG/PNG or Sentinel-2 GeoTIFF data as uint8 BGR for OpenCV."""
    extension = os.path.splitext(image_path)[1].lower()
    if extension in {".tif", ".tiff"}:
        try:
            import rasterio
        except ImportError as exc:
            raise RuntimeError("GeoTIFF temporal analysis requires rasterio.") from exc

        with rasterio.open(image_path) as source:
            data = source.read(out_dtype="float32")
            descriptions = tuple((item or "").upper() for item in source.descriptions)

        if data.ndim != 3 or data.shape[0] < 1:
            raise ValueError("Temporal GeoTIFF must contain at least one raster band.")
        if not np.isfinite(data).all():
            raise ValueError("Temporal GeoTIFF contains NaN or infinite values.")

        if data.shape[0] >= 3 and all(name in descriptions for name in ("B02", "B03", "B04")):
            channels = [data[descriptions.index(name)] for name in ("B04", "B03", "B02")]
        elif data.shape[0] >= 3:
            channels = [data[0], data[1], data[2]]
        else:
            channels = [data[0], data[0], data[0]]

        rgb = np.stack([_normalize_channel(channel) for channel in channels], axis=-1)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read image at path {image_path}")
    return image


def _normalize_channel(channel: np.ndarray) -> np.ndarray:
    """Robustly scale reflectance or arbitrary numeric data to display bytes."""
    low, high = np.percentile(channel, (2, 98))
    if high <= low:
        low, high = float(channel.min()), float(channel.max())
    if high <= low:
        return np.zeros(channel.shape, dtype=np.uint8)
    scaled = (channel - low) / (high - low)
    return np.clip(scaled * 255.0, 0, 255).astype(np.uint8)
