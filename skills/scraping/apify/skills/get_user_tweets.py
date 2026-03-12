#!/usr/bin/env python3
"""Get latest tweets from any Twitter user using code-first Apify."""

from __future__ import annotations

import json
import math
import sys

from .. import Apify, DatasetOptions


def main() -> None:
    args = sys.argv[1:]
    username = args[0] if args else None
    limit = int(args[1]) if len(args) > 1 else 5

    if not username:
        print("Usage: python get_user_tweets.py <username> [limit]", file=sys.stderr)
        print("Example: python get_user_tweets.py ThePrimeagen 5", file=sys.stderr)
        sys.exit(1)

    print(f"=== Getting Latest {limit} Tweets from @{username} ===\n")

    apify = Apify()

    try:
        # Use known working actor: apidojo/twitter-scraper-lite
        twitter_actor_id = "apidojo/twitter-scraper-lite"

        print(f"1. Scraping @{username} profile...")

        input_data = {
            "username": username,
            "max_posts": limit,
            "maxTweets": limit,
            "maxItems": limit,
            "resultsLimit": limit,
            "tweetsDesired": limit,
            "searchTerms": [f"from:{username}"],
            "startUrls": [f"https://twitter.com/{username}"],
        }

        print(f"   Fetching last {limit} tweets...")
        print("   (this may take 30-60 seconds)...")

        run = apify.call_actor(
            twitter_actor_id,
            input_data,
            {"memory": 2048, "timeout": 120},
        )

        print(f"   Run ID: {run.id}")
        print()

        # Step 2: Wait for completion
        print("2. Waiting for scraper to finish...")
        apify.wait_for_run(run.id, wait_secs=120)

        final_run = apify.get_run(run.id)
        print(f"   Status: {final_run.status}")

        if final_run.status != "SUCCEEDED":
            print("   Actor run did not succeed!", file=sys.stderr)
            print(f"   Status: {final_run.status}", file=sys.stderr)
            sys.exit(1)
        print()

        # Step 3: Get results
        print("3. Fetching results...")
        dataset = apify.get_dataset(final_run.default_dataset_id)
        items = dataset.list_items(DatasetOptions(limit=limit))

        print(f"   Retrieved {len(items)} tweets")
        print()

        if not items:
            print("   No tweets found.")
            return

        # Step 4: Show the tweets
        print("4. Latest tweets:")
        print("   " + "=" * 40)
        print()

        for i, tweet in enumerate(items):
            print(f"   {i + 1}/{len(items)}:")
            print(f"   {tweet.get('text') or tweet.get('fullText', '')}")
            print()
            print(f"   Posted: {tweet.get('createdAt', '')}")
            if tweet.get("url"):
                print(f"   URL: {tweet['url']}")
            print("   " + "-" * 40)
            print()

        # Step 5: Show token savings
        def estimate_tokens(data: object) -> int:
            return math.ceil(len(json.dumps(data, default=str)) / 4)

        total_tokens = estimate_tokens(items)
        print("5. Token efficiency:")
        print(f"   {len(items)} tweets: ~{total_tokens} tokens")
        print("   Filtered in code before model context")
        print()

        print("Successfully retrieved tweets using code-first Apify!")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if hasattr(e, "__traceback__"):
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
