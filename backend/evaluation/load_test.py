"""Load Testing for Paper API.

Simple load testing to measure latency percentiles and throughput.
Run with: python -m evaluation.load_test
"""

import asyncio
import json
import logging
import os
import statistics
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")


@dataclass
class LoadTestResult:
    """Result of a load test run."""
    scenario: str
    total_requests: int
    successful: int
    failed: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_avg_ms: float
    latency_min_ms: float
    latency_max_ms: float
    requests_per_second: float
    duration_seconds: float
    errors: list[str]


async def make_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs,
) -> tuple[bool, float, str | None]:
    """Make a single request and return (success, latency_ms, error)."""
    start = time.perf_counter()
    try:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        latency_ms = (time.perf_counter() - start) * 1000
        
        if response.status_code < 400:
            return True, latency_ms, None
        return False, latency_ms, f"HTTP {response.status_code}"
        
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000
        return False, latency_ms, str(e)[:100]


async def run_concurrent_requests(
    scenario: str,
    method: str,
    url: str,
    num_requests: int,
    concurrency: int,
    **kwargs,
) -> LoadTestResult:
    """Run concurrent requests and collect metrics."""
    logger.info(f"Running {scenario}: {num_requests} requests, concurrency={concurrency}")
    
    latencies: list[float] = []
    errors: list[str] = []
    successful = 0
    failed = 0
    
    semaphore = asyncio.Semaphore(concurrency)
    
    async def bounded_request(client: httpx.AsyncClient):
        async with semaphore:
            return await make_request(client, method, url, **kwargs)
    
    start_time = time.perf_counter()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [bounded_request(client) for _ in range(num_requests)]
        results = await asyncio.gather(*tasks)
    
    duration = time.perf_counter() - start_time
    
    for success, latency, error in results:
        latencies.append(latency)
        if success:
            successful += 1
        else:
            failed += 1
            if error and error not in errors:
                errors.append(error)
    
    # Handle empty latencies case
    if not latencies:
        return LoadTestResult(
            scenario=scenario,
            total_requests=num_requests,
            successful=0,
            failed=num_requests,
            latency_p50_ms=0.0,
            latency_p95_ms=0.0,
            latency_p99_ms=0.0,
            latency_avg_ms=0.0,
            latency_min_ms=0.0,
            latency_max_ms=0.0,
            requests_per_second=0.0,
            duration_seconds=round(duration, 2),
            errors=errors[:10],
        )
    
    # Compute percentiles
    sorted_latencies = sorted(latencies)
    
    if len(sorted_latencies) < 2:
        # Single element - all percentiles are the same value
        p50 = p95 = p99 = sorted_latencies[0]
    else:
        quantile_values = statistics.quantiles(sorted_latencies, n=100, method='inclusive')
        # quantiles returns n-1 cut points, so index 49 is p50, 94 is p95, 98 is p99
        p50 = quantile_values[49] if len(quantile_values) > 49 else sorted_latencies[len(sorted_latencies) // 2]
        p95 = quantile_values[94] if len(quantile_values) > 94 else sorted_latencies[int(len(sorted_latencies) * 0.95)]
        p99 = quantile_values[98] if len(quantile_values) > 98 else sorted_latencies[-1]
    
    return LoadTestResult(
        scenario=scenario,
        total_requests=num_requests,
        successful=successful,
        failed=failed,
        latency_p50_ms=round(p50, 2),
        latency_p95_ms=round(p95, 2),
        latency_p99_ms=round(p99, 2),
        latency_avg_ms=round(statistics.mean(latencies), 2),
        latency_min_ms=round(min(latencies), 2),
        latency_max_ms=round(max(latencies), 2),
        requests_per_second=round(num_requests / duration, 2),
        duration_seconds=round(duration, 2),
        errors=errors[:10],  # Limit error list
    )


async def run_health_check_load_test(num_requests: int = 100, concurrency: int = 10) -> LoadTestResult:
    """Load test the health endpoint."""
    return await run_concurrent_requests(
        scenario="health_check",
        method="GET",
        url=f"{API_BASE}/health",
        num_requests=num_requests,
        concurrency=concurrency,
    )


async def run_document_list_load_test(num_requests: int = 50, concurrency: int = 5) -> LoadTestResult:
    """Load test the document list endpoint."""
    return await run_concurrent_requests(
        scenario="document_list",
        method="GET",
        url=f"{API_BASE}/documents",
        num_requests=num_requests,
        concurrency=concurrency,
    )


async def run_search_load_test(
    document_id: str,
    num_requests: int = 20,
    concurrency: int = 3,
) -> LoadTestResult:
    """Load test the search endpoint."""
    return await run_concurrent_requests(
        scenario="search",
        method="POST",
        url=f"{API_BASE}/search",
        num_requests=num_requests,
        concurrency=concurrency,
        json={"query": "test query", "document_ids": [document_id], "top_k": 5},
    )


async def run_qa_load_test(
    document_id: str,
    num_requests: int = 10,
    concurrency: int = 2,
) -> LoadTestResult:
    """Load test the QA endpoint (expensive, use sparingly)."""
    return await run_concurrent_requests(
        scenario="qa",
        method="POST",
        url=f"{API_BASE}/ask",
        num_requests=num_requests,
        concurrency=concurrency,
        json={"question": "What is this document about?", "document_ids": [document_id]},
    )


def print_result(result: LoadTestResult) -> None:
    """Print a load test result."""
    print(f"\n{'=' * 50}")
    print(f"Scenario: {result.scenario}")
    print(f"{'=' * 50}")
    print(f"Total Requests:    {result.total_requests}")
    print(f"Successful:        {result.successful}")
    print(f"Failed:            {result.failed}")
    print(f"Duration:          {result.duration_seconds}s")
    print(f"Throughput:        {result.requests_per_second} req/s")
    print(f"Latency P50:       {result.latency_p50_ms}ms")
    print(f"Latency P95:       {result.latency_p95_ms}ms")
    print(f"Latency P99:       {result.latency_p99_ms}ms")
    print(f"Latency Avg:       {result.latency_avg_ms}ms")
    print(f"Latency Min/Max:   {result.latency_min_ms}ms / {result.latency_max_ms}ms")
    if result.errors:
        print(f"Errors:            {result.errors}")


def save_results(results: list[LoadTestResult], output_dir: Path) -> None:
    """Save load test results."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    
    with open(output_dir / f"load_test_{timestamp}.json", "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)
    
    logger.info(f"Results saved to {output_dir}")


async def main():
    """Run all load tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run load tests")
    parser.add_argument("--document-id", help="Document ID for search/QA tests")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/results"))
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    args = parser.parse_args()
    
    results: list[LoadTestResult] = []
    
    # Always run health check test
    result = await run_health_check_load_test(
        num_requests=50 if args.quick else 100,
        concurrency=10,
    )
    print_result(result)
    results.append(result)
    
    # Document list test
    result = await run_document_list_load_test(
        num_requests=25 if args.quick else 50,
        concurrency=5,
    )
    print_result(result)
    results.append(result)
    
    # Search and QA tests require a document
    if args.document_id:
        result = await run_search_load_test(
            args.document_id,
            num_requests=10 if args.quick else 20,
            concurrency=3,
        )
        print_result(result)
        results.append(result)
        
        if not args.quick:
            result = await run_qa_load_test(
                args.document_id,
                num_requests=5,
                concurrency=2,
            )
            print_result(result)
            results.append(result)
    
    save_results(results, args.output_dir)
    
    # Summary
    print("\n" + "=" * 50)
    print("LOAD TEST SUMMARY")
    print("=" * 50)
    for r in results:
        status = "✓" if r.failed == 0 else "✗"
        print(f"{status} {r.scenario}: P95={r.latency_p95_ms}ms, {r.requests_per_second} req/s")


if __name__ == "__main__":
    asyncio.run(main())
