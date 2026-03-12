#!/usr/bin/env python3
"""
PathDiscovery - Directory and file path fuzzing
Wraps ffuf for discovering hidden paths, directories, and files on web servers

Usage:
  python PathDiscovery.py <url> [options]

Examples:
  python PathDiscovery.py https://example.com
  python PathDiscovery.py https://example.com -w /path/to/wordlist.txt
  python PathDiscovery.py https://example.com --extensions php,html,js
  python PathDiscovery.py https://example.com --threads 100 --json
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PathDiscoveryOptions:
    wordlist: Optional[str] = None
    extensions: Optional[list[str]] = None
    threads: Optional[int] = None
    timeout: Optional[int] = None
    follow_redirects: bool = False
    match_codes: Optional[str] = None
    filter_codes: Optional[str] = None
    recursion: bool = False
    recursion_depth: Optional[int] = None
    headers: Optional[list[str]] = None
    cookies: Optional[str] = None
    method: Optional[str] = None
    data: Optional[str] = None
    proxy: Optional[str] = None
    rate: Optional[int] = None
    json_output: bool = False
    silent: bool = False
    auto_calibrate: bool = True


@dataclass
class PathResult:
    url: str
    status: int
    length: int
    words: int
    lines: int
    content_type: Optional[str] = None
    redirect_location: Optional[str] = None


@dataclass
class PathDiscoveryResult:
    target: str
    wordlist: str = ""
    timestamp: str = ""
    total_found: int = 0
    paths: list[PathResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# Default wordlists (SecLists paths)
DEFAULT_WORDLISTS = [
    "/opt/homebrew/share/seclists/Discovery/Web-Content/raft-medium-directories.txt",
    "/usr/share/seclists/Discovery/Web-Content/raft-medium-directories.txt",
    "/opt/seclists/Discovery/Web-Content/raft-medium-directories.txt",
    f"{os.environ.get('HOME', '')}/wordlists/raft-medium-directories.txt",
]


def find_wordlist(custom_path: Optional[str] = None) -> Optional[str]:
    if custom_path:
        if Path(custom_path).exists():
            return custom_path
        print(f"Wordlist not found: {custom_path}", file=sys.stderr)
        return None

    for path in DEFAULT_WORDLISTS:
        if Path(path).exists():
            return path

    return None


def run_path_discovery(target_url: str, options: Optional[PathDiscoveryOptions] = None) -> PathDiscoveryResult:
    if options is None:
        options = PathDiscoveryOptions()

    result = PathDiscoveryResult(
        target=target_url,
        timestamp=datetime.now().isoformat(),
    )

    # Find wordlist
    wordlist = find_wordlist(options.wordlist)
    if not wordlist:
        result.errors.append("No wordlist found. Install SecLists or provide a custom wordlist with -w")
        return result
    result.wordlist = wordlist

    # Build ffuf command
    fuzz_url = target_url if "FUZZ" in target_url else f"{target_url.rstrip('/')}/FUZZ"
    args: list[str] = [
        "ffuf",
        "-u", fuzz_url,
        "-w", wordlist,
        "-json",
        "-noninteractive",
    ]

    # Threading
    args.extend(["-t", str(options.threads or 40)])

    # Timeout
    if options.timeout:
        args.extend(["-timeout", str(options.timeout)])

    # Follow redirects
    if options.follow_redirects:
        args.append("-r")

    # Auto calibrate
    if options.auto_calibrate:
        args.append("-ac")

    # Match/filter status codes
    if options.match_codes:
        args.extend(["-mc", options.match_codes])
    if options.filter_codes:
        args.extend(["-fc", options.filter_codes])

    # Recursion
    if options.recursion:
        args.append("-recursion")
        if options.recursion_depth:
            args.extend(["-recursion-depth", str(options.recursion_depth)])

    # Extensions
    if options.extensions:
        args.extend(["-e", ",".join(options.extensions)])

    # Headers
    if options.headers:
        for header in options.headers:
            args.extend(["-H", header])

    # Cookies
    if options.cookies:
        args.extend(["-b", options.cookies])

    # HTTP method
    if options.method:
        args.extend(["-X", options.method])

    # POST data
    if options.data:
        args.extend(["-d", options.data])

    # Proxy
    if options.proxy:
        args.extend(["-x", options.proxy])

    # Rate limiting
    if options.rate:
        args.extend(["-rate", str(options.rate)])

    # Silent mode
    if options.silent:
        args.append("-s")

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600)

        if proc.stderr and not options.silent:
            errors = [
                line for line in proc.stderr.split("\n")
                if "error" in line.lower() or "Error" in line or "FATAL" in line
            ]
            result.errors.extend(errors)

        # Parse JSON lines output
        lines = [line for line in proc.stdout.strip().split("\n") if line]

        for line in lines:
            try:
                data = json.loads(line)
                if data.get("results") and isinstance(data["results"], list):
                    for r in data["results"]:
                        result.paths.append(PathResult(
                            url=r.get("url", ""),
                            status=r.get("status", 0),
                            length=r.get("length", 0),
                            words=r.get("words", 0),
                            lines=r.get("lines", 0),
                            content_type=r.get("content_type"),
                            redirect_location=r.get("redirectlocation"),
                        ))
            except json.JSONDecodeError:
                pass  # Skip non-JSON lines

        result.total_found = len(result.paths)

    except Exception as error:
        result.errors.append(f"ffuf execution failed: {error}")

    return result


def parse_args(args: list[str]) -> tuple[str, PathDiscoveryOptions]:
    options = PathDiscoveryOptions()
    url = ""
    i = 0

    while i < len(args):
        arg = args[i]
        next_arg = args[i + 1] if i + 1 < len(args) else ""

        if arg in ("-w", "--wordlist"):
            options.wordlist = next_arg
            i += 1
        elif arg in ("-e", "--extensions"):
            options.extensions = next_arg.split(",")
            i += 1
        elif arg in ("-t", "--threads"):
            options.threads = int(next_arg)
            i += 1
        elif arg == "--timeout":
            options.timeout = int(next_arg)
            i += 1
        elif arg in ("-r", "--follow-redirects"):
            options.follow_redirects = True
        elif arg in ("-mc", "--match-codes"):
            options.match_codes = next_arg
            i += 1
        elif arg in ("-fc", "--filter-codes"):
            options.filter_codes = next_arg
            i += 1
        elif arg == "--recursion":
            options.recursion = True
        elif arg == "--recursion-depth":
            options.recursion_depth = int(next_arg)
            i += 1
        elif arg in ("-H", "--header"):
            if options.headers is None:
                options.headers = []
            options.headers.append(next_arg)
            i += 1
        elif arg in ("-b", "--cookies"):
            options.cookies = next_arg
            i += 1
        elif arg in ("-X", "--method"):
            options.method = next_arg
            i += 1
        elif arg in ("-d", "--data"):
            options.data = next_arg
            i += 1
        elif arg == "--proxy":
            options.proxy = next_arg
            i += 1
        elif arg == "--rate":
            options.rate = int(next_arg)
            i += 1
        elif arg == "--json":
            options.json_output = True
        elif arg in ("-s", "--silent"):
            options.silent = True
        elif arg == "--no-auto-calibrate":
            options.auto_calibrate = False
        elif arg in ("-h", "--help"):
            print("""
