#!/usr/bin/env python3
"""Initialize bug bounty tracker."""

from __future__ import annotations

import sys

from .tracker import BugBountyTracker


def main() -> None:
    tracker = BugBountyTracker()

    try:
        tracker.initialize()
    except Exception as error:
        print(f"Initialization failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
