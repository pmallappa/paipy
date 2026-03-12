#!/usr/bin/env python3
"""Update bug bounty programs."""

from __future__ import annotations

import sys

from .tracker import BugBountyTracker


def main() -> None:
    tracker = BugBountyTracker()

    try:
        results = tracker.update()

        print("\n" + "=" * 60)
        print("UPDATE SUMMARY")
        print("=" * 60)
        print(f"New programs:        {len(results.new_programs)}")
        print(f"Scope expansions:    {len(results.scope_expansions)}")
        print(f"Upgraded to paid:    {len(results.upgraded_programs)}")
        print(f"Platforms checked:   {results.total_checked}")
        print(f"Duration:            {results.check_duration_ms / 1000:.1f}s")
        print("=" * 60)

        if results.new_programs:
            print("\nNEW PROGRAMS:")
            for i, p in enumerate(results.new_programs, 1):
                print(f"\n{i}. [{p.platform.upper()}] {p.name}")
                print(f"   URL: {p.url}")
                print(f"   Bounty: {'Yes' if p.offers_bounties else 'No (VDP only)'}")
                print(f"   Max Severity: {p.max_severity or 'Unknown'}")
                scopes_preview = ", ".join(p.key_scopes[:3])
                if len(p.key_scopes) > 3:
                    scopes_preview += "..."
                print(f"   Scopes: {scopes_preview}")

        if results.upgraded_programs:
            print("\nUPGRADED TO PAID:")
            for i, p in enumerate(results.upgraded_programs, 1):
                print(f"{i}. [{p.platform.upper()}] {p.name} - {p.url}")

        if results.scope_expansions:
            print("\nSCOPE EXPANSIONS:")
            for i, p in enumerate(results.scope_expansions, 1):
                print(f"{i}. [{p.platform.upper()}] {p.name} - {len(p.key_scopes)} scopes")

    except Exception as error:
        print(f"Update failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
