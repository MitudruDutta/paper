"""Semantic chunking service for document text."""

import bisect
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Chunking parameters
TARGET_CHUNK_SIZE = 650  # tokens (middle of 500-800 range)
MIN_CHUNK_SIZE = 500
MAX_CHUNK_SIZE = 800
OVERLAP_SIZE = 125  # tokens (middle of 100-150 range)

# Recursion safety
MAX_RECURSION_DEPTH = 10


@dataclass
class PageText:
    """Text content with page number."""
    page_number: int
    text: str


@dataclass
class Chunk:
    """A semantic chunk of text."""
    chunk_index: int
    content: str
    page_start: int
    page_end: int
    token_count: int


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using word-based heuristic.
    More accurate than char/4 for English text.
    
    Approximation: ~1.3 tokens per word for English
    """
    words = len(text.split())
    # Add extra for punctuation and special chars
    special_chars = len(re.findall(r'[^\w\s]', text))
    return int(words * 1.3 + special_chars * 0.5)


def tokens_to_chars(tokens: int) -> int:
    """Convert token estimate to character count."""
    # Average ~4 chars per token for English
    return tokens * 4


def _fallback_split(text: str) -> list[str]:
    """Fallback split when recursion limit reached. Uses overlap for continuity."""
    result = []
    chunk_chars = tokens_to_chars(MAX_CHUNK_SIZE)
    overlap_chars = tokens_to_chars(OVERLAP_SIZE)
    step = chunk_chars - overlap_chars
    for i in range(0, len(text), step):
        part = text[i:i + chunk_chars]
        if part:
            result.append(part)
    return result


def split_by_separators(text: str, separators: list[str], depth: int = 0) -> list[str]:
    """Recursively split text by separators, preserving order."""
    if not text:
        return []
    
    if not separators or depth >= MAX_RECURSION_DEPTH:
        if estimate_tokens(text) > MAX_CHUNK_SIZE:
            return _fallback_split(text)
        return [text] if text else []
    
    sep = separators[0]
    remaining_seps = separators[1:]
    
    parts = text.split(sep)
    
    result = []
    for i, part in enumerate(parts):
        if not part.strip():
            continue
        
        # Add separator back except for last part
        if i < len(parts) - 1:
            part = part + sep
        
        # If part is small enough, keep it; otherwise recurse
        if estimate_tokens(part) <= MAX_CHUNK_SIZE or not remaining_seps:
            if estimate_tokens(part) > MAX_CHUNK_SIZE and not remaining_seps:
                result.extend(_fallback_split(part))
            else:
                result.append(part)
        else:
            result.extend(split_by_separators(part, remaining_seps, depth + 1))
    
    return result


def merge_small_chunks(segments: list[str], min_size: int) -> list[str]:
    """Merge segments that are too small."""
    if not segments:
        return []
    
    result = []
    current = ""
    
    for segment in segments:
        if not segment.strip():
            continue
            
        if not current:
            current = segment
        elif estimate_tokens(current) < min_size:
            current = current + segment
        else:
            result.append(current)
            current = segment
    
    if current:
        result.append(current)
    
    return result


def create_overlapping_chunks(
    segments: list[str],
    target_size: int,
    overlap_size: int,
    page_markers: dict[int, int],
) -> list[Chunk]:
    """Create chunks with overlap from segments."""
    chunks = []
    current_content = ""
    current_start_page = 0
    chunk_index = 0
    
    # Precompute sorted positions for O(log n) lookup
    sorted_positions = sorted(page_markers.keys())
    sorted_pages = [page_markers[p] for p in sorted_positions]
    
    def get_page_at_pos(position: int) -> int:
        """Get page number for a character position using binary search."""
        if not sorted_positions:
            return 0
        idx = bisect.bisect_right(sorted_positions, position)
        if idx == 0:
            return 0
        return sorted_pages[idx - 1]
    
    full_text = "".join(segments)
    text_pos = 0
    
    for segment in segments:
        segment_tokens = estimate_tokens(segment)
        current_tokens = estimate_tokens(current_content)
        
        # If adding segment exceeds max, finalize current chunk
        if current_content and current_tokens + segment_tokens > MAX_CHUNK_SIZE:
            # Finalize chunk
            content = current_content.strip()
            if content:
                end_pos = text_pos
                page_end = get_page_at_pos(end_pos - 1) if end_pos > 0 else current_start_page
                
                chunks.append(Chunk(
                    chunk_index=chunk_index,
                    content=content,
                    page_start=current_start_page,
                    page_end=page_end,
                    token_count=estimate_tokens(content),
                ))
                chunk_index += 1
            
            # Start new chunk with overlap
            overlap_chars = tokens_to_chars(overlap_size)
            if len(current_content) > overlap_chars:
                # Find sentence boundary for overlap
                overlap_text = current_content[-overlap_chars:]
                sentence_end = overlap_text.rfind('. ')
                if sentence_end > 0:
                    overlap_text = overlap_text[sentence_end + 2:]
                current_content = overlap_text
                current_start_page = get_page_at_pos(text_pos - len(overlap_text))
            else:
                current_content = ""
                current_start_page = get_page_at_pos(text_pos)
        
        current_content += segment
        text_pos += len(segment)
    
    # Final chunk
    if current_content.strip():
        content = current_content.strip()
        chunks.append(Chunk(
            chunk_index=chunk_index,
            content=content,
            page_start=current_start_page,
            page_end=get_page_at_pos(text_pos - 1),
            token_count=estimate_tokens(content),
        ))
    
    return chunks


def chunk_document(pages: list[PageText]) -> list[Chunk]:
    """
    Chunk document text semantically.
    
    Args:
        pages: List of PageText objects sorted by page_number
    
    Returns:
        List of Chunk objects
    """
    if not pages:
        return []
    
    # Sort pages by page number
    pages = sorted(pages, key=lambda p: p.page_number)
    
    # Concatenate text with page position tracking
    full_text = ""
    page_markers: dict[int, int] = {}  # char_position -> page_number
    
    for page in pages:
        page_markers[len(full_text)] = page.page_number
        full_text += page.text
        if not full_text.endswith("\n"):
            full_text += "\n"
    
    if not full_text.strip():
        return []
    
    # Recursive semantic splitting
    separators = ["\n\n", "\n", ". ", " "]
    segments = split_by_separators(full_text, separators)
    
    # Merge very small segments
    segments = merge_small_chunks(segments, MIN_CHUNK_SIZE // 2)
    
    # Create overlapping chunks
    chunks = create_overlapping_chunks(
        segments,
        TARGET_CHUNK_SIZE,
        OVERLAP_SIZE,
        page_markers,
    )
    
    logger.info(f"Created {len(chunks)} chunks from {len(pages)} pages")
    
    return chunks
