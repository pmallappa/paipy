#!/usr/bin/env python3
"""Initiate reconnaissance on a bug bounty program."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .config import CONFIG
from .tracker import BugBountyTracker


def main() -> None:
    args = sys.argv[1:]

    if not args:
        print("Usage: python -m recon <program_number>", file=sys.stderr)
        print("Example: python -m recon 1", file=sys.stderr)
        sys.exit(1)

    try:
        program_index = int(args[0]) - 1
    except ValueError:
        print("Invalid program number", file=sys.stderr)
        sys.exit(1)

    if program_index < 0:
        print("Invalid program number", file=sys.stderr)
        sys.exit(1)

    tracker = BugBountyTracker()

    try:
        # Get recent programs
        programs = tracker.get_recent_discoveries(24 * 7)  # Last 7 days

        if program_index >= len(programs):
            print(f"Program #{program_index + 1} not found. Only {len(programs)} programs available.", file=sys.stderr)
            sys.exit(1)

        program = programs[program_index]

        print("INITIATING RECONNAISSANCE\n")
        print(f"Target: {program.name}")
        print(f"Platform: {program.platform.upper()}")
        print(f"URL: {program.url}")
        print(f"Bounty: {'Paid' if program.offers_bounties else 'VDP only'}")
        print(f"Scopes: {len(program.key_scopes)} domains\n")

        # Create recon configuration file
        recon_config = {
            "program": {
                "name": program.name,
                "platform": program.platform,
                "url": program.url,
                "offers_bounties": program.offers_bounties,
            },
            "scopes": program.key_scopes,
            "max_severity": program.max_severity,
            "discovered_at": program.discovered_at,
            "recon_started_at": datetime.now().isoformat(),
        }

        timestamp = datetime.now().isoformat().replace(":", "-").replace(".", "-")[:19]
        logs_dir = os.path.expanduser(CONFIG["paths"]["logs"])
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        config_path = os.path.join(logs_dir, f"recon-{program.handle}-{timestamp}.json")

        Path(config_path).write_text(json.dumps(recon_config, indent=2))

        print(f"Recon configuration saved to:")
        print(f"   {config_path}\n")

        # Generate pentester agent prompt
        print("PENTESTER AGENT INSTRUCTIONS:\n")
        print("Use this information to launch the pentester agent:\n")

        print(f"# Target: {program.name}")
        print(f"# Platform: {program.platform}")
        print(f"# Program URL: {program.url}")
        print(f"# Bounty Type: {'Paid Bounty' if program.offers_bounties else 'VDP Only'}")
        print()
        print("scopes = [")
        for scope in program.key_scopes[:10]:
            print(f'  "{scope}",')
        if len(program.key_scopes) > 10:
            print(f"  # ... and {len(program.key_scopes) - 10} more scopes")
        print("]\n")

        print("RECOMMENDED RECONNAISSANCE WORKFLOW:\n")
        print("Phase 1: Asset Discovery")
        print("  - Subdomain enumeration (Amass, Subfinder)")
        print("  - Live host validation (httpx)")
        print("  - Port scanning (nmap)")
        print("  - Technology detection (Wappalyzer, whatweb)")
        print()
        print("Phase 2: Content Discovery")
        print("  - Directory/file fuzzing (ffuf, dirsearch)")
        print("  - JavaScript analysis (LinkFinder, JSFinder)")
        print("  - API endpoint discovery (Kiterunner)")
        print()
        print("Phase 3: Vulnerability Scanning")
        print("  - Nuclei templates")
        print("  - Custom security checks")
        print("  - Manual testing of interesting findings")
        print()

        print("NEXT STEPS:\n")
        print("1. Review program rules and guidelines:")
        print(f"   {program.url}")
        print()
        print("2. Launch pentester agent with scopes:")
        print(f'   Task: "Do recon on {program.name} bug bounty program"')
        print(f"   Scopes: {', '.join(program.key_scopes[:3])}...")
        print()
        print("3. Document findings and submit reports")
        print()

        print("IMPORTANT REMINDERS:\n")
        print("  - Only test in-scope assets")
        print("  - Follow responsible disclosure guidelines")
        print("  - Check for rate limiting requirements")
        print("  - Do not perform DoS attacks")
        print("  - Respect program rules and boundaries")
        print()

    except Exception as error:
        print(f"Failed to initiate reconnaissance: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
