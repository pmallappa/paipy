#!/usr/bin/env python3
"""
EndpointDiscovery - Extract endpoints from JavaScript at scale
Parses large volumes of JS to find API endpoints, paths, and secrets

Usage:
  python EndpointDiscovery.py <target> [options]

Modes:
  URL mode:   Crawl target and extract endpoints from JS files
  File mode:  Parse local JS files directly (for offline analysis)
  Stdin mode: Pipe JS content directly

Examples:
  python EndpointDiscovery.py https://example.com
  python EndpointDiscovery.py https://example.com --deep
  python EndpointDiscovery.py ./js-files/ --local
  cat bundle.js | python EndpointDiscovery.py --stdin
  python EndpointDiscovery.py urls.txt --batch
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class Endpoint:
    path: str
    type: str  # "api" | "path" | "url" | "websocket" | "graphql" | "unknown"
    source: Optional[str] = None
    line: Optional[int] = None


@dataclass
class Secret:
    type: str
    value: str
    source: Optional[str] = None
    line: Optional[int] = None


@dataclass
class EndpointDiscoveryResult:
    target: str
    timestamp: str = ""
    mode: str = ""
    js_files_processed: int = 0
    endpoints: list[Endpoint] = field(default_factory=list)
    secrets: list[Secret] = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


@dataclass
class EndpointDiscoveryOptions:
    deep: bool = False
    local: bool = False
    stdin: bool = False
    batch: bool = False
    depth: Optional[int] = None
    threads: Optional[int] = None
    timeout: Optional[int] = None
    headless: bool = False
    include_secrets: bool = False
    output_dir: Optional[str] = None
    json_output: bool = False
    silent: bool = False


# Regex patterns for endpoint extraction
ENDPOINT_PATTERNS: dict[str, re.Pattern] = {
    "apiPath": re.compile(r"""["'`](/api/[^"'`\s]{1,200})["'`]"""),
    "apiV": re.compile(r"""["'`](/v[0-9]+/[^"'`\s]{1,200})["'`]"""),
    "restPath": re.compile(
        r"""["'`](/(?:users?|admin|auth|login|logout|register|account|profile|settings|config|data|search|upload|download|export|import|webhook|callback|graphql|query|mutation)[^"'`\s]{0,150})["'`]""",
        re.IGNORECASE,
    ),
    "fullUrl": re.compile(r"""["'`](https?://[^"'`\s]{5,500})["'`]"""),
    "relativePath": re.compile(r"""["'`](/[a-zA-Z0-9_\-]{1,50}(?:/[a-zA-Z0-9_\-.]{1,100}){0,10})["'`]"""),
    "websocket": re.compile(r"""["'`](wss?://[^"'`\s]{5,300})["'`]"""),
    "graphql": re.compile(r"""["'`](/graphql[^"'`\s]{0,100})["'`]""", re.IGNORECASE),
    "pathAssign": re.compile(
        r"""(?:path|url|endpoint|uri|href|src|action|route)\s*[=:]\s*["'`]([^"'`\s]{2,300})["'`]""",
        re.IGNORECASE,
    ),
    "fetchCall": re.compile(
        r"""(?:fetch|axios|get|post|put|delete|patch)\s*\(\s*["'`]([^"'`\s]{2,300})["'`]""",
        re.IGNORECASE,
    ),
    "templatePath": re.compile(r"""`[^`]*(?:\$\{[^}]+\})?/[a-zA-Z][^`]{1,200}`"""),
}

# Secret patterns
SECRET_PATTERNS: dict[str, re.Pattern] = {
    "awsKey": re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[A-Z0-9]{16}"),
    "awsSecret": re.compile(r"""["'`]([A-Za-z0-9/+=]{40})["'`]"""),
    "googleApi": re.compile(r"AIza[A-Za-z0-9_-]{35}"),
    "githubToken": re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"),
    "stripeKey": re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{24,}"),
    "jwtToken": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "privateKey": re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
    "bearer": re.compile(r"""["'`]Bearer\s+[A-Za-z0-9_\-.]{20,}["'`]"""),
    "apiKey": re.compile(
        r"""["'`](?:api[_-]?key|apikey|api[_-]?secret|access[_-]?token|auth[_-]?token)["']*\s*[:=]\s*["'`]([^"'`\s]{10,100})["'`]""",
        re.IGNORECASE,
    ),
    "slackToken": re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    "twilioKey": re.compile(r"SK[a-f0-9]{32}"),
    "sendgridKey": re.compile(r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}"),
}

# Skip patterns
SKIP_PATTERNS = [
    re.compile(r"^/\*"),
    re.compile(r"^/$"),
    re.compile(r"\.(css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot|map)$", re.IGNORECASE),
    re.compile(r"^data:"),
    re.compile(r"^javascript:"),
    re.compile(r"^#"),
    re.compile(r"^mailto:"),
    re.compile(r"node_modules"),
    re.compile(r"webpack"),
    re.compile(r"sourcemap"),
    re.compile(r"^\s*$"),
    re.compile(r"^[0-9]+$"),
    re.compile(r"^[a-f0-9]{32,}$", re.IGNORECASE),
]


def classify_endpoint(path: str) -> str:
    lower = path.lower()
    if "graphql" in lower:
        return "graphql"
    if path.startswith("ws://") or path.startswith("wss://"):
        return "websocket"
    if path.startswith("http://") or path.startswith("https://"):
        return "url"
    if "/api/" in lower or re.search(r"/v[0-9]+/", lower):
        return "api"
    if path.startswith("/"):
        return "path"
    return "unknown"


def should_skip_path(path: str) -> bool:
    return any(p.search(path) for p in SKIP_PATTERNS)


def extract_endpoints_from_js(
    content: str, source: Optional[str] = None,
) -> tuple[list[Endpoint], list[Secret]]:
    endpoints: list[Endpoint] = []
    secrets: list[Secret] = []
    seen_paths: set[str] = set()

    for _name, pattern in ENDPOINT_PATTERNS.items():
        for match in pattern.finditer(content):
            path = match.group(1) if match.lastindex else match.group(0)
            if should_skip_path(path):
                continue
            if path in seen_paths:
                continue
            seen_paths.add(path)
            endpoints.append(Endpoint(
                path=path,
                type=classify_endpoint(path),
                source=source,
            ))

    for type_name, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(content):
            value = match.group(1) if match.lastindex else match.group(0)
            if len(value) < 10 or len(value) > 500:
                continue
            secrets.append(Secret(
                type=type_name,
                value=value[:50] + ("..." if len(value) > 50 else ""),
                source=source,
            ))

    return endpoints, secrets


def crawl_with_katana(target: str, options: EndpointDiscoveryOptions) -> list[str]:
    args = ["katana", "-u", target, "-jc"]

    if options.deep:
        args.append("-jsl")

    args.extend(["-d", str(options.depth or 3)])
    args.extend(["-ct", f"{options.timeout or 30}s"])

    if options.threads:
        args.extend(["-c", str(options.threads)])

    if options.headless:
        args.append("-hl")

    args.extend(["-silent", "-nc", "-f", "js"])

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600)
        return [line for line in proc.stdout.strip().split("\n") if line]
    except Exception as error:
        print(f"Katana error: {error}", file=sys.stderr)
        return []


