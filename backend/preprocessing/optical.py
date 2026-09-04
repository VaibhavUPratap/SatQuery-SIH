import cv2
import numpy as np


def load_optical_rgb(image_path: str) -> tuple[np.ndarray, dict]:
    """Load an RGB image or GeoTIFF as uint8 BGR plus modality metadata."""
    if image_path.lower().endswith((".tif", ".tiff")):
        import rasterio
        with rasterio.open(image_path) as source:
            data = source.read(out_dtype="float32")
            descriptions = tuple((item or "").upper() for item in source.descriptions)
        if data.shape[0] >= 3 and all(name in descriptions for name in ("B02", "B03", "B04")):
            channels = [data[descriptions.index(name)] for name in ("B04", "B03", "B02")]
            modality = "sentinel2_multispectral"
        elif data.shape[0] >= 3:
            channels = [data[0], data[1], data[2]]
            modality = "rgb_geotiff"
        else:
            raise ValueError("Optical input must contain RGB channels or Sentinel-2 B02/B03/B04 bands.")
        return _normalize_channels(channels), {"modality": modality, "bands": data.shape[0], "band_descriptions": descriptions}
    image = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Could not read optical image: {image_path}")
    return image, {"modality": "rgb", "bands": 3}


def load_sar_intensity(image_path: str) -> tuple[np.ndarray, dict]:
    """Load single-band/VV/VH SAR GeoTIFF or an image proxy as float32 intensity."""
    if image_path.lower().endswith((".tif", ".tiff")):
        import rasterio
        with rasterio.open(image_path) as source:
            data = source.read(out_dtype="float32")
            descriptions = tuple((item or "").upper() for item in source.descriptions)
        if not np.isfinite(data).all():
            raise ValueError("SAR input contains NaN or infinite values.")
        if "VV" in descriptions:
            index = descriptions.index("VV")
        elif "VH" in descriptions:
            index = descriptions.index("VH")
        else:
            if data.shape[0] >= 3:
                return _normalize_channels([data[0], data[1], data[2]]), {"modality": "rgb_geotiff", "bands": data.shape[0], "band_descriptions": descriptions}
            index = 0
        return data[index], {"modality": "sar_geotiff", "bands": data.shape[0], "band_descriptions": descriptions}
    image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not read SAR image: {image_path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.astype(np.float32), {"modality": "sar_image_proxy", "bands": 1}


def _normalize_channels(channels: list[np.ndarray]) -> np.ndarray:
    normalized = []
    for channel in channels:
        low, high = np.percentile(channel, (2, 98))
        if high <= low:
            high = low + 1
        normalized.append(np.clip((channel - low) * 255 / (high - low), 0, 255).astype(np.uint8))
    return cv2.merge(normalized)


def normalize_sar_backscatter(sar_image: np.ndarray) -> np.ndarray:
    """Denoise and robustly normalize a SAR image to an 8-bit intensity map."""
    if sar_image.ndim == 3:
        sar_image = cv2.cvtColor(sar_image, cv2.COLOR_BGR2GRAY)

    filtered = cv2.medianBlur(sar_image, 3)
    low, high = np.percentile(filtered, (2, 98))
    if high <= low:
        return np.zeros_like(filtered, dtype=np.uint8)
    normalized = (filtered.astype(np.float32) - low) * (255.0 / (high - low))
    return np.clip(normalized, 0, 255).astype(np.uint8)