PathDiscovery - Directory and file path fuzzing

Usage:
  python PathDiscovery.py <url> [options]

Arguments:
  url                     Target URL (FUZZ keyword optional, defaults to URL/FUZZ)

Options:
  -w, --wordlist <path>   Custom wordlist path (default: SecLists raft-medium-directories)
  -e, --extensions <ext>  Extensions to append (comma-separated: php,html,js)
  -t, --threads <n>       Concurrent threads (default: 40)
  --timeout <seconds>     HTTP request timeout
  -r, --follow-redirects  Follow HTTP redirects
  -mc, --match-codes      Match status codes
  -fc, --filter-codes     Filter out status codes
  --recursion             Enable recursive scanning
  --recursion-depth <n>   Maximum recursion depth
  -H, --header <header>   Custom header (can use multiple times)
  -b, --cookies <cookies> Cookie string
  -X, --method <method>   HTTP method (default: GET)
  -d, --data <data>       POST data
  --proxy <url>           Proxy URL (HTTP or SOCKS5)
  --rate <n>              Requests per second
  --json                  Output as JSON
  -s, --silent            Silent mode (minimal output)
  --no-auto-calibrate     Disable auto-calibration
""")
            sys.exit(0)
        else:
            if not arg.startswith("-") and not url:
                url = arg
        i += 1

    return url, options


if __name__ == "__main__":
    args = sys.argv[1:]
    url, options = parse_args(args)

    if not url:
        print("Error: Target URL required", file=sys.stderr)
        print("Usage: python PathDiscovery.py <url> [options]", file=sys.stderr)
        print("Use --help for more information", file=sys.stderr)
        sys.exit(1)

    result = run_path_discovery(url, options)

    if options.json_output:
        output = {
            "target": result.target,
            "wordlist": result.wordlist,
            "timestamp": result.timestamp,
            "totalFound": result.total_found,
            "paths": [
                {
                    "url": p.url,
                    "status": p.status,
                    "length": p.length,
                    "words": p.words,
                    "lines": p.lines,
                    "contentType": p.content_type,
                    "redirectLocation": p.redirect_location,
                }
                for p in result.paths
            ],
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nPath Discovery: {result.target}")
        print(f"Wordlist: {result.wordlist}")
        print(f"Timestamp: {result.timestamp}")
        print(f"\nFound {result.total_found} paths:\n")

        if not result.paths:
            print("  No paths discovered")
        else:
            by_status: dict[int, list[PathResult]] = {}
            for path in result.paths:
                by_status.setdefault(path.status, []).append(path)

            for status in sorted(by_status.keys()):
                paths = by_status[status]
                print(f"  [{status}] {len(paths)} paths:")
                for p in paths[:20]:
                    print(f"    {p.url} ({p.length} bytes)")
                if len(paths) > 20:
                    print(f"    ... and {len(paths) - 20} more")
                print()

        if result.errors:
            print("\nErrors:")
            for err in result.errors:
                print(f"  {err}")
