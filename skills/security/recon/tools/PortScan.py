#!/usr/bin/env python3
"""
PortScan - Port scanning for hosts and networks
Wraps naabu for fast and reliable port enumeration

Usage:
  python PortScan.py <target> [options]

Examples:
  python PortScan.py example.com
  python PortScan.py example.com -p 80,443,8080
  python PortScan.py 192.168.1.0/24 --top-ports 1000
  python PortScan.py targets.txt --json
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PortScanOptions:
    ports: Optional[str] = None
    top_ports: Optional[str] = None
    exclude_ports: Optional[str] = None
    rate: Optional[int] = None
    threads: Optional[int] = None
    timeout: Optional[int] = None
    scan_type: Optional[str] = None  # "syn" | "connect"
    json_output: bool = False
    silent: bool = False
    nmap: Optional[str] = None
    exclude_cdn: bool = False
    display_cdn: bool = False
    scan_all_ips: bool = False
    resolver: Optional[str] = None
    proxy: Optional[str] = None


@dataclass
class PortResult:
    host: str
    ip: str
    port: int
    protocol: str
    cdn: Optional[str] = None


@dataclass
class PortScanResult:
    target: str
    timestamp: str = ""
    scan_type: str = ""
    ports_scanned: str = ""
    total_hosts: int = 0
    total_ports: int = 0
    results: list[PortResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_port_scan(target: str, options: Optional[PortScanOptions] = None) -> PortScanResult:
    if options is None:
        options = PortScanOptions()

    result = PortScanResult(
        target=target,
        timestamp=datetime.now().isoformat(),
        scan_type=options.scan_type or "connect",
        ports_scanned=options.ports or options.top_ports or "top 100",
    )

    # Determine if target is a file
    is_file = Path(target).is_file()

    # Build naabu command
    args: list[str] = ["naabu"]

    if is_file:
        args.extend(["-list", target])
    else:
        args.extend(["-host", target])

    args.append("-json")

    if options.ports:
        args.extend(["-p", options.ports])
    elif options.top_ports:
        args.extend(["-top-ports", options.top_ports])

    if options.exclude_ports:
        args.extend(["-exclude-ports", options.exclude_ports])

    if options.rate:
        args.extend(["-rate", str(options.rate)])
    if options.threads:
        args.extend(["-c", str(options.threads)])

    if options.scan_type == "syn":
        args.extend(["-s", "s"])

    if options.exclude_cdn:
        args.append("-exclude-cdn")
    if options.display_cdn:
        args.append("-display-cdn")

    if options.scan_all_ips:
        args.append("-scan-all-ips")

    if options.resolver:
        args.extend(["-r", options.resolver])

    if options.proxy:
        args.extend(["-proxy", options.proxy])

    if options.nmap:
        args.extend(["-nmap-cli", options.nmap])

    if options.silent:
        args.append("-silent")

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=600)

        if proc.stderr:
            errors = [
                line for line in proc.stderr.split("\n")
                if "[ERR]" in line or "[FATAL]" in line
            ]
            result.errors.extend(errors)

        lines = [line for line in proc.stdout.strip().split("\n") if line]
        host_set: set[str] = set()

        for line in lines:
            try:
                data = json.loads(line)
                if data.get("host") and data.get("port"):
                    result.results.append(PortResult(
                        host=data["host"],
                        ip=data.get("ip", data["host"]),
                        port=data["port"],
                        protocol=data.get("protocol", "tcp"),
                        cdn=data.get("cdn"),
                    ))
                    host_set.add(data["host"])
            except json.JSONDecodeError:
                pass

        result.total_hosts = len(host_set)
        result.total_ports = len(result.results)

    except Exception as error:
        result.errors.append(f"naabu execution failed: {error}")

    return result


def parse_args(args: list[str]) -> tuple[str, PortScanOptions]:
    options = PortScanOptions()
    target = ""
    i = 0

    while i < len(args):
        arg = args[i]
        next_arg = args[i + 1] if i + 1 < len(args) else ""

        if arg in ("-p", "--ports"):
            options.ports = next_arg
            i += 1
        elif arg in ("-tp", "--top-ports"):
            options.top_ports = next_arg
            i += 1
        elif arg in ("-ep", "--exclude-ports"):
            options.exclude_ports = next_arg
            i += 1
        elif arg == "--rate":
            options.rate = int(next_arg)
            i += 1
        elif arg in ("-t", "--threads"):
            options.threads = int(next_arg)
            i += 1
        elif arg == "--timeout":
            options.timeout = int(next_arg)
            i += 1
        elif arg in ("-s", "--scan-type"):
            options.scan_type = next_arg
            i += 1
        elif arg == "--json":
            options.json_output = True
        elif arg == "--silent":
            options.silent = True
        elif arg == "--nmap":
            options.nmap = next_arg
            i += 1
        elif arg == "--exclude-cdn":
            options.exclude_cdn = True
        elif arg == "--display-cdn":
            options.display_cdn = True
        elif arg == "--scan-all-ips":
            options.scan_all_ips = True
        elif arg in ("-r", "--resolver"):
            options.resolver = next_arg
            i += 1
        elif arg == "--proxy":
            options.proxy = next_arg
            i += 1
        elif arg in ("-h", "--help"):
            print("""