def fetch_js_content(urls: list[str]) -> dict[str, str]:
    results: dict[str, str] = {}
    batch_size = 10

    with httpx.Client(
        timeout=10,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
    ) as client:
        for i in range(0, len(urls), batch_size):
            batch = urls[i : i + batch_size]
            for url in batch:
                try:
                    response = client.get(url)
                    if response.status_code == 200:
                        results[url] = response.text
                except Exception:
                    pass

    return results


def process_local_files(directory: str) -> dict[str, str]:
    results: dict[str, str] = {}
    path = Path(directory)

    for ext in ("*.js", "*.mjs", "*.jsx"):
        for file_path in path.rglob(ext):
            try:
                results[str(file_path)] = file_path.read_text(errors="ignore")
            except Exception:
                pass

    return results


def run_endpoint_discovery(
    target: str, options: Optional[EndpointDiscoveryOptions] = None,
) -> EndpointDiscoveryResult:
    if options is None:
        options = EndpointDiscoveryOptions()

    mode = "local" if options.local else "stdin" if options.stdin else "batch" if options.batch else "crawl"
    result = EndpointDiscoveryResult(
        target=target,
        timestamp=datetime.now().isoformat(),
        mode=mode,
        stats={"totalEndpoints": 0, "byType": {}, "uniquePaths": 0},
    )

    try:
        if options.stdin:
            content = sys.stdin.read()
            js_contents = {"stdin": content}
        elif options.local:
            js_contents = process_local_files(target)
        elif options.batch:
            urls = [u for u in Path(target).read_text().strip().split("\n") if u]
            js_urls = [u for u in urls if u.endswith(".js") or ".js?" in u]
            js_contents = fetch_js_content(js_urls)
        else:
            if not options.silent:
                print(f"Crawling {target} for JS files...", file=sys.stderr)
            js_urls = crawl_with_katana(target, options)
            if not options.silent:
                print(f"Found {len(js_urls)} JS files, fetching content...", file=sys.stderr)
            js_contents = fetch_js_content(js_urls)

        result.js_files_processed = len(js_contents)

        all_endpoints: list[Endpoint] = []
        all_secrets: list[Secret] = []
        seen_paths: set[str] = set()

        for source, content in js_contents.items():
            endpoints, secrets = extract_endpoints_from_js(content, source)
            for ep in endpoints:
                if ep.path not in seen_paths:
                    seen_paths.add(ep.path)
                    all_endpoints.append(ep)
            if options.include_secrets:
                all_secrets.extend(secrets)

        result.endpoints = sorted(all_endpoints, key=lambda e: e.path)
        result.secrets = all_secrets

        result.stats["totalEndpoints"] = len(result.endpoints)
        result.stats["uniquePaths"] = len(seen_paths)

        for ep in result.endpoints:
            result.stats["byType"][ep.type] = result.stats["byType"].get(ep.type, 0) + 1

    except Exception as error:
        result.errors.append(f"Processing error: {error}")

    return result


