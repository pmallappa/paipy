#!/usr/bin/env python3
"""
FetchReport - Fetch and summarize a specific report

Usage:
  python FetchReport.py <vendor> <report-name>    # Fetch specific report
  python FetchReport.py --url <url>               # Fetch by direct URL
  python FetchReport.py --list-cached             # List downloaded reports
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

SOURCES_PATH = Path(__file__).parent.parent / "Data" / "sources.json"
REPORTS_DIR = Path(__file__).parent.parent / "Reports"


def load_sources() -> dict:
    return json.loads(SOURCES_PATH.read_text())


def find_report(sources: dict, vendor: str, report_name: str) -> Optional[dict]:
    normalized_vendor = vendor.lower()
    normalized_name = report_name.lower()

    # Search analysis reports
    for reports in sources.get("categories", {}).get("analysis", {}).values():
        for report in reports:
            if (
                normalized_vendor in report["vendor"].lower()
                and normalized_name in report["name"].lower()
            ):
                return report

    # Search survey reports
    for reports in sources.get("categories", {}).get("survey", {}).values():
        for report in reports:
            if (
                normalized_vendor in report["vendor"].lower()
                and normalized_name in report["name"].lower()
            ):
                return report

    return None


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", name)
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned.lower()


def fetch_report_page(url: str) -> str:
    print(f"Fetching: {url}")

    try:
        with httpx.Client(
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        ) as client:
            response = client.get(url)

        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}: {response.reason_phrase}")

        content_type = response.headers.get("content-type", "")

        if "application/pdf" in content_type:
            return "[PDF file - download manually from URL]"

        return response.text
    except Exception as error:
        print(f"Fetch failed: {error}", file=sys.stderr)
        return f"[Fetch failed: {error}]"


def extract_text_from_html(html: str) -> str:
    """Simple HTML to text conversion."""
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def create_summary_file(report: dict, content: str) -> str:
    vendor_dir = REPORTS_DIR / sanitize_filename(report["vendor"])
    vendor_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{sanitize_filename(report['name'])}-summary.md"
    filepath = vendor_dir / filename

    text = extract_text_from_html(content)
    preview = text[:2000]

    from datetime import datetime

    summary = f"""# {report['name']}

**Vendor:** {report['vendor']}
**URL:** {report['url']}
**Fetched:** {datetime.now().isoformat()[:10]}

## Landing Page Preview

{preview}{'[Truncated - see full page at URL above]' if len(text) > 2000 else ''}

## Notes

- Full report may require registration
- Check URL for download options
- PDF versions may be available
"""

    filepath.write_text(summary)
    return str(filepath)


def list_cached_reports() -> None:
    if not REPORTS_DIR.exists():
        print("No cached reports yet")
        return

    print("Cached Reports:\n")

    vendors = [d for d in sorted(REPORTS_DIR.iterdir()) if d.is_dir()]

    for vendor_dir in vendors:
        files = sorted(vendor_dir.iterdir())
        if files:
            print(f"  {vendor_dir.name}/")
            for f in files:
                print(f"    {f.name}")
            print()


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  python FetchReport.py <vendor> <report-name>")
        print("  python FetchReport.py --url <url>")
        print("  python FetchReport.py --list-cached")
        print()
        print("Examples:")
        print('  python FetchReport.py crowdstrike "global threat"')
        print("  python FetchReport.py verizon dbir")
        print("  python FetchReport.py --url https://example.com/report")
        return

    if args[0] == "--list-cached":
        list_cached_reports()
        return

    if args[0] == "--url" and len(args) > 1:
        url = args[1]
        content = fetch_report_page(url)

        parsed_url = urlparse(url)
        path_basename = os.path.basename(parsed_url.path) or "report"

        report = {
            "vendor": "custom",
            "name": path_basename,
            "url": url,
        }

        filepath = create_summary_file(report, content)
        print(f"Summary saved: {filepath}")
        return

    # Find report by vendor and name
    if len(args) >= 2:
        vendor = args[0]
        report_name = " ".join(args[1:])

        sources = load_sources()
        report = find_report(sources, vendor, report_name)

        if not report:
            print(f'Report not found: {vendor} "{report_name}"')
            print()
            print("Try searching:")
            print(f"  python ListSources.py --search {vendor}")
            return

        print(f"Found: {report['vendor']} - {report['name']}")
        print(f"   URL: {report['url']}\n")

        content = fetch_report_page(report["url"])
        filepath = create_summary_file(report, content)

        print(f"\nSummary saved: {filepath}")
        print()
        print("Note: Most reports require registration for full PDF.")
        print("   Visit the URL above to download the complete report.")
        return

    print("Invalid arguments. Run without args for usage.")


if __name__ == "__main__":
    main()
