#!/usr/bin/env python3
"""
BountyPrograms - Bug bounty program discovery and monitoring
Aggregates data from ProjectDiscovery Chaos, HackerOne, and Bugcrowd

Usage:
  python BountyPrograms.py [command] [options]

Commands:
  list          List all known public bounty programs
  new           Show recently added programs
  search        Search for programs by name/domain
  check         Check if a domain has a bounty program
  update        Update local program cache from sources
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class BountyProgram:
    name: str
    url: str
    bounty: bool
    swag: bool
    domains: list[str] = field(default_factory=list)
    platform: Optional[str] = None
    added_date: Optional[str] = None
    max_bounty: Optional[str] = None
    in_scope: Optional[list[str]] = None


@dataclass
class BountyProgramsResult:
    command: str
    timestamp: str
    total_programs: int
    programs: list[BountyProgram] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ProjectDiscovery Chaos bounty list URL
CHAOS_BOUNTY_URL = "https://raw.githubusercontent.com/projectdiscovery/public-bugbounty-programs/main/chaos-bugbounty-list.json"

# Local cache path
CACHE_DIR = os.path.join(os.environ.get("HOME", ""), ".claude/skills/security/recon/data")
CACHE_FILE = os.path.join(CACHE_DIR, "BountyPrograms.json")
CACHE_MAX_AGE_HOURS = 24


def ensure_cache_dir() -> None:
    Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)


def get_cached_programs() -> Optional[list[BountyProgram]]:
    try:
        cache_path = Path(CACHE_FILE)
        if not cache_path.exists():
            return None

        stat = cache_path.stat()
        age_hours = (time.time() - stat.st_mtime) / 3600
        if age_hours > CACHE_MAX_AGE_HOURS:
            return None

        data = json.loads(cache_path.read_text())
        return [
            BountyProgram(
                name=p["name"],
                url=p["url"],
                bounty=p["bounty"],
                swag=p["swag"],
                domains=p.get("domains", []),
                platform=p.get("platform"),
            )
            for p in data.get("programs", [])
        ]
    except Exception:
        return None


def update_cache(programs: list[BountyProgram]) -> None:
    ensure_cache_dir()
    data = {
        "lastUpdated": datetime.now().isoformat(),
        "programs": [
            {
                "name": p.name,
                "url": p.url,
                "bounty": p.bounty,
                "swag": p.swag,
                "domains": p.domains,
                "platform": p.platform,
            }
            for p in programs
        ],
    }
    Path(CACHE_FILE).write_text(json.dumps(data, indent=2))


def fetch_chaos_programs() -> list[BountyProgram]:
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(CHAOS_BOUNTY_URL)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")

        data = response.json()
        return [
            BountyProgram(
                name=p["name"],
                url=p["url"],
                bounty=p.get("bounty", False),
                swag=p.get("swag", False),
                domains=p.get("domains", []),
                platform="chaos",
            )
            for p in data.get("programs", [])
        ]
    except Exception as error:
        print(f"Failed to fetch Chaos programs: {error}", file=sys.stderr)
        return []


def get_all_programs(force_update: bool = False) -> list[BountyProgram]:
    if not force_update:
        cached = get_cached_programs()
        if cached:
            return cached

    print("Fetching fresh bounty program data...", file=sys.stderr)
    programs = fetch_chaos_programs()

    if programs:
        update_cache(programs)

    return programs


def list_programs(bounty_only: bool = False, swag_only: bool = False) -> BountyProgramsResult:
    programs = get_all_programs()
    filtered = programs

    if bounty_only:
        filtered = [p for p in filtered if p.bounty]
    if swag_only:
        filtered = [p for p in filtered if p.swag]

    return BountyProgramsResult(
        command="list",
        timestamp=datetime.now().isoformat(),
        total_programs=len(filtered),
        programs=filtered,
    )


def search_programs(query: str) -> BountyProgramsResult:
    programs = get_all_programs()
    query_lower = query.lower()

    matched = [
        p for p in programs
        if query_lower in p.name.lower()
        or query_lower in p.url.lower()
        or any(query_lower in d.lower() for d in p.domains)
    ]

    return BountyProgramsResult(
        command="search",
        timestamp=datetime.now().isoformat(),
        total_programs=len(matched),
        programs=matched,
    )


def check_domain(domain: str) -> BountyProgramsResult:
    programs = get_all_programs()
    domain_lower = domain.lower().removeprefix("www.")

    matched = [
        p for p in programs
        if any(
            (prog_domain := d.lower().removeprefix("*.").removeprefix("www.")) == domain_lower
            or domain_lower.endswith(f".{prog_domain}")
            or prog_domain.endswith(f".{domain_lower}")
            for d in p.domains
        )
    ]

    return BountyProgramsResult(
        command="check",
        timestamp=datetime.now().isoformat(),
        total_programs=len(matched),
        programs=matched,
    )


def update_programs() -> BountyProgramsResult:
    programs = get_all_programs(force_update=True)

    return BountyProgramsResult(
        command="update",
        timestamp=datetime.now().isoformat(),
        total_programs=len(programs),
        errors=["Failed to fetch programs"] if not programs else [],
    )


def get_new_programs(days: int = 7) -> BountyProgramsResult:
    programs = get_all_programs()
    bounty_programs = [p for p in programs if p.bounty]

    return BountyProgramsResult(
        command="new",
        timestamp=datetime.now().isoformat(),
        total_programs=len(bounty_programs),
        programs=bounty_programs[:50],
        errors=["Note: 'new' command currently shows bounty programs. Full tracking coming soon."],
    )


def parse_args(args: list[str]) -> tuple[str, str, dict]:
    options: dict = {}
    command = "list"
    query = ""
    i = 0

    while i < len(args):
        arg = args[i]
        next_arg = args[i + 1] if i + 1 < len(args) else ""

        if arg in ("list", "new", "search", "check", "update"):
            command = arg
        elif arg == "--bounty-only":
            options["bounty_only"] = True
        elif arg == "--swag-only":
            options["swag_only"] = True
        elif arg == "--days":
            options["days"] = int(next_arg)
            i += 1
        elif arg == "--json":
            options["json"] = True
        elif arg in ("-h", "--help"):
            print("""
