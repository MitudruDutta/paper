"""Confidence scoring for QA answers."""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfidenceInputs:
    """Inputs for confidence calculation."""
    retrieval_scores: list[float]
    num_chunks_retrieved: int
    num_chunks_cited: int
    num_pages_cited: int
    num_documents: int
    citation_valid: bool
    required_regeneration: bool


def compute_confidence(inputs: ConfidenceInputs) -> float:
    """
    Compute confidence score from retrieval and citation quality.
    
    Returns float between 0.0 and 0.99 (never 1.0 unless perfect conditions).
    """
    if not inputs.citation_valid:
        logger.warning("Invalid citations - confidence 0")
        return 0.0
    
    # Base score from retrieval relevance (0-0.4)
    if inputs.retrieval_scores:
        # Clamp scores to valid range before averaging
        clamped_scores = [max(0.0, min(1.0, s)) for s in inputs.retrieval_scores]
        avg_relevance = sum(clamped_scores) / len(clamped_scores)
        # Qdrant cosine similarity is typically 0.3-0.9 for relevant results
        relevance_score = min(avg_relevance, 0.9) / 0.9 * 0.4
    else:
        relevance_score = 0.0
    
    # Citation coverage score (0-0.3)
    if inputs.num_chunks_retrieved > 0:
        citation_ratio = inputs.num_chunks_cited / inputs.num_chunks_retrieved
        coverage_score = min(citation_ratio, 1.0) * 0.3
    else:
        coverage_score = 0.0
    
    # Multi-source bonus (0-0.2)
    if inputs.num_pages_cited >= 3:
        source_score = 0.2
    elif inputs.num_pages_cited >= 2:
        source_score = 0.15
    elif inputs.num_pages_cited >= 1:
        source_score = 0.1
    else:
        source_score = 0.0
    
    # Multi-document handling (0-0.1)
    if inputs.num_documents > 1 and inputs.num_chunks_cited >= inputs.num_documents:
        # Cited from multiple documents
        doc_score = 0.1
    elif inputs.num_documents == 1:
        doc_score = 0.05
    else:
        doc_score = 0.0
    
    # Penalties
    penalty = 0.0
    if inputs.required_regeneration:
        penalty += 0.15  # Had to retry due to citation issues
    
    # Calculate final score
    raw_score = relevance_score + coverage_score + source_score + doc_score - penalty
    
    # Clamp to valid range, never return 1.0
    final_score = max(0.0, min(0.99, raw_score))
    
    logger.info(
        f"Confidence: {final_score:.2f} "
        f"(relevance={relevance_score:.2f}, coverage={coverage_score:.2f}, "
        f"sources={source_score:.2f}, docs={doc_score:.2f}, penalty={penalty:.2f})"
    )
    
    return round(final_score, 2)
