"""Citation validation and post-processing for RAG answers."""

import logging
import re
from dataclasses import dataclass

from services.prompt_builder import ChunkContext

logger = logging.getLogger(__name__)

# Pattern matches [Page X] or [Pages X-Y]
CITATION_PATTERN = re.compile(r'\[Pages?\s+(\d+)(?:\s*-\s*(\d+))?\]', re.IGNORECASE)


@dataclass
class ValidationResult:
    """Result of citation validation."""
    valid: bool
    answer: str
    cited_pages: list[int]
    invalid_pages: list[int]
    error: str | None = None


def extract_citations(answer: str) -> list[tuple[int, int]]:
    """Extract all page citations from answer."""
    citations = []
    for match in CITATION_PATTERN.finditer(answer):
        page_start = int(match.group(1))
        page_end = int(match.group(2)) if match.group(2) else page_start
        citations.append((page_start, page_end))
    return citations


def get_valid_page_range(chunks: list[ChunkContext]) -> set[int]:
    """Get all valid page numbers from retrieved chunks."""
    valid_pages = set()
    for chunk in chunks:
        for page in range(chunk.page_start, chunk.page_end + 1):
            valid_pages.add(page)
    return valid_pages


def is_refusal_answer(answer: str) -> bool:
    """Check if the answer is a valid refusal."""
    refusal_phrases = [
        "cannot find this information",
        "not present in the context",
        "not found in the provided",
        "no information about",
        "not mentioned in",
        "does not contain",
        "no relevant information",
    ]
    answer_lower = answer.lower()
    return any(phrase in answer_lower for phrase in refusal_phrases)


def clean_citation_formatting(answer: str) -> str:
    """Clean up awkward citation placements."""
    # Fix: [Page X]? [Page Y] -> [Page X]?
    answer = re.sub(r'(\[Pages?\s+\d+(?:\s*-\s*\d+)?\])\s*\?\s*\[Pages?\s+\d+(?:\s*-\s*\d+)?\]', r'\1?', answer)
    
    # Fix: [Page X]. [Page Y] -> [Page X].
    answer = re.sub(r'(\[Pages?\s+\d+(?:\s*-\s*\d+)?\])\s*\.\s*\[Pages?\s+\d+(?:\s*-\s*\d+)?\]', r'\1.', answer)
    
    # Fix: [Page X] [Page Y] (consecutive) -> [Pages X-Y]
    answer = re.sub(r'\[Page\s+(\d+)\]\s*\[Page\s+(\d+)\]', r'[Pages \1-\2]', answer)
    
    # Fix: multiple citations at end of same sentence
    answer = re.sub(r'(\[Pages?\s+\d+(?:\s*-\s*\d+)?\])\s*(\[Pages?\s+\d+(?:\s*-\s*\d+)?\])', r'\1', answer)
    
    # Fix: citation before punctuation -> after
    answer = re.sub(r'\s*(\[Pages?\s+[^\]]+\])\s*([.!?])', r'\2 \1', answer)
    answer = re.sub(r'([.!?])\s+(\[Pages?\s+[^\]]+\])\s*([.!?])', r'\1 \2', answer)
    
    # Clean up double spaces
    answer = re.sub(r'  +', ' ', answer)
    
    return answer.strip()


def remove_invalid_citations(answer: str, valid_pages: set[int]) -> str:
    """Remove citations that reference invalid pages."""
    def replace_if_invalid(match):
        page_start = int(match.group(1))
        page_end = int(match.group(2)) if match.group(2) else page_start
        
        # Check if ALL pages in range are valid
        for p in range(page_start, page_end + 1):
            if p not in valid_pages:
                logger.warning(f"Removing invalid citation: {match.group(0)}")
                return ""
        return match.group(0)
    
    return CITATION_PATTERN.sub(replace_if_invalid, answer)


def ensure_sentence_citations(answer: str, chunks: list[ChunkContext]) -> str:
    """Ensure substantive sentences have citations by adding at end of paragraphs."""
    if not chunks:
        return answer
    
    # Get the most common/relevant page from chunks
    page_counts: dict[int, int] = {}
    for chunk in chunks:
        for p in range(chunk.page_start, chunk.page_end + 1):
            page_counts[p] = page_counts.get(p, 0) + 1
    
    if not page_counts:
        return answer
    
    primary_page = max(page_counts, key=page_counts.get)
    
    # Split into paragraphs
    paragraphs = answer.split('\n\n')
    result_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # Skip if refusal or already has citation
        if is_refusal_answer(para) or CITATION_PATTERN.search(para):
            result_paragraphs.append(para)
            continue
        
        # Only add citation to substantial paragraphs
        if len(para.split()) > 10:
            # Add citation at end
            if para[-1] in '.!?':
                para = f"{para[:-1]} [Page {primary_page}]{para[-1]}"
            else:
                para = f"{para} [Page {primary_page}]."
        
        result_paragraphs.append(para)
    
    return '\n\n'.join(result_paragraphs)


def validate_and_fix_citations(answer: str, chunks: list[ChunkContext]) -> ValidationResult:
    """Validate and fix citations in the answer."""
    
    # Handle refusals
    if is_refusal_answer(answer):
        return ValidationResult(
            valid=True,
            answer=answer,
            cited_pages=[],
            invalid_pages=[],
        )
    
    valid_pages = get_valid_page_range(chunks)
    
    # Step 1: Remove invalid citations
    fixed_answer = remove_invalid_citations(answer, valid_pages)
    
    # Step 2: Clean up formatting
    fixed_answer = clean_citation_formatting(fixed_answer)
    
    # Step 3: Ensure citations exist (add if missing)
    if not CITATION_PATTERN.search(fixed_answer):
        fixed_answer = ensure_sentence_citations(fixed_answer, chunks)
    
    # Final validation
    citations = extract_citations(fixed_answer)
    cited_pages_set = set()
    invalid_pages = []
    
    for page_start, page_end in citations:
        for page in range(page_start, page_end + 1):
            if page in valid_pages:
                cited_pages_set.add(page)
            else:
                invalid_pages.append(page)
    
    if invalid_pages:
        return ValidationResult(
            valid=False,
            answer=fixed_answer,
            cited_pages=sorted(cited_pages_set),
            invalid_pages=invalid_pages,
            error=f"Invalid citations remain: {invalid_pages}",
        )
    
    return ValidationResult(
        valid=True,
        answer=fixed_answer,
        cited_pages=sorted(cited_pages_set),
        invalid_pages=[],
    )
