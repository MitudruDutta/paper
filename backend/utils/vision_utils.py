"""Vision processing utilities."""

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def image_to_base64(image_bytes: bytes) -> str:
    """Convert image bytes to base64 string."""
    return base64.b64encode(image_bytes).decode("utf-8")


def crop_region(page_image: bytes, bbox: tuple[float, float, float, float], page_width: int = 0, page_height: int = 0) -> bytes:
    """Crop a region from page image. bbox is (x0, y0, x1, y1) in relative coords.
    
    Note: page_width/page_height are ignored; actual image dimensions are used.
    """
    try:
        from PIL import Image
        
        img = Image.open(io.BytesIO(page_image))
        img_width, img_height = img.size
        
        # Convert relative to absolute using actual image dimensions
        x0 = max(0, int(bbox[0] * img_width))
        y0 = max(0, int(bbox[1] * img_height))
        x1 = min(img_width, int(bbox[2] * img_width))
        y1 = min(img_height, int(bbox[3] * img_height))
        
        cropped = img.crop((x0, y0, x1, y1))
        
        output = io.BytesIO()
        cropped.save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        logger.error(f"Failed to crop region: {e}")
        return page_image


def render_page_to_image(pdf_path: str, page_number: int, dpi: int = 150) -> bytes | None:
    """Render a PDF page to image bytes."""
    try:
        from pdf2image import convert_from_path
        
        images = convert_from_path(
            pdf_path,
            first_page=page_number + 1,
            last_page=page_number + 1,
            dpi=dpi,
        )
        
        if not images:
            return None
        
        output = io.BytesIO()
        images[0].save(output, format="PNG")
        return output.getvalue()
    except Exception as e:
        logger.error(f"Failed to render page {page_number}: {e}")
        return None


def get_image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    """Get image width and height. Returns (0, 0) on failure with warning."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        return img.size
    except Exception as e:
        logger.warning(f"Failed to get image dimensions: {e}")
        return (0, 0)
