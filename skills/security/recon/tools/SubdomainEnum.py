#!/usr/bin/env python3
"""
Domain Recon Aggregator

Aggregates subdomain enumeration from multiple sources:
- Subfinder (passive sources)
- Chaos (ProjectDiscovery database)
- Certificate Transparency (crt.sh)
- DNS enumeration (dnsx)

Usage:
  python SubdomainEnum.py example.com
  python SubdomainEnum.py example.com --json
  python SubdomainEnum.py example.com --resolve
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class ReconResult:
    domain: str
    subdomains: list[str] = field(default_factory=list)
    sources: dict[str, list[str]] = field(default_factory=dict)
    resolved: Optional[dict[str, list[str]]] = None
    stats: dict = field(default_factory=dict)


def run_subfinder(domain: str) -> list[str]:
    try:
        result = subprocess.run(
            ["subfinder", "-d", domain, "-silent", "-all"],
            capture_output=True, text=True, timeout=300,
        )
        return [line for line in result.stdout.strip().split("\n") if line]
    except Exception:
        print("[subfinder] Failed", file=sys.stderr)
        return []


def run_chaos(domain: str) -> list[str]:
    key = os.environ.get("PDCP_API_KEY")
    if not key:
        print("[chaos] No PDCP_API_KEY set", file=sys.stderr)
        return []
    try:
        result = subprocess.run(
            ["chaos", "-key", key, "-d", domain, "-silent"],
            capture_output=True, text=True, timeout=300,
        )
        return [line for line in result.stdout.strip().split("\n") if line]
    except Exception:
        print("[chaos] Failed", file=sys.stderr)
        return []


def run_crtsh(domain: str) -> list[str]:
    try:
        with httpx.Client(timeout=30) as client:
            response = client.get(f"https://crt.sh/?q=%.{domain}&output=json")
            if response.status_code != 200:
                return []
            data = response.json()
        names: set[str] = set()
        for cert in data:
            for name in cert.get("name_value", "").split("\n"):
                if name.endswith(domain) and not name.startswith("*"):
                    names.add(name.lower())
        return list(names)
    except Exception:
        print("[crt.sh] Failed", file=sys.stderr)
        return []


def resolve_subdomains(subdomains: list[str]) -> dict[str, list[str]]:
    resolved: dict[str, list[str]] = {}
    try:
        input_data = "\n".join(subdomains)
        result = subprocess.run(
            ["dnsx", "-silent", "-a", "-resp"],
            input=input_data, capture_output=True, text=True, timeout=300,
        )
        import re
        for line in result.stdout.strip().split("\n"):
            match = re.match(r"^(\S+)\s+\[(.+)\]$", line)
            if match:
                resolved[match.group(1)] = [s.strip() for s in match.group(2).split(",")]
    except Exception:
        print("[dnsx] Resolution failed", file=sys.stderr)
    return resolved


def main() -> None:
    args = sys.argv[1:]
    domain = next((a for a in args if not a.startswith("-")), None)
    json_output = "--json" in args
    resolve = "--resolve" in args

    if not domain:
        print("Usage: SubdomainEnum.py <domain> [--json] [--resolve]")
        sys.exit(1)

    start_time = time.time()
    print(f"[*] Starting recon for {domain}", file=sys.stderr)

    # Run sources (sequential in sync version)
    subfinder_results = run_subfinder(domain)
    chaos_results = run_chaos(domain)
    crtsh_results = run_crtsh(domain)

    # Deduplicate
    all_subdomains: set[str] = set()
    sources: dict[str, list[str]] = {
        "subfinder": subfinder_results,
        "chaos": chaos_results,
        "crtsh": crtsh_results,
    }

    for results in sources.values():
        for sub in results:
            all_subdomains.add(sub.lower())

    unique_subdomains = sorted(all_subdomains)

    # Optionally resolve
    resolved: Optional[dict[str, list[str]]] = None
    if resolve:
        print(f"[*] Resolving {len(unique_subdomains)} subdomains...", file=sys.stderr)
        resolved = resolve_subdomains(unique_subdomains)

    duration = (time.time() - start_time) * 1000  # ms

    result = ReconResult(
        domain=domain,
        subdomains=unique_subdomains,
        sources=sources,
        resolved=resolved,
        stats={
            "total": len(subfinder_results) + len(chaos_results) + len(crtsh_results),
            "unique": len(unique_subdomains),
            "bySource": {
                "subfinder": len(subfinder_results),
                "chaos": len(chaos_results),
                "crtsh": len(crtsh_results),
            },
            "duration": duration,
        },
    )

    if json_output:
        output = {
            "domain": result.domain,
            "subdomains": result.subdomains,
            "sources": result.sources,
            "resolved": result.resolved,
            "stats": result.stats,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n=== Domain Recon: {domain} ===\n")
        print(f"Subdomains ({len(unique_subdomains)} unique):")
        for sub in unique_subdomains:
            if resolved and sub in resolved:
                print(f"  {sub} -> {', '.join(resolved[sub])}")
            else:
                print(f"  {sub}")
        print("\nSources:")
        print(f"  subfinder: {len(subfinder_results)}")
        print(f"  chaos: {len(chaos_results)}")
        print(f"  crt.sh: {len(crtsh_results)}")
        print(f"\nCompleted in {duration / 1000:.1f}s")


if __name__ == "__main__":
    main()