BountyPrograms - Bug bounty program discovery

Usage:
  python BountyPrograms.py [command] [options]

Commands:
  list              List all known public bounty programs
  new               Show recently added programs
  search <query>    Search for programs by name/domain
  check <domain>    Check if a domain has a bounty program
  update            Update local program cache from sources

Options:
  --bounty-only     Only show programs with cash bounties
  --swag-only       Only show programs with swag rewards
  --days <n>        For 'new' command: programs added in last N days
  --json            Output as JSON
""")
            sys.exit(0)
        else:
            if not arg.startswith("-") and arg not in ("list", "new", "search", "check", "update"):
                query = arg
        i += 1

    return command, query, options


if __name__ == "__main__":
    args = sys.argv[1:]
    command, query, options = parse_args(args)

    result: BountyProgramsResult

    if command == "list":
        result = list_programs(
            bounty_only=options.get("bounty_only", False),
            swag_only=options.get("swag_only", False),
        )
    elif command == "search":
        if not query:
            print("Error: Search query required", file=sys.stderr)
            print("Usage: python BountyPrograms.py search <query>", file=sys.stderr)
            sys.exit(1)
        result = search_programs(query)
    elif command == "check":
        if not query:
            print("Error: Domain required", file=sys.stderr)
            print("Usage: python BountyPrograms.py check <domain>", file=sys.stderr)
            sys.exit(1)
        result = check_domain(query)
    elif command == "update":
        result = update_programs()
    elif command == "new":
        result = get_new_programs(options.get("days", 7))
    else:
        result = list_programs()

    if options.get("json"):
        output = {
            "command": result.command,
            "timestamp": result.timestamp,
            "totalPrograms": result.total_programs,
            "programs": [
                {
                    "name": p.name,
                    "url": p.url,
                    "bounty": p.bounty,
                    "swag": p.swag,
                    "domains": p.domains,
                    "platform": p.platform,
                }
                for p in result.programs
            ],
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nBug Bounty Programs - {result.command}")
        print(f"Timestamp: {result.timestamp}")
        print(f"Total: {result.total_programs} programs\n")

        if command == "update":
            if not result.errors:
                print(f"Cache updated with {result.total_programs} programs")
            else:
                print(f"Update failed: {', '.join(result.errors)}")
        elif not result.programs:
            print("  No programs found")
        else:
            for p in result.programs[:30]:
                badges = []
                if p.bounty:
                    badges.append("[BOUNTY]")
                if p.swag:
                    badges.append("[SWAG]")
                print(f"  {' '.join(badges)} {p.name}")
                print(f"     URL: {p.url}")
                if p.domains:
                    display_domains = ", ".join(p.domains[:5])
                    more = f" +{len(p.domains) - 5} more" if len(p.domains) > 5 else ""
                    print(f"     Scope: {display_domains}{more}")
                print()

            if len(result.programs) > 30:
                print(f"  ... and {len(result.programs) - 30} more programs")
                print("  Use --json for full list")

        if result.errors and command != "update":
            print("\nNotes:")
            for err in result.errors:
                print(f"  {err}")
