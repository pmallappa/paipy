#!/usr/bin/env python3
"""
UpdateSources - Update sources from upstream GitHub repo

Usage:
  python UpdateSources.py                  # Fetch and update from GitHub
  python UpdateSources.py --dry-run       # Show changes without saving
  python UpdateSources.py --diff          # Show diff with upstream
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

SOURCES_PATH = Path(__file__).parent.parent / "Data" / "sources.json"
UPSTREAM_URL = "https://raw.githubusercontent.com/jacobdjwilson/awesome-annual-security-reports/main/README.md"


def fetch_upstream_readme() -> str:
    print("Fetching upstream README...")
    with httpx.Client(timeout=30) as client:
        response = client.get(UPSTREAM_URL)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch: {response.status_code} {response.reason_phrase}")
    return response.text


def parse_markdown_reports(markdown: str) -> dict[str, list[dict]]:
    reports: dict[str, list[dict]] = {}
    lines = markdown.split("\n")

    current_category = ""
    current_section = ""

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()

        if line.startswith("## Analysis Reports"):
            current_section = "analysis"
        elif line.startswith("## Survey Reports"):
            current_section = "survey"

        if line.startswith("### "):
            current_category = line[4:].lower().replace(" ", "_")
            key = f"{current_section}_{current_category}"
            if key not in reports:
                reports[key] = []

        report_match = re.match(r"^\d+\.\s+\*\*(.+?)\*\*", line) or re.match(r"^-\s+\*\*(.+?)\*\*", line)
        if report_match and current_category:
            report_name = report_match.group(1)

            vendor = ""
            url = ""

            for j in range(i + 1, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                if next_line.startswith("- Vendor:"):
                    vendor = next_line.replace("- Vendor:", "").strip()
                elif next_line.startswith("- URL:"):
                    url = next_line.replace("- URL:", "").strip()
                elif re.match(r"^\d+\.\s+\*\*", next_line) or next_line.startswith("### "):
                    break

            if vendor and url:
                key = f"{current_section}_{current_category}"
                reports.setdefault(key, []).append({
                    "vendor": vendor,
                    "name": report_name,
                    "url": url,
                })

    return reports


def load_current_sources() -> dict:
    if not SOURCES_PATH.exists():
        return {
            "metadata": {
                "source": UPSTREAM_URL.replace("/README.md", ""),
                "lastUpdated": datetime.now().isoformat()[:10],
                "totalReports": 0,
            },
            "categories": {
                "analysis": {},
                "survey": {},
            },
        }
    return json.loads(SOURCES_PATH.read_text())


def count_reports(sources: dict) -> int:
    count = 0
    for reports in sources.get("categories", {}).get("analysis", {}).values():
        count += len(reports)
    for reports in sources.get("categories", {}).get("survey", {}).values():
        count += len(reports)
    return count


def compare_reports(current: dict, parsed: dict[str, list[dict]]) -> dict[str, int]:
    added = 0
    removed = 0
    updated = 0

    current_urls: set[str] = set()
    for reports in current.get("categories", {}).get("analysis", {}).values():
        for report in reports:
            current_urls.add(report["url"])
    for reports in current.get("categories", {}).get("survey", {}).values():
        for report in reports:
            current_urls.add(report["url"])

    parsed_urls: set[str] = set()
    for reports in parsed.values():
        for report in reports:
            parsed_urls.add(report["url"])
            if report["url"] not in current_urls:
                added += 1

    for url in current_urls:
        if url not in parsed_urls:
            removed += 1

    return {"added": added, "removed": removed, "updated": updated}


def main() -> None:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    show_diff = "--diff" in args

    try:
        markdown = fetch_upstream_readme()
        print(f"Fetched {len(markdown)} bytes\n")

        parsed = parse_markdown_reports(markdown)
        current = load_current_sources()

        print("Parsing results:")
        parsed_total = 0
        for key, reports in parsed.items():
            print(f"  {key}: {len(reports)} reports")
            parsed_total += len(reports)
        print(f"  Total parsed: {parsed_total}\n")

        comparison = compare_reports(current, parsed)
        print("Changes detected:")
        print(f"  New reports: {comparison['added']}")
        print(f"  Removed reports: {comparison['removed']}")
        print(f"  Updated URLs: {comparison['updated']}\n")

        if dry_run:
            print("Dry run - no changes saved")
            return

        if show_diff:
            print("Detailed diff:")
            for key in parsed:
                parts = key.split("_", 1)
                if len(parts) == 2:
                    section, category = parts
                    current_category = current.get("categories", {}).get(section, {}).get(category)
                    if not current_category:
                        print(f"  + NEW CATEGORY: {key}")
            return

        # Update timestamp
        current["metadata"]["lastUpdated"] = datetime.now().isoformat()[:10]
        current["metadata"]["totalReports"] = count_reports(current)

        SOURCES_PATH.write_text(json.dumps(current, indent=2))
        print("Updated sources.json")
        print(f"   Total reports: {current['metadata']['totalReports']}")
        print(f"   Last updated: {current['metadata']['lastUpdated']}")

        print("\nFor full upstream sync, manually review changes at:")
        print(f"   {UPSTREAM_URL.replace('/README.md', '')}")

    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
