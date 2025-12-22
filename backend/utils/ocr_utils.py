"""OCR utilities for image preprocessing and text extraction."""

import logging
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

# Minimum confidence threshold for OCR results
MIN_OCR_CONFIDENCE = 0.6


def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Preprocess image for better OCR accuracy.
    
    Steps:
    1. Convert to grayscale
    2. Resize for optimal OCR (300 DPI equivalent)
    3. Binarize using adaptive threshold simulation
    4. Denoise
    5. Enhance contrast and sharpness
    """
    # Convert to grayscale
    if image.mode != "L":
        image = image.convert("L")
    
    # Upscale small images (OCR works best at ~300 DPI)
    min_dimension = min(image.size)
    if min_dimension < 1000:
        scale = 1500 / min_dimension
        new_size = (int(image.size[0] * scale), int(image.size[1] * scale))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
    
    # Auto-contrast to normalize brightness
    image = ImageOps.autocontrast(image, cutoff=2)
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    
    # Binarize: convert to black and white
    threshold = 140
    image = image.point(lambda p: 255 if p > threshold else 0)
    
    # Denoise using median filter
    image = image.filter(ImageFilter.MedianFilter(size=3))
    
    # Slight blur to smooth edges, then sharpen
    image = image.filter(ImageFilter.GaussianBlur(radius=0.5))
    enhancer = ImageEnhance.Sharpness(image)
    image = enhancer.enhance(2.0)
    
    return image


def extract_text_with_tesseract(image: Image.Image) -> tuple[str, float]:
    """
    Extract text from image using Tesseract OCR.
    
    Returns:
        Tuple of (extracted_text, average_confidence)
    """
    import pytesseract
    
    # Preprocess image
    processed = preprocess_image(image)
    
    # Get detailed OCR data with confidence scores
    # PSM 6: Assume uniform block of text
    # OEM 3: Default LSTM engine
    ocr_data = pytesseract.image_to_data(
        processed,
        config="--psm 6 --oem 3",
        output_type=pytesseract.Output.DICT
    )
    
    # Extract words and their confidences
    words = []
    confidences = []
    
    for i, conf in enumerate(ocr_data["conf"]):
        text = ocr_data["text"][i].strip()
        if text and conf != -1:  # -1 means no confidence available
            words.append(text)
            confidences.append(conf / 100.0)  # Convert to 0-1 scale
    
    extracted_text = " ".join(words)
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    
    return extracted_text, avg_confidence


def convert_pdf_page_to_image(pdf_path: str, page_number: int, dpi: int = 300) -> Image.Image:
    """
    Convert a single PDF page to an image.
    
    Args:
        pdf_path: Path to PDF file
        page_number: 0-indexed page number
        dpi: Resolution for conversion (higher = better OCR but slower)
    
    Returns:
        PIL Image of the page
    """
    from pdf2image import convert_from_path
    
    images = convert_from_path(
        pdf_path,
        first_page=page_number + 1,  # pdf2image uses 1-indexed pages
        last_page=page_number + 1,
        dpi=dpi,
        grayscale=True,  # Convert to grayscale during PDF rendering
    )
    
    if not images:
        raise ValueError(f"Failed to convert page {page_number} to image")
    
    return images[0]


def ocr_pdf_page(pdf_path: str, page_number: int) -> tuple[str, float]:
    """
    Perform OCR on a single PDF page.
    
    Args:
        pdf_path: Path to PDF file
        page_number: 0-indexed page number
    
    Returns:
        Tuple of (extracted_text, confidence)
        Returns empty string and 0.0 if confidence below threshold
    """
    try:
        image = convert_pdf_page_to_image(pdf_path, page_number, dpi=300)
        text, confidence = extract_text_with_tesseract(image)
        
        if confidence < MIN_OCR_CONFIDENCE:
            logger.warning(
                f"OCR confidence {confidence:.2f} below threshold {MIN_OCR_CONFIDENCE} "
                f"for page {page_number}"
            )
            return "", confidence
        
        return text, confidence
        
    except Exception as e:
        logger.error(f"OCR failed for page {page_number}: {e}")
        raise
