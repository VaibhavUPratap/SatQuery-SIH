import os
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
    channels/bands, and geospatial metadata.
    """
    
    SUPPORTED_FORMATS = {".tif", ".tiff", ".png", ".jpg", ".jpeg"}

    @classmethod
    def validate_image(cls, file_path: str) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates the format and dimensions of the input image.
        
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

        metadata = {
            "file_name": os.path.basename(file_path),
            "file_size_bytes": os.path.getsize(file_path),
            "format": ext[1:].upper(),
            "geospatial": False
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
                    if src.width * src.height > settings.MAX_IMAGE_PIXELS:
                        return False, "Image dimensions exceed the configured pixel limit.", metadata
                    if np is not None:
                        sample = src.read()
                        if not np.isfinite(sample).all():
                            return False, "Image contains NaN or infinite pixel values.", metadata
                    return True, "", metadata
            except Exception as e:
                # If rasterio fails, fall back to standard PIL reader
                pass

        # Fallback/standard image reading using PIL
        try:
            with Image.open(file_path) as img:
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["bands"] = len(img.getbands())
                metadata["mode"] = img.mode
                if img.width * img.height > settings.MAX_IMAGE_PIXELS:
                    return False, "Image dimensions exceed the configured pixel limit.", metadata
                
                # Check for standard remote sensing TIFF tags without rasterio
                if hasattr(img, "tag_v2"):
                    # Check for typical GeoTIFF tags like ModelPixelScaleTag (33550) or ModelTiepointTag (33922)
                    if 33550 in img.tag_v2 or 33922 in img.tag_v2:
                        metadata["geospatial"] = True
                
                return True, "", metadata
        except Exception as e:
            return False, f"Invalid or corrupted image: {str(e)}", {}
