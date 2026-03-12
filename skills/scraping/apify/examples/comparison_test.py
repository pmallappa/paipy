#!/usr/bin/env python3
"""
Comparison Test: MCP vs Code-First Apify

Demonstrates the difference in approach and token usage between
traditional MCP tool calls and code-first execution.
"""

from __future__ import annotations

import json
import math
import random
import time

from .. import Apify


def estimate_tokens(data: object) -> int:
    """Estimate token count from data."""
    s = json.dumps(data, default=str)
    return math.ceil(len(s) / 4)


def demonstrate_mcp_approach() -> None:
    print("=== MCP APPROACH ===\n")
    print("Traditional MCP flow with multiple round-trips through model context:\n")

    print("Step 1: mcp__Apify__search-actors")
    print('  Input: { search: "instagram scraper", limit: 10 }')
    print("  -> Tool definitions loaded: ~5,000 tokens")
    print("  -> Search results returned: ~1,000 tokens")
    print("  -> Results pass through model context")

    print("\nStep 2: mcp__Apify__call-actor")
    print('  Input: { actor: "apify/instagram-scraper", input: {...} }')
    print("  -> Run information returned: ~1,000 tokens")
    print("  -> Results pass through model context")

    print("\nStep 3: mcp__Apify__get-actor-output")
    print('  Input: { datasetId: "xyz123" }')
    print("  -> FULL dataset returned: ~50,000 tokens (100 items)")
    print("  -> ALL results pass through model context")
    print("  -> Model must filter in subsequent reasoning step")

    print("\nStep 4: Model reasoning to filter")
    print("  -> Additional model call to process and filter")
    print("  -> Context includes all 100 items again")

    print("\n  MCP Total Token Usage:")
    print("  Tool definitions:    5,000 tokens")
    print("  Search results:      1,000 tokens")
    print("  Run info:            1,000 tokens")
    print("  Full dataset:       50,000 tokens")
    print("  --------------------------------")
    print("  TOTAL:             ~57,000 tokens")
    print("  Plus additional reasoning overhead!\n")


def demonstrate_code_first_approach() -> None:
    print("=== CODE-FIRST APPROACH ===\n")
    print("Direct code execution with in-code filtering:\n")

    print("Step 1: Model reads README.md for API discovery")
    print("  -> README.md content: ~200 tokens")
    print("  -> Progressive disclosure (only load what's needed)")

    print("\nStep 2: Model writes code to execute operations")
    code_example = '''
from apify import Apify, DatasetOptions

apify = Apify()

# All operations in code -- no intermediate context bloat
actors = apify.search("instagram scraper")
run = apify.call_actor(actors[0].id, {
    "profiles": ["target"],
    "resultsLimit": 100,
})

# Wait for completion
apify.wait_for_run(run.id)

# Get dataset
dataset = apify.get_dataset(run.default_dataset_id)
items = dataset.list_items()

# CRITICAL: Filter in code BEFORE returning to model
import time
yesterday = time.time() * 1000 - 86400000
filtered = sorted(
    [p for p in items if (p.get("likesCount") or 0) > 1000],
    key=lambda p: p.get("likesCount") or 0,
    reverse=True,
)[:10]

# Only 10 filtered results reach model context
return filtered
    '''.strip()

    print("  Code to execute (~300 tokens):")
    for line in code_example.split("\n"):
        print(f"  {line}")

    print("\nStep 3: Code executes in bash environment")
    print("  -> All operations happen locally")
    print("  -> Intermediate results NEVER enter model context")
    print("  -> Filtering happens in execution environment")

    print("\nStep 4: Only filtered results return to model")
    print("  -> Filtered dataset: 10 items (~500 tokens)")
    print("  -> Model sees only what it needs")

    print("\n  Code-First Total Token Usage:")
    print("  README discovery:      200 tokens")
    print("  Code execution:        300 tokens")
    print("  Filtered results:      500 tokens")
    print("  --------------------------------")
    print("  TOTAL:              ~1,000 tokens")
    print("\n  TOKEN SAVINGS: 98.2% reduction!")
    print("  PERFORMANCE: Faster (no model round-trips)")
    print("  PRIVACY: Intermediate data never in model context\n")


def demonstrate_filtering_comparison() -> None:
    print("=== FILTERING COMPARISON ===\n")

    # Simulate a dataset of 100 items
    full_dataset = [
        {
            "id": f"post_{i}",
            "username": f"user{i}",
            "text": f"This is post {i} with some content",
            "likesCount": random.randint(0, 5000),
            "timestamp": time.time() * 1000 - random.random() * 86400000 * 7,
            "url": f"https://instagram.com/p/{i}",
        }
        for i in range(100)
    ]

    # Filter to top 10 high-engagement recent posts
    yesterday = time.time() * 1000 - 86400000
    filtered = sorted(
        [p for p in full_dataset if p["likesCount"] > 1000 and p["timestamp"] > yesterday],
        key=lambda p: p["likesCount"],
        reverse=True,
    )[:10]

    full_tokens = estimate_tokens(full_dataset)
    filtered_tokens = estimate_tokens(filtered)
    savings = (full_tokens - filtered_tokens) / full_tokens * 100 if full_tokens > 0 else 0

    print("Dataset Size Comparison:")
    print(f"  Full dataset:     {len(full_dataset)} items ({full_tokens} tokens)")
    print(f"  Filtered dataset: {len(filtered)} items ({filtered_tokens} tokens)")
    print(f"  Reduction:        {savings:.1f}% fewer tokens\n")

    print("MCP Approach:")
    print(f"  1. Return all 100 items to model ({full_tokens} tokens)")
    print("  2. Model reasons about filtering criteria")
    print("  3. Model makes another call to filter")
    print("  4. All 100 items in context again during filtering")
    print(f"  Total: ~{full_tokens * 2} tokens (dataset appears 2x in context)\n")

    print("Code-First Approach:")
    print("  1. Filter executed in code environment")
    print("  2. Only 10 items returned to model")
    print(f"  Total: ~{filtered_tokens} tokens\n")

    print(f"Key Insight: Code-first prevents {len(full_dataset) - len(filtered)} irrelevant items")
    print("   from ever entering the model context!\n")


def main() -> None:
    print("\n+-----------------------------------------------------------+")
    print("|  MCP vs Code-First Comparison: Apify Integration          |")
    print("+-----------------------------------------------------------+\n")

    demonstrate_mcp_approach()
    print("\n" + "-" * 60 + "\n")

    demonstrate_code_first_approach()
    print("\n" + "-" * 60 + "\n")

    demonstrate_filtering_comparison()
    print("\n" + "-" * 60 + "\n")

    print("=== CONCLUSION ===\n")
    print("Code-first Apify integration provides:")
    print("  - 98%+ token reduction through in-code filtering")
    print("  - Faster execution (no model round-trips for control flow)")
    print("  - Better privacy (intermediate data stays in execution env)")
    print("  - Progressive disclosure (load only what you need)")
    print("  - More maintainable (standard Python, not tool schemas)\n")

    print("When to use:")
    print("  - Data-heavy operations (scraping, large datasets)")
    print("  - Operations requiring filtering/transformation")
    print("  - Multiple sequential operations")
    print("  - Privacy-sensitive workflows\n")


if __name__ == "__main__":
    main()
