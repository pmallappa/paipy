#!/usr/bin/env python3
"""
MassScan - Large-scale network port scanning
Wraps masscan for scanning large IP ranges at high speed

REQUIRES ROOT/SUDO for raw packet operations

Usage:
  sudo python MassScan.py <target> [options]

Examples:
  sudo python MassScan.py 10.0.0.0/8 -p 80,443
  sudo python MassScan.py 192.168.0.0/16 --rate 10000
  sudo python MassScan.py targets.txt -p 22,80,443,3389 --json
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
class MassScanOptions:
    ports: Optional[str] = None
    rate: Optional[int] = None
    banners: bool = False
    exclude_file: Optional[str] = None
    include_file: Optional[str] = None
    adapter: Optional[str] = None
    adapter_ip: Optional[str] = None
    adapter_mac: Optional[str] = None
    router_mac: Optional[str] = None
    output_file: Optional[str] = None
    json_output: bool = False
    wait: Optional[int] = None
    retries: Optional[int] = None
    exclude_ports: Optional[str] = None


@dataclass
class MassScanResult:
    ip: str
    port: int
    protocol: str
    state: str
    reason: Optional[str] = None
    ttl: Optional[int] = None
    banner: Optional[str] = None
    timestamp: Optional[str] = None


@dataclass
class MassScanReport:
    target: str
    timestamp: str = ""
    rate: int = 1000
    ports_scanned: str = "80"
    total_hosts: int = 0
    total_ports: int = 0
    results: list[MassScanResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_mass_scan(target: str, options: Optional[MassScanOptions] = None) -> MassScanReport:
    if options is None:
        options = MassScanOptions()

    report = MassScanReport(
        target=target,
        timestamp=datetime.now().isoformat(),
        rate=options.rate or 1000,
        ports_scanned=options.ports or "80",
    )

    # Check if running as root
    if os.getuid() != 0:
        report.errors.append("masscan requires root privileges. Run with sudo.")
        return report

    # Build masscan command
    args: list[str] = ["masscan"]

    is_file = Path(target).is_file()
    if is_file:
        args.extend(["-iL", target])
    else:
        args.append(target)

    args.extend(["-p", options.ports or "80"])
    args.extend(["--rate", str(options.rate or 1000)])
    args.extend(["-oJ", "-"])

    if options.banners:
        args.append("--banners")

    if options.exclude_file:
        args.extend(["--excludefile", options.exclude_file])

    if options.adapter:
        args.extend(["--adapter", options.adapter])
    if options.adapter_ip:
        args.extend(["--adapter-ip", options.adapter_ip])
    if options.adapter_mac:
        args.extend(["--adapter-mac", options.adapter_mac])
    if options.router_mac:
        args.extend(["--router-mac", options.router_mac])

    if options.wait is not None:
        args.extend(["--wait", str(options.wait)])

    if options.retries:
        args.extend(["--retries", str(options.retries)])

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=3600)

        if proc.stderr:
            errors = [
                line for line in proc.stderr.split("\n")
                if any(kw in line.lower() for kw in ("error", "fatal", "failed"))
            ]
            report.errors.extend(errors)

        # Parse JSON output
        try:
            data = json.loads(proc.stdout)
            if isinstance(data, list):
                host_set: set[str] = set()
                for entry in data:
                    if entry.get("finished"):
                        continue
                    if entry.get("ip") and entry.get("ports"):
                        for port in entry["ports"]:
                            report.results.append(MassScanResult(
                                ip=entry["ip"],
                                port=port.get("port", 0),
                                protocol=port.get("proto", "tcp"),
                                state=port.get("status", "open"),
                                reason=port.get("reason"),
                                ttl=port.get("ttl"),
                                banner=port.get("service", {}).get("banner") if isinstance(port.get("service"), dict) else None,
                                timestamp=entry.get("timestamp"),
                            ))
                            host_set.add(entry["ip"])
                report.total_hosts = len(host_set)
                report.total_ports = len(report.results)
        except json.JSONDecodeError:
            # Try line-by-line
            lines = [line for line in proc.stdout.strip().split("\n") if line]
            host_set = set()
            for line in lines:
                try:
                    entry = json.loads(line)
                    if entry.get("ip") and entry.get("ports"):
                        for port in entry["ports"]:
                            report.results.append(MassScanResult(
                                ip=entry["ip"],
                                port=port.get("port", 0),
                                protocol=port.get("proto", "tcp"),
                                state=port.get("status", "open"),
                            ))
                            host_set.add(entry["ip"])
                except json.JSONDecodeError:
                    pass
            report.total_hosts = len(host_set)
            report.total_ports = len(report.results)

    except Exception as error:
        report.errors.append(f"masscan execution failed: {error}")

    return report


def parse_args(args: list[str]) -> tuple[str, MassScanOptions]:
    options = MassScanOptions()
    target = ""
    i = 0

    while i < len(args):
        arg = args[i]
        next_arg = args[i + 1] if i + 1 < len(args) else ""

        if arg in ("-p", "--ports"):
            options.ports = next_arg
            i += 1
        elif arg == "--rate":
            options.rate = int(next_arg)
            i += 1
        elif arg == "--banners":
            options.banners = True
        elif arg == "--excludefile":
            options.exclude_file = next_arg
            i += 1
        elif arg in ("-iL", "--include-file"):
            options.include_file = next_arg
            i += 1
        elif arg == "--adapter":
            options.adapter = next_arg
            i += 1
        elif arg == "--adapter-ip":
            options.adapter_ip = next_arg
            i += 1
        elif arg == "--adapter-mac":
            options.adapter_mac = next_arg
            i += 1
        elif arg == "--router-mac":
            options.router_mac = next_arg
            i += 1
        elif arg in ("-o", "--output"):
            options.output_file = next_arg
            i += 1
        elif arg == "--json":
            options.json_output = True
        elif arg == "--wait":
            options.wait = int(next_arg)
            i += 1
        elif arg == "--retries":
            options.retries = int(next_arg)
            i += 1
        elif arg in ("-h", "--help"):
            print("""
