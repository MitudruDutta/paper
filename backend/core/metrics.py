"""Metrics collection and instrumentation."""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from typing import Any


@dataclass
class MetricValue:
    """A single metric with count, sum, min, max for aggregation."""
    count: int = 0
    total: float = 0.0
    min_val: float = float("inf")
    max_val: float = float("-inf")

    def record(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.min_val = min(self.min_val, value)
        self.max_val = max(self.max_val, value)

    @property
    def avg(self) -> float:
        return self.total / self.count if self.count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        if self.count == 0:
            return {"count": 0}
        return {
            "count": self.count,
            "total": round(self.total, 2),
            "avg": round(self.avg, 2),
            "min": round(self.min_val, 2) if self.min_val != float("inf") else None,
            "max": round(self.max_val, 2) if self.max_val != float("-inf") else None,
        }


@dataclass
class CounterMetric:
    """Simple counter metric."""
    value: int = 0

    def inc(self, amount: int = 1) -> None:
        self.value += amount

    def to_dict(self) -> dict[str, int]:
        return {"count": self.value}


class MetricsCollector:
    """Thread-safe metrics collector."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._histograms: dict[str, MetricValue] = defaultdict(MetricValue)
        self._counters: dict[str, CounterMetric] = defaultdict(CounterMetric)
        self._start_time = time.time()

    def record_histogram(self, name: str, value: float) -> None:
        """Record a value for a histogram metric."""
        with self._lock:
            self._histograms[name].record(value)

    def inc_counter(self, name: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        with self._lock:
            self._counters[name].inc(amount)

    def get_all(self) -> dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            return {
                "uptime_seconds": round(time.time() - self._start_time, 2),
                "histograms": {k: v.to_dict() for k, v in self._histograms.items()},
                "counters": {k: v.to_dict() for k, v in self._counters.items()},
            }

    def reset(self) -> None:
        """Reset all metrics (for testing)."""
        with self._lock:
            self._histograms.clear()
            self._counters.clear()
            self._start_time = time.time()


# Global metrics instance
metrics = MetricsCollector()


# Metric names as constants for consistency
class MetricNames:
    # Ingestion
    UPLOAD_SIZE_MB = "ingestion.upload_size_mb"
    UPLOAD_TIME_MS = "ingestion.upload_time_ms"
    UPLOAD_SUCCESS = "ingestion.upload_success"
    UPLOAD_FAILURE = "ingestion.upload_failure"
    VALIDATION_FAILURE = "ingestion.validation_failure"

    # Extraction
    EXTRACTION_TIME_MS = "extraction.time_ms"
    EXTRACTION_PAGES = "extraction.pages_processed"
    EXTRACTION_NATIVE_PAGES = "extraction.native_pages"
    EXTRACTION_SCANNED_PAGES = "extraction.scanned_pages"
    EXTRACTION_ERRORS = "extraction.errors"
    EXTRACTION_STARTED = "extraction.background_started"
    EXTRACTION_SUCCESS = "extraction.background_success"
    EXTRACTION_FAILURE = "extraction.background_failure"
    OCR_TIME_MS = "extraction.ocr_time_ms"

    # Retrieval
    RETRIEVAL_TIME_MS = "retrieval.time_ms"
    RETRIEVAL_CHUNKS = "retrieval.chunks_searched"
    RETRIEVAL_TOP_SCORE = "retrieval.top_score"

    # QA
    QA_TIME_MS = "qa.total_time_ms"
    QA_RETRIEVAL_TIME_MS = "qa.retrieval_time_ms"
    QA_LLM_TIME_MS = "qa.llm_time_ms"
    QA_CITATIONS = "qa.citation_count"
    QA_REGENERATIONS = "qa.regeneration_count"
    QA_REFUSALS = "qa.refusal_count"
    QA_NO_RESULTS = "qa.no_results"
    QA_NO_CITATIONS = "qa.no_citations"
    QA_SUCCESS = "qa.success"
    QA_FAILURE = "qa.failure"
    QA_CONFIDENCE = "qa.confidence"

    # LLM/Embedding calls
    LLM_CALLS = "llm.calls"
    LLM_FAILURES = "llm.failures"
    EMBEDDING_CALLS = "embedding.calls"
    EMBEDDING_FAILURES = "embedding.failures"
    VISION_CALLS = "vision.calls"
    VISION_FAILURES = "vision.failures"

    # Multimodal
    VISUAL_EXTRACTION_TIME_MS = "multimodal.visual_extraction_time_ms"
    TABLE_EXTRACTION_TIME_MS = "multimodal.table_extraction_time_ms"
    TABLES_EXTRACTED = "multimodal.tables_extracted"
    FIGURE_EXTRACTION_TIME_MS = "multimodal.figure_extraction_time_ms"
    FIGURES_EXTRACTED = "multimodal.figures_extracted"