PortScan - Fast port scanning

Usage:
  python PortScan.py <target> [options]

Arguments:
  target                  Host, IP, CIDR, or file containing targets

Options:
  -p, --ports <ports>     Ports to scan (80,443 or 1-1000)
  -tp, --top-ports <n>    Top ports: 100, 1000, or full
  -ep, --exclude-ports    Ports to exclude
  --rate <n>              Packets per second (default: 1000)
  -t, --threads <n>       Worker threads (default: 25)
  -s, --scan-type <type>  Scan type: syn or connect (syn requires root)
  --exclude-cdn           Skip CDN/WAF hosts
  --display-cdn           Show CDN provider in results
  --scan-all-ips          Scan all IPs for hostname
  -r, --resolver <dns>    Custom DNS resolver
  --proxy <url>           SOCKS5 proxy
  --nmap <cmd>            Run nmap command on results
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

    if not target:
        print("Error: Target required (host, IP, CIDR, or file)", file=sys.stderr)
        print("Usage: python PortScan.py <target> [options]", file=sys.stderr)
        sys.exit(1)

    result = run_port_scan(target, options)

    if options.json_output:
        output = {
            "target": result.target,
            "timestamp": result.timestamp,
            "scanType": result.scan_type,
            "portsScanned": result.ports_scanned,
            "totalHosts": result.total_hosts,
            "totalPorts": result.total_ports,
            "results": [
                {
                    "host": r.host,
                    "ip": r.ip,
                    "port": r.port,
                    "protocol": r.protocol,
                    "cdn": r.cdn,
                }
                for r in result.results
            ],
            "errors": result.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nPort Scan: {result.target}")
        print(f"Timestamp: {result.timestamp}")
        print(f"Scan Type: {result.scan_type}")
        print(f"Ports: {result.ports_scanned}")
        print(f"\nFound {result.total_ports} open ports on {result.total_hosts} hosts:\n")

        if not result.results:
            print("  No open ports found")
        else:
            by_host: dict[str, list[PortResult]] = {}
            for r in result.results:
                by_host.setdefault(r.host, []).append(r)

            for host, ports in by_host.items():
                port_list = ", ".join(str(p.port) for p in sorted(ports, key=lambda p: p.port))
                cdn = f" (CDN: {ports[0].cdn})" if ports[0].cdn else ""
                print(f"  {host}{cdn}")
                print(f"    Open: {port_list}")
                print()

        if result.errors:
            print("\nErrors:")
            for err in result.errors:
                print(f"  {err}")