MassScan - Large-scale network port scanning

REQUIRES ROOT/SUDO for raw packet operations

Usage:
  sudo python MassScan.py <target> [options]

Arguments:
  target                  CIDR range, IP, or file containing targets

Options:
  -p, --ports <ports>     Ports to scan (80,443 or 0-65535)
  --rate <n>              Packets per second (default: 1000)
  --banners               Grab service banners
  --excludefile <file>    File with IPs/ranges to exclude
  --adapter <name>        Network interface to use
  --adapter-ip <ip>       Source IP address
  --adapter-mac <mac>     Source MAC address
  --router-mac <mac>      Gateway MAC address
  --wait <seconds>        Wait time for responses after scan
  --retries <n>           Number of retries per port
  -o, --output <file>     Save results to file
  --json                  Output as JSON

Rate Guidelines:
  - Home network: 1000-10000 pps
  - Corporate: 10000-100000 pps
  - Data center: 100000+ pps
  - Internet-wide: 1000000+ pps (be careful!)
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

    if not target and not options.include_file:
        print("Error: Target required (CIDR, IP, or file)", file=sys.stderr)
        print("Usage: sudo python MassScan.py <target> [options]", file=sys.stderr)
        sys.exit(1)

    report = run_mass_scan(target or options.include_file or "", options)

    if options.json_output:
        output = {
            "target": report.target,
            "timestamp": report.timestamp,
            "rate": report.rate,
            "portsScanned": report.ports_scanned,
            "totalHosts": report.total_hosts,
            "totalPorts": report.total_ports,
            "results": [
                {
                    "ip": r.ip,
                    "port": r.port,
                    "protocol": r.protocol,
                    "state": r.state,
                    "reason": r.reason,
                    "ttl": r.ttl,
                    "banner": r.banner,
                    "timestamp": r.timestamp,
                }
                for r in report.results
            ],
            "errors": report.errors,
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\nMassScan: {report.target}")
        print(f"Timestamp: {report.timestamp}")
        print(f"Rate: {report.rate} packets/second")
        print(f"Ports: {report.ports_scanned}")

        if report.errors and any("root" in e for e in report.errors):
            print("\nRun with sudo for raw packet scanning")
        else:
            print(f"\nFound {report.total_ports} open ports on {report.total_hosts} hosts:\n")

            if not report.results:
                print("  No open ports found")
            else:
                by_ip: dict[str, list[MassScanResult]] = {}
                for r in report.results:
                    by_ip.setdefault(r.ip, []).append(r)

                def ip_sort_key(ip: str) -> tuple:
                    return tuple(int(p) for p in ip.split("."))

                sorted_ips = sorted(by_ip.keys(), key=ip_sort_key)

                for ip in sorted_ips[:50]:
                    ports = by_ip[ip]
                    port_list = ", ".join(str(p.port) for p in sorted(ports, key=lambda p: p.port))
                    print(f"  {ip}")
                    print(f"    Open: {port_list}")
                    banner_ports = [p for p in ports if p.banner]
                    if banner_ports:
                        for p in banner_ports:
                            print(f"    {p.port}: {p.banner}")
                    print()

                if len(sorted_ips) > 50:
                    print(f"  ... and {len(sorted_ips) - 50} more hosts")

        if report.errors:
            print("\nErrors:")
            for err in report.errors:
                print(f"  {err}")

    if options.output_file:
        output_data = {
            "target": report.target,
            "timestamp": report.timestamp,
            "results": [
                {"ip": r.ip, "port": r.port, "protocol": r.protocol, "state": r.state}
                for r in report.results
            ],
        }
        Path(options.output_file).write_text(json.dumps(output_data, indent=2))
        print(f"\nResults saved to: {options.output_file}")