def parse_args(args: list[str]) -> tuple[str, EndpointDiscoveryOptions]:
    options = EndpointDiscoveryOptions()
    target = ""
    i = 0

    while i < len(args):
        arg = args[i]
        next_arg = args[i + 1] if i + 1 < len(args) else ""

        if arg == "--deep":
            options.deep = True
        elif arg in ("--local", "-l"):
            options.local = True
        elif arg == "--stdin":
            options.stdin = True
        elif arg in ("--batch", "-b"):
            options.batch = True
        elif arg in ("-d", "--depth"):
            options.depth = int(next_arg)
            i += 1
        elif arg in ("-t", "--threads"):
            options.threads = int(next_arg)
            i += 1
        elif arg == "--timeout":
            options.timeout = int(next_arg)
            i += 1
        elif arg in ("--headless", "-hl"):
            options.headless = True
        elif arg in ("--secrets", "-s"):
            options.include_secrets = True
        elif arg in ("-o", "--output"):
            options.output_dir = next_arg
            i += 1
        elif arg == "--json":
            options.json_output = True
        elif arg == "--silent":
            options.silent = True
        elif arg in ("-h", "--help"):
            print("""
EndpointDiscovery - Extract endpoints from JavaScript at scale

Usage:
  python EndpointDiscovery.py <target> [options]

Modes:
  (default)               Crawl URL and extract endpoints from JS
  --local, -l             Parse local JS files from directory
  --stdin                 Read JS content from stdin
  --batch, -b             Process file as list of JS URLs

Options:
  --deep                  Use jsluice for deeper analysis
  -d, --depth <n>         Crawl depth (default: 3)
  -t, --threads <n>       Concurrent threads
  --timeout <seconds>     Request timeout (default: 30)
  --headless, -hl         Use headless browser for JS rendering
  -s, --secrets           Also extract potential secrets/API keys
  -o, --output <dir>      Save JS files for later analysis
  --json                  Output as JSON
  --silent                Minimal output
""")
            sys.exit(0)
        else:
            if not arg.startswith("-") and not target:
                target = arg
        i += 1

    return target, options


if __name__ == "__main__":
    args = sys.argv[1:]
    target, options = parse_args(args)

    if not target and not options.stdin:
        print("Error: Target required (URL, directory, or use --stdin)", file=sys.stderr)
        print("Usage: python EndpointDiscovery.py <target> [options]", file=sys.stderr)
        sys.exit(1)

    result = run_endpoint_discovery(target, options)

    if options.json_output:
        output = {
            "target": result.target,
            "timestamp": result.timestamp,
            "mode": result.mode,
            "jsFilesProcessed": result.js_files_processed,
            "endpoints": [
                {"path": e.path, "type": e.type, "source": e.source}
                for e in result.endpoints
            ],
            "secrets": [
                {"type": s.type, "value": s.value, "source": s.source}
                for s in result.secrets
            ],
            "stats": result.stats,
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nEndpoint Discovery: {result.target}")
        print(f"Timestamp: {result.timestamp}")
        print(f"Mode: {result.mode}")
        print(f"JS Files Processed: {result.js_files_processed}")
        print(f"\nStats:")
        print(f"   Total Endpoints: {result.stats['totalEndpoints']}")
        print(f"   Unique Paths: {result.stats['uniquePaths']}")

        for type_name, count in result.stats.get("byType", {}).items():
            print(f"   {type_name}: {count}")

        if result.endpoints:
            print(f"\nEndpoints by Type:\n")
            by_type: dict[str, list[Endpoint]] = {}
            for ep in result.endpoints:
                by_type.setdefault(ep.type, []).append(ep)

            for type_name, endpoints in by_type.items():
                print(f"  [{type_name.upper()}] ({len(endpoints)})")
                for ep in endpoints[:15]:
                    print(f"    {ep.path}")
                if len(endpoints) > 15:
                    print(f"    ... and {len(endpoints) - 15} more")
                print()

        if result.secrets:
            print(f"\nPotential Secrets ({len(result.secrets)}):\n")
            for secret in result.secrets[:10]:
                print(f"  [{secret.type}] {secret.value}")
            if len(result.secrets) > 10:
                print(f"  ... and {len(result.secrets) - 10} more")

        if result.errors:
            print("\nErrors:")
            for err in result.errors:
                print(f"  {err}")

        if result.endpoints:
            print(f'\nNext: Pipe to PathDiscovery for fuzzing')
            print(f'   python EndpointDiscovery.py "{target}" --json | jq -r \'.endpoints[].path\'')
