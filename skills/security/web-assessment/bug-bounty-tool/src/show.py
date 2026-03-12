#!/usr/bin/env python3
"""Show recent bug bounty discoveries."""

from __future__ import annotations

import sys
from datetime import datetime

from .tracker import BugBountyTracker


def main() -> None:
    args = sys.argv[1:]
    tracker = BugBountyTracker()

    try:
        hours = 24  # Default to last 24 hours
        search_query = ""

        i = 0
        while i < len(args):
            if args[i] == "--last" and i + 1 < len(args):
                value = args[i + 1]
                if value.endswith("h"):
                    hours = int(value[:-1])
                elif value.endswith("d"):
                    hours = int(value[:-1]) * 24
                else:
                    hours = int(value)
                i += 1
            elif args[i] == "--search" and i + 1 < len(args):
                search_query = args[i + 1]
                i += 1
            elif args[i] == "--all":
                hours = 24 * 365
            i += 1

        if search_query:
            print(f'Searching for: "{search_query}"\n')
            programs = tracker.search_programs(search_query)
        else:
            print(f"Bug bounty programs discovered in the last {hours}h\n")
            programs = tracker.get_recent_discoveries(hours)

        if not programs:
            print("No programs found.")
            return

        for i, p in enumerate(programs, 1):
            change_info = f" ({p.change_type.replace('_', ' ')})" if p.change_type else ""
            print(f"{i}. [{p.platform.upper()}] {p.name}{change_info}")
            print(f"   URL: {p.url}")
            print(f"   Bounty: {'Paid' if p.offers_bounties else 'VDP only'}")

            if p.max_severity:
                severity_map = {
                    "critical": "[CRIT]",
                    "high": "[HIGH]",
                    "medium": "[MED]",
                    "low": "[LOW]",
                }
                print(f"   Max Severity: {severity_map.get(p.max_severity, '')} {p.max_severity.upper()}")

            print(f"   Scopes ({len(p.key_scopes)}):")
            for scope in p.key_scopes[:5]:
                print(f"     - {scope}")
            if len(p.key_scopes) > 5:
                print(f"     ... and {len(p.key_scopes) - 5} more")

            print(f"   Discovered: {p.discovered_at}")
            print()

        print(f"\nTotal: {len(programs)} program(s)")
        print('\nTip: Use "initiate-recon <number>" to start testing a program')

    except Exception as error:
        print(f"Failed to show programs: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
