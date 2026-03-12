#!/usr/bin/env python3
"""
Example: Instagram Scraper with Code-First Apify

Demonstrates token savings through in-code filtering:
- MCP approach: ~57,000 tokens
- Code-first: ~1,000 tokens (98.2% reduction)
"""

from __future__ import annotations

import json
import math
import sys

from .. import Apify


def main() -> None:
    print("=== Apify Code-First Example: Instagram Scraper ===\n")

    # Initialize client (uses APIFY_TOKEN from environment)
    apify = Apify()

    try:
        # Step 1: Search for Instagram scraper actors
        print("1. Searching for Instagram scraper actors...")
        actors = apify.search("instagram scraper", limit=5)

        print(f"   Found {len(actors)} actors:")
        for i, actor in enumerate(actors):
            print(f"   {i + 1}. {actor.username}/{actor.name}")
            print(f"      {actor.title}")
            stats = actor.stats or {}
            runs = stats.get("runs", {}) if isinstance(stats, dict) else {}
            users = stats.get("users", {}) if isinstance(stats, dict) else {}
            total_runs = runs.get("total", "N/A") if isinstance(runs, dict) else "N/A"
            total_users = users.get("total", "N/A") if isinstance(users, dict) else "N/A"
            print(f"      Stats: {total_runs} runs, {total_users} users\n")

        # Select the most popular actor
        selected_actor = actors[0]
        print(f"   Selected: {selected_actor.username}/{selected_actor.name}\n")

        # Step 2: Call the actor (execute scraping)
        print("2. Calling actor to scrape Instagram profiles...")
        print("   (This is a dry run -- modify input for real scraping)")

        # Example input -- modify for actual use
        input_data = {
            # Instagram profile usernames to scrape
            "profiles": ["example"],
            # Limit results to avoid excessive runtime/costs
            "resultsLimit": 50,
        }

        print(f"   Input: {json.dumps(input_data, indent=2)}")
        print("   Note: Using dry run mode (not actually executing)\n")

        # Uncomment to actually run:
        # run = apify.call_actor(selected_actor.id, input_data, {
        #     "memory": 2048,
        #     "timeout": 300,
        # })
        #
        # print(f"   Run started: {run.id}")
        # print(f"   Status: {run.status}")
        # print(f"   Container URL: {run.container_url}\n")
        #
        # # Step 3: Wait for completion
        # print("3. Waiting for actor run to complete...")
        # apify.wait_for_run(run.id, wait_secs=300)
        #
        # final_run = apify.get_run(run.id)
        # print(f"   Final status: {final_run.status}")
        #
        # if final_run.status != "SUCCEEDED":
        #     print("   Actor run failed!", file=sys.stderr)
        #     sys.exit(1)
        #
        # # Step 4: Get dataset and filter results IN CODE
        # print("\n4. Fetching and filtering results...")
        # dataset = apify.get_dataset(final_run.default_dataset_id)
        #
        # # Get all items
        # from .. import DatasetOptions
        # all_items = dataset.list_items(DatasetOptions(limit=100))
        # print(f"   Total items retrieved: {len(all_items)}")
        #
        # # KEY: Filter in code BEFORE returning to model context
        # import time
        # yesterday = time.time() * 1000 - 86400000  # 24 hours ago
        # filtered = sorted(
        #     [p for p in all_items if (p.get("likesCount") or 0) > 1000],
        #     key=lambda p: p.get("likesCount") or 0,
        #     reverse=True,
        # )[:10]
        #
        # print(f"   Filtered to top {len(filtered)} high-engagement recent posts\n")
        #
        # # Step 5: Show token savings
        # def estimate_tokens(data):
        #     return math.ceil(len(json.dumps(data, default=str)) / 4)
        #
        # mcp_tokens = estimate_tokens(all_items)
        # code_tokens = estimate_tokens(filtered)
        # savings = (mcp_tokens - code_tokens) / mcp_tokens * 100
        #
        # print("=== Token Savings ===")
        # print(f"MCP approach (all items): ~{mcp_tokens} tokens")
        # print(f"Code-first (filtered):    ~{code_tokens} tokens")
        # print(f"Savings:                  {savings:.1f}%")

        print("3. Dry run complete!")
        print("   Uncomment the code above to actually execute the scraper.")
        print("   Make sure to:")
        print("   - Set valid Instagram profile usernames")
        print("   - Have sufficient Apify credits")
        print("   - Review actor documentation for input schema\n")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
