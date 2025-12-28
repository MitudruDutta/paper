"""Figure analysis service using Gemini Vision."""

import asyncio
import logging
import re
from dataclasses import dataclass

import google.generativeai as genai

from core.config import settings

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.6
MIN_FIGURE_DIM_RATIO = 0.1
NUMBER_SANITY_LIMIT = 1e12

# One-time configuration
_configured = False
_vision_model: genai.GenerativeModel | None = None


def _get_vision_model() -> genai.GenerativeModel:
    """Get cached vision model."""
    global _configured, _vision_model
    if _vision_model is None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not configured")
        if not _configured:
            genai.configure(api_key=settings.gemini_api_key)
            _configured = True
        _vision_model = genai.GenerativeModel(settings.gemini_model)
    return _vision_model


@dataclass
class DetectedFigure:
    """Detected figure region."""
    page_number: int
    bbox: tuple[float, float, float, float]
    figure_type: str
    confidence: float


@dataclass
class AnalyzedFigure:
    """Analyzed figure with description."""
    page_number: int
    figure_type: str
    description: str
    extracted_data: dict | None
    confidence: float


def detect_figures_simple(pdf_path: str, page_number: int) -> list[DetectedFigure]:
    """Simple figure detection using PyMuPDF image extraction."""
    try:
        import fitz
        
        with fitz.open(pdf_path) as doc:
            if page_number >= len(doc):
                return []
            
            page = doc[page_number]
            images = page.get_images()
            
            figures = []
            for img_idx, img in enumerate(images):
                xref = img[0]
                try:
                    img_rect = page.get_image_rects(xref)
                    if img_rect:
                        rect = img_rect[0]
                        page_rect = page.rect
                        bbox = (
                            rect.x0 / page_rect.width,
                            rect.y0 / page_rect.height,
                            rect.x1 / page_rect.width,
                            rect.y1 / page_rect.height,
                        )
                        
                        width = bbox[2] - bbox[0]
                        height = bbox[3] - bbox[1]
                        if width > MIN_FIGURE_DIM_RATIO and height > MIN_FIGURE_DIM_RATIO:
                            figures.append(DetectedFigure(
                                page_number=page_number,
                                bbox=bbox,
                                figure_type="unknown",
                                confidence=0.7,
                            ))
                except Exception as err:
                    logger.error(f"Error processing image {img_idx} on page {page_number}: {err}")
                    continue
            
            return figures
    except Exception as e:
        logger.error(f"Figure detection failed on page {page_number}: {e}")
        return []


def _validate_extracted_numbers(data: dict | None) -> tuple[dict | None, bool]:
    """Validate extracted numeric data."""
    if not data or "raw" not in data:
        return data, True
    
    raw = data["raw"]
    numbers = re.findall(r'-?\d+\.?\d*', raw)
    
    for num_str in numbers:
        try:
            num = float(num_str)
            if num < -NUMBER_SANITY_LIMIT or num > NUMBER_SANITY_LIMIT:
                return {**data, "validation": "suspect"}, False
        except ValueError:
            continue
    
    return data, True


def _crop_image(image_bytes: bytes, bbox: tuple[float, float, float, float]) -> bytes:
    """Crop image to bbox region. Returns original if cropping fails."""
    try:
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        
        # Convert normalized bbox to pixel coordinates
        left = int(bbox[0] * width)
        top = int(bbox[1] * height)
        right = int(bbox[2] * width)
        bottom = int(bbox[3] * height)
        
        # Validate crop region
        if right <= left or bottom <= top:
            return image_bytes
        if right - left < 50 or bottom - top < 50:  # Too small
            return image_bytes
        
        cropped = img.crop((left, top, right, bottom))
        
        output = io.BytesIO()
        cropped.save(output, format='PNG')
        return output.getvalue()
    except Exception as e:
        logger.warning(f"Image crop failed: {e}")
        return image_bytes


def _analyze_sync(image_bytes: bytes) -> tuple[str, str, dict | None, float]:
    """Synchronous vision analysis."""
    prompt = """Analyze this figure/chart from a document. Provide:
1. Type: (bar_chart, line_chart, pie_chart, diagram, flowchart, table, photograph, other)
2. Description: A factual description of what the figure shows.
3. Data: If this is a chart with visible numeric values, list them. Otherwise say "none".

Format your response exactly as:
TYPE: <type>
DESCRIPTION: <description>
DATA: <data or none>"""

    model = _get_vision_model()
    image_part = {"mime_type": "image/png", "data": image_bytes}
    
    response = model.generate_content(
        [prompt, image_part],
        generation_config=genai.GenerationConfig(temperature=0.1, max_output_tokens=500),
    )
    
    # Safely access response.text (can raise ValueError if blocked/filtered)
    try:
        result = response.text
    except (ValueError, Exception) as e:
        logger.warning(f"Vision response blocked or inaccessible: {e}")
        # Log safety info if available
        if hasattr(response, 'prompt_feedback'):
            logger.debug(f"Prompt feedback: {response.prompt_feedback}")
        return "unknown", "Figure analysis blocked by safety filter", None, 0.0
    
    if not result:
        return "unknown", "Empty response from vision model", None, 0.0
    
    figure_type = "unknown"
    description = "Unable to analyze figure"
    extracted_data = None
    parsing_success = True
    
    type_match = re.search(r'TYPE:\s*(\w+)', result, re.IGNORECASE)
    if type_match:
        figure_type = type_match.group(1).lower()
    else:
        parsing_success = False
    
    desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?=DATA:|$)', result, re.IGNORECASE | re.DOTALL)
    if desc_match:
        description = desc_match.group(1).strip()
    else:
        parsing_success = False
    
    data_match = re.search(r'DATA:\s*(.+?)$', result, re.IGNORECASE | re.DOTALL)
    if data_match:
        data_str = data_match.group(1).strip().lower()
        if data_str != "none" and data_str:
            extracted_data = {"raw": data_match.group(1).strip()}
            extracted_data, is_valid = _validate_extracted_numbers(extracted_data)
            if not is_valid:
                parsing_success = False
    
    confidence = 0.7 if parsing_success else 0.5
    return figure_type, description, extracted_data, confidence


async def analyze_figure_with_vision(
    image_bytes: bytes,
) -> tuple[str, str, dict | None, float]:
    """Analyze figure using Gemini Vision."""
    try:
        return await asyncio.to_thread(_analyze_sync, image_bytes)
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return "unknown", "Unable to analyze figure", None, 0.0


async def analyze_figures_on_page(
    pdf_path: str,
    page_number: int,
) -> list[AnalyzedFigure]:
    """Detect and analyze figures on a page."""
    from utils.vision_utils import render_page_to_image
    
    detected = detect_figures_simple(pdf_path, page_number)
    if not detected:
        return []
    
    page_image = render_page_to_image(pdf_path, page_number, dpi=150)
    if not page_image:
        return []
    
    results = []
    for fig in detected:
        # Crop to figure region
        cropped_image = _crop_image(page_image, fig.bbox)
        
        figure_type, description, extracted_data, confidence = await analyze_figure_with_vision(
            cropped_image
        )
        
        if confidence >= CONFIDENCE_THRESHOLD:
            results.append(AnalyzedFigure(
                page_number=page_number,
                figure_type=figure_type,
                description=description,
                extracted_data=extracted_data,
                confidence=confidence,
            ))
    
    logger.info(f"Page {page_number}: Analyzed {len(results)} figures")
    return results
