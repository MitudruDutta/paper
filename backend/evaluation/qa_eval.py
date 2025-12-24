"""QA Evaluation Harness for Paper.

This module provides tools to evaluate QA quality against a curated test set.
Run with: python -m evaluation.qa_eval
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


@dataclass
class TestCase:
    """A single QA test case."""
    document_id: str
    question: str
    expected_answer_contains: list[str]  # Key phrases that should appear
    expected_pages: list[int]  # Pages that should be cited
    should_refuse: bool = False  # Whether the system should refuse to answer


@dataclass
class EvalResult:
    """Result of evaluating a single test case."""
    test_id: str
    question: str
    passed: bool
    answer: str
    cited_pages: list[int]
    expected_pages: list[int]
    confidence: float
    citation_accuracy: float  # % of cited pages that are expected
    answer_contains_expected: bool
    refusal_correct: bool
    latency_ms: float
    error: str | None = None


@dataclass
class EvalSummary:
    """Summary of evaluation run."""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    pass_rate: float
    avg_citation_accuracy: float
    avg_confidence: float
    avg_latency_ms: float
    refusal_accuracy: float


async def run_qa_test(client: httpx.AsyncClient, test: TestCase) -> EvalResult:
    """Run a single QA test case."""
    import time
    
    start = time.perf_counter()
    try:
        response = await client.post(
            f"{API_BASE}/ask",
            json={
                "question": test.question,
                "document_ids": [test.document_id],
            },
            timeout=60.0,
        )
        latency_ms = (time.perf_counter() - start) * 1000
        
        if response.status_code != 200:
            return EvalResult(
                test_id=f"{test.document_id[:8]}_{test.question[:20]}",
                question=test.question,
                passed=False,
                answer="",
                cited_pages=[],
                expected_pages=test.expected_pages,
                confidence=0.0,
                citation_accuracy=0.0,
                answer_contains_expected=False,
                refusal_correct=False,
                latency_ms=latency_ms,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
            )
        
        data = response.json()
        answer = data.get("answer", "")
        confidence = data.get("confidence", 0.0)
        sources = data.get("sources", [])
        
        # Extract cited pages
        cited_pages = []
        for src in sources:
            for p in range(src.get("page_start", 0), src.get("page_end", 0) + 1):
                if p not in cited_pages:
                    cited_pages.append(p)
        
        # Check if answer is a refusal
        refusal_phrases = ["cannot find", "not found", "no information", "unable to"]
        is_refusal = any(phrase in answer.lower() for phrase in refusal_phrases)
        refusal_correct = is_refusal == test.should_refuse
        
        # Citation accuracy: what % of cited pages are in expected pages
        if cited_pages and test.expected_pages:
            correct_citations = len(set(cited_pages) & set(test.expected_pages))
            citation_accuracy = correct_citations / len(cited_pages)
        elif not cited_pages and not test.expected_pages:
            citation_accuracy = 1.0  # Both empty is correct for refusals
        else:
            citation_accuracy = 0.0
        
        # Check if answer contains expected phrases
        answer_lower = answer.lower()
        answer_contains_expected = all(
            phrase.lower() in answer_lower
            for phrase in test.expected_answer_contains
        ) if test.expected_answer_contains else True
        
        # Overall pass criteria
        passed = (
            refusal_correct
            and (citation_accuracy >= 0.8 or test.should_refuse)
            and (answer_contains_expected or test.should_refuse)
        )
        
        return EvalResult(
            test_id=f"{test.document_id[:8]}_{test.question[:20]}",
            question=test.question,
            passed=passed,
            answer=answer[:500],  # Truncate for storage
            cited_pages=cited_pages,
            expected_pages=test.expected_pages,
            confidence=confidence,
            citation_accuracy=citation_accuracy,
            answer_contains_expected=answer_contains_expected,
            refusal_correct=refusal_correct,
            latency_ms=latency_ms,
        )
        
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return EvalResult(
            test_id=f"{test.document_id[:8]}_{test.question[:20]}",
            question=test.question,
            passed=False,
            answer="",
            cited_pages=[],
            expected_pages=test.expected_pages,
            confidence=0.0,
            citation_accuracy=0.0,
            answer_contains_expected=False,
            refusal_correct=False,
            latency_ms=latency_ms,
            error=str(e),
        )


async def run_evaluation(test_cases: list[TestCase]) -> tuple[list[EvalResult], EvalSummary]:
    """Run all test cases and compute summary."""
    results: list[EvalResult] = []
    
    async with httpx.AsyncClient() as client:
        for i, test in enumerate(test_cases):
            logger.info(f"Running test {i+1}/{len(test_cases)}: {test.question[:50]}...")
            result = await run_qa_test(client, test)
            results.append(result)
            logger.info(f"  {'✓ PASS' if result.passed else '✗ FAIL'} (latency: {result.latency_ms:.0f}ms)")
    
    # Compute summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    citation_accuracies = [r.citation_accuracy for r in results if not r.error]
    confidences = [r.confidence for r in results if not r.error]
    latencies = [r.latency_ms for r in results if not r.error]
    refusal_tests = [r for r in results if r.expected_pages == []]
    refusal_correct = sum(1 for r in refusal_tests if r.refusal_correct)
    
    summary = EvalSummary(
        timestamp=datetime.utcnow().isoformat(),
        total_tests=total,
        passed=passed,
        failed=total - passed,
        pass_rate=passed / total if total > 0 else 0.0,
        avg_citation_accuracy=sum(citation_accuracies) / len(citation_accuracies) if citation_accuracies else 0.0,
        avg_confidence=sum(confidences) / len(confidences) if confidences else 0.0,
        avg_latency_ms=sum(latencies) / len(latencies) if latencies else 0.0,
        refusal_accuracy=refusal_correct / len(refusal_tests) if refusal_tests else 1.0,
    )
    
    return results, summary


def save_results(results: list[EvalResult], summary: EvalSummary, output_dir: Path) -> None:
    """Save evaluation results to files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    # Save detailed results
    results_file = output_dir / f"eval_results_{timestamp}.json"
    with open(results_file, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    # Save summary
    summary_file = output_dir / f"eval_summary_{timestamp}.json"
    with open(summary_file, "w") as f:
        json.dump(asdict(summary), f, indent=2)
    
    logger.info(f"Results saved to {output_dir}")


def load_test_cases(test_file: Path) -> list[TestCase]:
    """Load test cases from JSON file."""
    with open(test_file) as f:
        data = json.load(f)
    return [TestCase(**tc) for tc in data]


# Example test cases (replace with real document IDs after upload)
EXAMPLE_TEST_CASES = [
    {
        "document_id": "00000000-0000-0000-0000-000000000000",
        "question": "What is the main topic of this document?",
        "expected_answer_contains": [],
        "expected_pages": [1],
        "should_refuse": False,
    },
    {
        "document_id": "00000000-0000-0000-0000-000000000000",
        "question": "What is the weather in Tokyo?",
        "expected_answer_contains": [],
        "expected_pages": [],
        "should_refuse": True,
    },
]


async def main():
    """Run evaluation from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run QA evaluation")
    parser.add_argument("--test-file", type=Path, help="Path to test cases JSON")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"))
    args = parser.parse_args()
    
    if args.test_file and args.test_file.exists():
        test_cases = load_test_cases(args.test_file)
    else:
        logger.warning("No test file provided, using example test cases")
        test_cases = [TestCase(**tc) for tc in EXAMPLE_TEST_CASES]
    
    if not test_cases:
        logger.error("No test cases to run")
        sys.exit(1)
    
    logger.info(f"Running {len(test_cases)} test cases...")
    results, summary = await run_evaluation(test_cases)
    
    # Print summary
    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Tests:        {summary.total_tests}")
    print(f"Passed:             {summary.passed}")
    print(f"Failed:             {summary.failed}")
    print(f"Pass Rate:          {summary.pass_rate:.1%}")
    print(f"Avg Citation Acc:   {summary.avg_citation_accuracy:.1%}")
    print(f"Avg Confidence:     {summary.avg_confidence:.2f}")
    print(f"Avg Latency:        {summary.avg_latency_ms:.0f}ms")
    print(f"Refusal Accuracy:   {summary.refusal_accuracy:.1%}")
    print("=" * 50)
    
    save_results(results, summary, args.output_dir)
    
    # Exit with error if pass rate < 80%
    if summary.pass_rate < 0.8:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
