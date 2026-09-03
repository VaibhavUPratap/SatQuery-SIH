import os
import re
from typing import Dict, Any, Tuple
from PIL import Image

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False

try:
    import numpy as np
except ImportError:
    np = None

from backend.config import settings


class InputValidator:
    """
    Validates uploaded satellite images for format, resolution,
    channels/bands, and geospatial metadata with sensor/polarization detection.
    """
    
    SUPPORTED_FORMATS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}

    @classmethod
    def detect_sensor_and_modality(cls, file_name: str, bands: int, descriptions: tuple = ()) -> Tuple[str, str, str | None]:
        """Detect sensor family, modality (Optical/SAR), and polarization from metadata/filename."""
        name_lower = file_name.lower()
        desc_joined = " ".join((d or "").upper() for d in descriptions)
        
        polarization = None
        if "VV" in desc_joined and "VH" in desc_joined:
            polarization = "VV+VH Dual-Pol"
        elif "VV" in desc_joined:
            polarization = "VV"
        elif "VH" in desc_joined:
            polarization = "VH"
        elif any(k in name_lower for k in ("_sar", "-sar", "sar_", "sar.", "sentinel1", "sentinel-1", "s1_")):
            polarization = "Intensity / Backscatter"

        is_sar = (
            any(k in name_lower for k in ("sentinel1", "sentinel-1", "sentinel_1", "s1", "sar", "risat"))
            or polarization is not None
        )
        if is_sar:
            sensor = "Sentinel-1 SAR" if any(k in name_lower for k in ("sentinel1", "sentinel-1", "s1", "sentinel")) else "SAR Sensor"
            modality = "SAR"
            return sensor, modality, polarization or "Single-Pol (Backscatter)"

        is_s2 = (
            bands == 12
            or any(k in name_lower for k in ("sentinel2", "sentinel-2", "sentinel_2", "s2", "msi"))
        )
        if is_s2:
            sensor = "Sentinel-2 MSI"
            modality = "Optical (Multispectral)" if bands > 4 else "Optical"
            return sensor, modality, None

        if bands in (3, 4):
            sensor = "Optical Sensor"
            modality = "Optical"
            return sensor, modality, None

        return "Earth Observation Sensor", "Optical/SAR", polarization

    @classmethod
    def extract_acquisition_date(cls, file_name: str, img: Any = None) -> str | None:
        """Extract acquisition date from filename pattern (e.g. YYYYMMDD) or TIFF metadata."""
        match = re.search(r"(20\d{2})[-_]?(\d{2})[-_]?(\d{2})", file_name)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
        
        if img and hasattr(img, "tag_v2"):
            date_tag = img.tag_v2.get(306)
            if date_tag and isinstance(date_tag, str) and len(date_tag) >= 10:
                parts = date_tag[:10].replace(":", "-").split("-")
                if len(parts) == 3:
                    return f"{parts[0]}-{parts[1]}-{parts[2]}"

        return None

    @classmethod
    def validate_image(cls, file_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates the format and dimensions of the input image and extracts rich metadata.
        
        Args:
            file_path: Path to the image file.
            
        Returns:
            Tuple containing:
            - is_valid (bool)
            - error_message (str)
            - metadata (dict)
        """
        if not os.path.exists(file_path):
            return False, "File does not exist.", {}
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in cls.SUPPORTED_FORMATS:
            return False, f"Unsupported format '{ext}'. Supported formats: {', '.join(cls.SUPPORTED_FORMATS)}", {}

        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        metadata: Dict[str, Any] = {
            "file_name": file_name,
            "file_size_bytes": file_size,
            "format": ext[1:].upper(),
            "geospatial": False,
            "acquisition_date": cls.extract_acquisition_date(file_name),
        }

        # Try reading geospatial metadata with rasterio if format is TIFF/TIF
        if HAS_RASTERIO and ext in {".tif", ".tiff"}:
            try:
                with rasterio.open(file_path) as src:
                    metadata["width"] = src.width
                    metadata["height"] = src.height
                    metadata["bands"] = src.count
                    metadata["crs"] = str(src.crs) if src.crs else None
                    metadata["bounds"] = list(src.bounds) if src.bounds else None
                    metadata["transform"] = [float(x) for x in src.transform] if src.transform else None
                    metadata["geospatial"] = src.crs is not None
                    
                    descriptions = tuple(src.descriptions or ())
                    metadata["band_descriptions"] = [d for d in descriptions if d]

                    sensor, modality, pol = cls.detect_sensor_and_modality(file_name, src.count, descriptions)
                    metadata["sensor"] = sensor
                    metadata["modality"] = modality
                    if pol:
                        metadata["polarization"] = pol

                    if src.width * src.height > settings.MAX_IMAGE_PIXELS:
                        return False, "Image dimensions exceed the configured pixel limit.", metadata
                    if np is not None:
                        sample = src.read()
                        if not np.isfinite(sample).all():
                            return False, "Image contains NaN or infinite pixel values.", metadata
                    return True, "", metadata
            except Exception:
                pass

        # Fallback/standard image reading using PIL
        try:
            with Image.open(file_path) as img:
                bands = len(img.getbands())
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["bands"] = bands
                metadata["mode"] = img.mode
                
                date = cls.extract_acquisition_date(file_name, img)
                if date:
                    metadata["acquisition_date"] = date

                sensor, modality, pol = cls.detect_sensor_and_modality(file_name, bands)
                metadata["sensor"] = sensor
                metadata["modality"] = modality
                if pol:
                    metadata["polarization"] = pol

                if img.width * img.height > settings.MAX_IMAGE_PIXELS:
                    return False, "Image dimensions exceed the configured pixel limit.", metadata
                
                if hasattr(img, "tag_v2"):
                    if 33550 in img.tag_v2 or 33922 in img.tag_v2:
                        metadata["geospatial"] = True
                
                return True, "", metadata
        except Exception as e:
            return False, f"Invalid or corrupted image: {str(e)}", {}
