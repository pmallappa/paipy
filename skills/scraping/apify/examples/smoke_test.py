#!/usr/bin/env python3
"""
Smoke Test: Verify Apify Code-First API Works

Tests basic functionality without executing expensive operations.
"""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from .. import Apify


def main() -> None:
    print("=== Apify Code-First Smoke Test ===\n")

    if not os.environ.get("APIFY_TOKEN") and not os.environ.get("APIFY_API_KEY"):
        print("APIFY_TOKEN or APIFY_API_KEY not set in environment", file=sys.stderr)
        print("   Add to ${PAI_DIR}/.env: APIFY_TOKEN=apify_api_xxxxx", file=sys.stderr)
        print("   Or: APIFY_API_KEY=apify_api_xxxxx\n", file=sys.stderr)
        sys.exit(1)

    apify = Apify()

    try:
        # Test 1: Search for actors
        print("Test 1: Searching for actors...")
        actors = apify.search("web scraper", limit=3)

        if not actors:
            print("No actors found -- API may not be working", file=sys.stderr)
            sys.exit(1)

        print(f"Found {len(actors)} actors:")
        for i, actor in enumerate(actors):
            print(f"   {i + 1}. {actor.username}/{actor.name}")
            print(f"      {actor.title}")
            if actor.stats and actor.stats.get("totalRuns"):
                print(f"      Runs: {actor.stats['totalRuns']}")
        print()

        # Test 2: Verify types
        print("Test 2: Verifying types...")
        first_actor = actors[0]
        if not first_actor.id or not first_actor.name or not first_actor.username:
            print("Actor object missing required fields", file=sys.stderr)
            sys.exit(1)
        print("Actor types correct")
        print()

        # Test 3: Test token estimation
        print("Test 3: Token estimation...")

        def estimate_tokens(data: object) -> int:
            return math.ceil(len(json.dumps(data, default=str)) / 4)

        tokens = estimate_tokens([{"id": a.id, "name": a.name, "username": a.username, "title": a.title} for a in actors])
        print(f"{len(actors)} actors = ~{tokens} tokens")
        print()

        print("=== ALL TESTS PASSED ===\n")
        print("Apify code-first API is working correctly")
        print("Ready to use for scraping operations")
        print("Token savings will apply when filtering datasets\n")

    except Exception as e:
        print(f"Test failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
