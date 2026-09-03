"""Input preparation for the RGB-only RSVQA BLIP LoRA adapter."""

from pathlib import Path
from PIL import Image

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


def load_rgb_image(image_path: str) -> Image.Image:
    """Load an RGB visualization compatible with the model's training inputs.

    The adapter was trained with ``PIL.Image.open(...).convert("RGB")`` on
    RSVQA imagery. It consequently accepts PNG/JPEG and RGB/RGBA TIFF images,
    but not raw multispectral or SAR tensors. The saved BLIP processor performs
    its own resize and normalization after this function returns.
    """
    path = Path(image_path)

    # Check multi-band GeoTIFFs using rasterio first to produce clean rejection messages
    if HAS_RASTERIO and path.suffix.lower() in {".tif", ".tiff"}:
        try:
            with rasterio.open(path) as src:
                if src.count > 4:
                    raise ValueError(
                        f"The fine-tuned RSVQA BLIP adapter expects an RGB image, not a raw {src.count}-band multispectral raster. "
                        "Provide an RGB visualization or route multispectral classification to /land-cover."
                    )
        except rasterio.errors.RasterioIOError:
            pass

    try:
        with Image.open(path) as source:
            bands = len(source.getbands())
            if bands > 4:
                raise ValueError(
                    "The fine-tuned RSVQA BLIP adapter expects an RGB image, not a raw multispectral raster. "
                    "Provide an RGB visualization or route multispectral classification to /land-cover."
                )
            return source.convert("RGB").copy()
    except ValueError:
        raise
    except Exception as exc:
        err_msg = str(exc)
        if "More samples per pixel than can be decoded" in err_msg:
            raise ValueError(
                "The fine-tuned RSVQA BLIP adapter expects an RGB image, not a raw multispectral raster. "
                "Provide an RGB visualization or route multispectral classification to /land-cover."
            ) from exc
        raise ValueError(f"Unable to prepare an RGB image for VQA: {exc}") from exc
