"""Figure analysis service."""

import logging
import os
import re
from dataclasses import dataclass

import httpx

from utils.vision_utils import image_to_base64, render_page_to_image

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "172.17.0.1")
OLLAMA_URL = f"http://{OLLAMA_HOST}:11434"
VISION_MODEL = os.getenv("VISION_MODEL", "llava:7b")
CONFIDENCE_THRESHOLD = 0.6

# Minimum figure dimension as ratio of page size (filters out icons/small images)
MIN_FIGURE_DIM_RATIO = 0.1

# Sanity limit for extracted numeric values (reject extreme outliers)
NUMBER_SANITY_LIMIT = 1e12


def _check_ollama_config():
    if OLLAMA_HOST == "172.17.0.1":
        logger.warning(
            "OLLAMA_HOST using default Docker bridge IP (172.17.0.1). "
            "Set OLLAMA_HOST env var for other deployments (Kubernetes, remote, etc.)"
        )


def _validate_constants():
    if not (0 < MIN_FIGURE_DIM_RATIO < 1):
        logger.warning(f"MIN_FIGURE_DIM_RATIO={MIN_FIGURE_DIM_RATIO} should be in (0,1)")
    if NUMBER_SANITY_LIMIT <= 0:
        logger.warning(f"NUMBER_SANITY_LIMIT={NUMBER_SANITY_LIMIT} should be positive")


_check_ollama_config()
_validate_constants()


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
                    logger.error(f"Error processing image {img_idx} (xref={xref}) on page {page_number}: {err}")
                    continue
            
            return figures
    except Exception as e:
        logger.error(f"Figure detection failed on page {page_number}: {e}")
        return []


def _validate_extracted_numbers(data: dict | None) -> tuple[dict | None, bool]:
    """Validate extracted numeric data. Returns (data, is_valid)."""
    if not data or "raw" not in data:
        return data, True
    
    raw = data["raw"]
    numbers = re.findall(r'-?\d+\.?\d*', raw)
    
    for num_str in numbers:
        try:
            num = float(num_str)
            if num < -NUMBER_SANITY_LIMIT or num > NUMBER_SANITY_LIMIT:
                return {**data, "validation": "suspect", "reason": "extreme_value"}, False
        except ValueError:
            continue
    
    return data, True


async def analyze_figure_with_vision(
    image_bytes: bytes,
    http_client: httpx.AsyncClient,
) -> tuple[str, str, dict | None, float]:
    """Analyze figure using vision model."""
    prompt = """Analyze this figure/chart from a document. Provide:
1. Type: (bar_chart, line_chart, pie_chart, diagram, flowchart, table, photograph, other)
2. Description: A factual, grounded description of what the figure shows. Do NOT invent specific numbers unless they are clearly visible.
3. Data: If this is a chart with clearly visible numeric values, list them. Otherwise say "none".

Format your response exactly as:
TYPE: <type>
DESCRIPTION: <description>
DATA: <data or none>"""

    try:
        response = await http_client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [image_to_base64(image_bytes)],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        
        result = response.json().get("response", "")
        
        logger.debug(f"Vision model raw response: {result[:500]}")
        
        figure_type = "unknown"
        description = "Unable to analyze figure"
        extracted_data = None
        parsing_success = True
        
        type_match = re.search(r'TYPE:\s*(\w+)', result, re.IGNORECASE)
        if type_match:
            figure_type = type_match.group(1).lower()
        else:
            logger.warning(f"Failed to parse TYPE from vision response: {result[:100]}")
            parsing_success = False
        
        desc_match = re.search(r'DESCRIPTION:\s*(.+?)(?=DATA:|$)', result, re.IGNORECASE | re.DOTALL)
        if desc_match:
            description = desc_match.group(1).strip()
            description += " [Note: Verify any numeric values against the original document.]"
        else:
            logger.warning("Failed to parse DESCRIPTION from vision response")
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
        if extracted_data:
            confidence = min(confidence, 0.6)
        
        return figure_type, description, extracted_data, confidence
        
    except Exception as e:
        logger.error(f"Vision analysis failed: {e}")
        return "unknown", "Unable to analyze figure", None, 0.0


async def analyze_figures_on_page(
    pdf_path: str,
    page_number: int,
    http_client: httpx.AsyncClient,
) -> list[AnalyzedFigure]:
    """Detect and analyze figures on a page."""
    detected = detect_figures_simple(pdf_path, page_number)
    if not detected:
        return []
    
    page_image = render_page_to_image(pdf_path, page_number, dpi=150)
    if not page_image:
        return []
    
    results = []
    for fig in detected:
        figure_type, description, extracted_data, confidence = await analyze_figure_with_vision(
            page_image, http_client
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
