"""Retrieval Evaluation for Paper.

Measures retrieval quality metrics: Recall@K, Precision@K, score distributions.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


@dataclass
class RetrievalTestCase:
    """A retrieval test case with known relevant chunks."""
    document_id: str
    query: str
    relevant_pages: list[int]  # Pages that should be retrieved
    top_k: int = 5


@dataclass
class RetrievalResult:
    """Result of a retrieval evaluation."""
    query: str
    top_k: int
    retrieved_pages: list[int]
    relevant_pages: list[int]
    scores: list[float]
    recall_at_k: float
    precision_at_k: float
    avg_score: float
    latency_ms: float
    error: str | None = None


@dataclass
class RetrievalSummary:
    """Summary of retrieval evaluation."""
    timestamp: str
    total_queries: int
    avg_recall_at_k: float
    avg_precision_at_k: float
    avg_score: float
    avg_latency_ms: float
    score_distribution: dict  # min, max, p50, p90


async def run_retrieval_test(
    client: httpx.AsyncClient,
    test: RetrievalTestCase,
) -> RetrievalResult:
    """Run a single retrieval test."""
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{API_BASE}/search",
            json={
                "query": test.query,
                "document_ids": [test.document_id],
                "top_k": test.top_k,
            },
            timeout=30.0,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        
        if response.status_code != 200:
            return RetrievalResult(
                query=test.query,
                top_k=test.top_k,
                retrieved_pages=[],
                relevant_pages=test.relevant_pages,
                scores=[],
                recall_at_k=0.0,
                precision_at_k=0.0,
                avg_score=0.0,
                latency_ms=latency_ms,
                error=f"HTTP {response.status_code}",
            )
        
        data = response.json()
        results = data.get("results", [])
        
        # Extract retrieved pages and scores
        retrieved_pages = []
        scores = []
        for r in results:
            for p in range(r.get("page_start", 0), r.get("page_end", 0) + 1):
                if p not in retrieved_pages:
                    retrieved_pages.append(p)
            scores.append(r.get("score", 0.0))
        
        # Compute metrics
        relevant_set = set(test.relevant_pages)
        retrieved_set = set(retrieved_pages)
        
        if relevant_set:
            recall = len(relevant_set & retrieved_set) / len(relevant_set)
        else:
            recall = 1.0 if not retrieved_set else 0.0
        
        if retrieved_set:
            precision = len(relevant_set & retrieved_set) / len(retrieved_set)
        else:
            precision = 1.0 if not relevant_set else 0.0
        
        avg_score = sum(scores) / len(scores) if scores else 0.0
        
        return RetrievalResult(
            query=test.query,
            top_k=test.top_k,
            retrieved_pages=retrieved_pages,
            relevant_pages=test.relevant_pages,
            scores=scores,
            recall_at_k=recall,
            precision_at_k=precision,
            avg_score=avg_score,
            latency_ms=latency_ms,
        )
        
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return RetrievalResult(
            query=test.query,
            top_k=test.top_k,
            retrieved_pages=[],
            relevant_pages=test.relevant_pages,
            scores=[],
            recall_at_k=0.0,
            precision_at_k=0.0,
            avg_score=0.0,
            latency_ms=latency_ms,
            error=str(e),
        )


async def run_retrieval_evaluation(
    test_cases: list[RetrievalTestCase],
) -> tuple[list[RetrievalResult], RetrievalSummary]:
    """Run all retrieval tests and compute summary."""
    results: list[RetrievalResult] = []
    
    async with httpx.AsyncClient() as client:
        for i, test in enumerate(test_cases):
            logger.info(f"Running retrieval test {i+1}/{len(test_cases)}: {test.query[:50]}...")
            result = await run_retrieval_test(client, test)
            results.append(result)
            logger.info(f"  Recall@{test.top_k}: {result.recall_at_k:.2f}, Precision: {result.precision_at_k:.2f}")
    
    # Compute summary
    valid_results = [r for r in results if not r.error]
    all_scores = [s for r in valid_results for s in r.scores]
    
    if all_scores:
        sorted_scores = sorted(all_scores)
        p50_idx = len(sorted_scores) // 2
        p90_idx = int(len(sorted_scores) * 0.9)
        score_dist = {
            "min": round(min(sorted_scores), 3),
            "max": round(max(sorted_scores), 3),
            "p50": round(sorted_scores[p50_idx], 3),
            "p90": round(sorted_scores[p90_idx], 3),
        }
    else:
        score_dist = {"min": 0, "max": 0, "p50": 0, "p90": 0}
    
    summary = RetrievalSummary(
        timestamp=datetime.now(timezone.utc).isoformat(),
        total_queries=len(test_cases),
        avg_recall_at_k=sum(r.recall_at_k for r in valid_results) / len(valid_results) if valid_results else 0.0,
        avg_precision_at_k=sum(r.precision_at_k for r in valid_results) / len(valid_results) if valid_results else 0.0,
        avg_score=sum(all_scores) / len(all_scores) if all_scores else 0.0,
        avg_latency_ms=sum(r.latency_ms for r in valid_results) / len(valid_results) if valid_results else 0.0,
        score_distribution=score_dist,
    )
    
    return results, summary


def save_results(results: list[RetrievalResult], summary: RetrievalSummary, output_dir: Path) -> None:
    """Save evaluation results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    
    with open(output_dir / f"retrieval_results_{timestamp}.json", "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    with open(output_dir / f"retrieval_summary_{timestamp}.json", "w") as f:
        json.dump(asdict(summary), f, indent=2)


if __name__ == "__main__":
    # Example usage
    test_cases = [
        RetrievalTestCase(
            document_id="00000000-0000-0000-0000-000000000000",
            query="What is machine learning?",
            relevant_pages=[1, 2, 3],
            top_k=5,
        ),
    ]
    
    async def main():
        results, summary = await run_retrieval_evaluation(test_cases)
        print(f"\nAvg Recall@K: {summary.avg_recall_at_k:.2f}")
        print(f"Avg Precision@K: {summary.avg_precision_at_k:.2f}")
        print(f"Score Distribution: {summary.score_distribution}")
    
    asyncio.run(main())
