#!/usr/bin/env python3
"""
System Parser - Universal Content Parser

Usage:
    python parser.py <URL>
    python parser.py <URL1> <URL2> <URL3> (batch mode)
"""

from __future__ import annotations

import json
import math
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from .validators import validate_content_schema

SCHEMA_VERSION = "1.0.0"


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: python parser.py <URL> [URL2] [URL3] ...", file=sys.stderr)
        print("\nExample:", file=sys.stderr)
        print("  python parser.py https://example.com/article", file=sys.stderr)
        sys.exit(1)

    urls = args
    print(f"System Parser v{SCHEMA_VERSION}")
    print(f"Processing {len(urls)} URL(s)\n")

    success_count = 0
    fail_count = 0

    for i, url in enumerate(urls):
        print(f"\n[{i + 1}/{len(urls)}] Processing: {url}")
        print("-" * 80)

        try:
            result = parse_content(url)
            success_count += 1
            print(f"Success: {result['filename']}")
            print(f"Stats: {result['stats']}")
            print(f"Confidence: {result['confidence']}")
            if result["warnings"]:
                print(f"Warnings: {len(result['warnings'])}")
                for w in result["warnings"]:
                    print(f"   - {w}")
        except Exception as error:
            fail_count += 1
            print(f"Failed: {error}", file=sys.stderr)

    print("\n" + "=" * 80)
    print("Batch Processing Complete")
    print(f"Successful: {success_count}/{len(urls)}")
    print(f"Failed: {fail_count}/{len(urls)}")


def parse_content(url: str) -> dict:
    """Parse a single URL into ContentSchema."""
    # Step 1: Detect content type
    print("  Detecting content type...")
    content_type = detect_content_type(url)
    print(f"   Type: {content_type}")

    # Step 2: Extract content
    print("  Extracting content...")
    raw_content = extract_content(url, content_type)
    print(f"   Extracted: {raw_content['word_count']} words")

    # Step 3: Analyze
    print("  Analyzing with Gemini...")
    analyzed = analyze_with_gemini(raw_content)
    print(f"   People: {len(analyzed['people'])}, Companies: {len(analyzed['companies'])}")

    # Step 4: Populate schema
    print("  Populating schema...")
    schema = populate_schema(url, content_type, raw_content, analyzed)

    # Step 5: Validate
    print("  Validating schema...")
    validation = validate_content_schema(schema)
    if not validation.valid:
        error_msgs = ", ".join(str(e) for e in validation.errors)
        raise ValueError(f"Validation failed: {error_msgs}")
    print(f"   Valid: yes ({len(validation.warnings)} warnings)")

    # Step 6: Output JSON
    print("  Writing output...")
    filename = write_output(schema)
    print(f"   File: {filename}")

    stats = (
        f"{raw_content['word_count']} words, "
        f"{len(analyzed['people'])} people, "
        f"{len(analyzed['companies'])} companies, "
        f"{len(analyzed['links'])} links"
    )
    return {
        "filename": filename,
        "stats": stats,
        "confidence": schema["extraction_metadata"]["confidence_score"],
        "warnings": validation.warnings,
    }


def detect_content_type(url: str) -> str:
    """Detect content type from URL."""
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    path = parsed.path

    if "youtube.com" in domain or "youtu.be" in domain:
        return "video"
    if ("twitter.com" in domain or "x.com" in domain) and "/status/" in path:
        return "tweet_thread"
    if any(d in domain for d in ["substack.com", "beehiiv.com", "convertkit.com", "ghost.io"]):
        return "newsletter"
    if "arxiv.org" in domain or path.endswith(".pdf"):
        return "pdf"

    return "article"


def extract_content(url: str, content_type: str) -> dict:
    """Extract content using appropriate method for content type."""
    print(f"   [Placeholder: would extract {content_type} from {url}]")

    return {
        "title": "Example Title",
        "content": "This is example content that would be extracted from the URL.",
        "word_count": 150,
        "published_date": datetime.now(timezone.utc).isoformat(),
    }


def analyze_with_gemini(raw_content: dict) -> dict:
    """Analyze content with Gemini for entity extraction, summarization, etc."""
    print("   [Placeholder: would analyze with Gemini]")

    return {
        "people": [],
        "companies": [],
        "topics": {
            "primary_category": "technology",
            "secondary_categories": [],
            "tags": ["example", "demo", "placeholder"],
            "keywords": ["example", "demo"],
            "themes": ["Example theme"],
            "newsletter_sections": ["Headlines"],
        },
        "links": [],
        "summaries": {
            "short": "Example short summary.",
            "medium": "Example medium summary with more detail.",
            "long": "Example long summary with comprehensive coverage of the topic.",
        },
        "excerpts": ["Example excerpt"],
        "analysis": {
            "sentiment": "neutral",
            "importance_score": 5,
            "novelty_score": 5,
            "controversy_score": 3,
            "relevance_to_audience": ["general_tech"],
            "key_insights": ["Example insight"],
            "trending_potential": "medium",
        },
    }


def populate_schema(url: str, content_type: str, raw_content: dict, analyzed: dict) -> dict:
    """Populate complete ContentSchema."""
    now = datetime.now(timezone.utc).isoformat()

    return {
        "content": {
            "id": str(uuid.uuid4()),
            "type": content_type,
            "title": raw_content["title"],
            "summary": {
                "short": analyzed["summaries"]["short"],
                "medium": analyzed["summaries"]["medium"],
                "long": analyzed["summaries"]["long"],
            },
            "content": {
                "full_text": raw_content["content"],
                "transcript": None,
                "excerpts": analyzed["excerpts"],
            },
            "metadata": {
                "source_url": url,
                "canonical_url": url,
                "published_date": raw_content.get("published_date"),
                "accessed_date": now,
                "language": "en",
                "word_count": raw_content["word_count"],
                "read_time_minutes": math.ceil(raw_content["word_count"] / 200),
                "author_platform": "other",
            },
        },
        "people": analyzed["people"],
        "companies": analyzed["companies"],
        "topics": analyzed["topics"],
        "links": analyzed["links"],
        "sources": [],
        "newsletter_metadata": {
            "issue_number": None,
            "section": None,
            "position_in_section": None,
            "editorial_note": None,
            "include_in_newsletter": False,
            "scheduled_date": None,
        },
        "analysis": {
            **analyzed["analysis"],
            "related_content_ids": [],
        },
        "extraction_metadata": {
            "processed_date": now,
            "processing_method": "hybrid",
            "confidence_score": 0.75,
            "warnings": [],
            "version": SCHEMA_VERSION,
        },
    }


def write_output(schema: dict) -> str:
    """Write schema to JSON file."""
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d-%H%M%S")
    sanitized_title = re.sub(r"[^a-z0-9]+", "-", schema["content"]["title"].lower())
    sanitized_title = sanitized_title.strip("-")[:50]

    filename = f"{timestamp}_{sanitized_title}.json"
    Path(filename).write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return filename


if __name__ == "__main__":
    main()
