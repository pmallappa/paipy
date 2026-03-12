#!/usr/bin/env python3
"""
ListSources - List annual security report sources

Usage:
  python ListSources.py                    # List all categories with counts
  python ListSources.py <category>         # List reports in category
  python ListSources.py --search <term>    # Search by vendor or report name
  python ListSources.py --vendor <name>    # List all reports from vendor
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SOURCES_PATH = Path(__file__).parent.parent / "Data" / "sources.json"


def load_sources() -> dict:
    return json.loads(SOURCES_PATH.read_text())


def format_category_name(key: str) -> str:
    return " ".join(word.capitalize() for word in key.split("_"))


def list_categories(sources: dict) -> None:
    metadata = sources.get("metadata", {})
    print("Annual Security Reports\n")
    print(f"Source: {metadata.get('source', 'N/A')}")
    print(f"Last Updated: {metadata.get('lastUpdated', 'N/A')}")
    print(f"Total Reports: {metadata.get('totalReports', 0)}\n")

    print("ANALYSIS REPORTS:")
    for key, reports in sources.get("categories", {}).get("analysis", {}).items():
        print(f"  {format_category_name(key)}: {len(reports)} reports")

    print("\nSURVEY REPORTS:")
    for key, reports in sources.get("categories", {}).get("survey", {}).items():
        print(f"  {format_category_name(key)}: {len(reports)} reports")

    print("\nUsage: python ListSources.py <category_name>")


def list_category(sources: dict, category_name: str) -> None:
    normalized_name = category_name.lower().replace(" ", "_")

    reports = None
    found_in = ""

    if normalized_name in sources.get("categories", {}).get("analysis", {}):
        reports = sources["categories"]["analysis"][normalized_name]
        found_in = "Analysis"
    elif normalized_name in sources.get("categories", {}).get("survey", {}):
        reports = sources["categories"]["survey"][normalized_name]
        found_in = "Survey"

    if reports is None:
        print(f"Category not found: {category_name}")
        print("\nAvailable categories:")
        print("Analysis:", ", ".join(sources.get("categories", {}).get("analysis", {}).keys()))
        print("Survey:", ", ".join(sources.get("categories", {}).get("survey", {}).keys()))
        return

    print(f"{format_category_name(normalized_name)} ({found_in})\n")
    print(f"{len(reports)} reports:\n")

    for report in reports:
        print(f"  {report['vendor']}: {report['name']}")
        print(f"  {report['url']}\n")


def search_reports(sources: dict, term: str) -> None:
    normalized_term = term.lower()
    results: list[dict] = []

    for category, reports in sources.get("categories", {}).get("analysis", {}).items():
        for report in reports:
            if (
                normalized_term in report["vendor"].lower()
                or normalized_term in report["name"].lower()
            ):
                results.append({"category": category, "type": "Analysis", "report": report})

    for category, reports in sources.get("categories", {}).get("survey", {}).items():
        for report in reports:
            if (
                normalized_term in report["vendor"].lower()
                or normalized_term in report["name"].lower()
            ):
                results.append({"category": category, "type": "Survey", "report": report})

    if not results:
        print(f"No reports found matching: {term}")
        return

    print(f'Search results for "{term}": {len(results)} reports\n')

    for item in results:
        print(f"  {item['report']['vendor']}: {item['report']['name']}")
        print(f"  Category: {format_category_name(item['category'])} ({item['type']})")
        print(f"  {item['report']['url']}\n")


def list_vendor(sources: dict, vendor_name: str) -> None:
    normalized_vendor = vendor_name.lower()
    results: list[dict] = []

    for category, reports in sources.get("categories", {}).get("analysis", {}).items():
        for report in reports:
            if normalized_vendor in report["vendor"].lower():
                results.append({"category": category, "type": "Analysis", "report": report})

    for category, reports in sources.get("categories", {}).get("survey", {}).items():
        for report in reports:
            if normalized_vendor in report["vendor"].lower():
                results.append({"category": category, "type": "Survey", "report": report})

    if not results:
        print(f"No reports found from vendor: {vendor_name}")
        return

    print(f'Reports from "{vendor_name}": {len(results)} reports\n')

    for item in results:
        print(f"  {item['report']['name']}")
        print(f"  Category: {format_category_name(item['category'])} ({item['type']})")
        print(f"  {item['report']['url']}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    sources = load_sources()

    if not args:
        list_categories(sources)
    elif args[0] == "--search" and len(args) > 1:
        search_reports(sources, " ".join(args[1:]))
    elif args[0] == "--vendor" and len(args) > 1:
        list_vendor(sources, " ".join(args[1:]))
    else:
        list_category(sources, " ".join(args))
