#!/usr/bin/env python3
"""
CIDR Utilities

Parse and manipulate CIDR notation, calculate IP ranges, generate IPs.

Usage:
  from CidrUtils import parse_cidr, generate_ips_from_cidr
  cidr = parse_cidr("192.168.1.0/24")
  print(cidr["total_ips"])  # 256
  ips = generate_ips_from_cidr("192.168.1.0/28", 5)
"""

from __future__ import annotations

import json
import math
import random
import sys
from dataclasses import dataclass
from typing import Generator, Optional


@dataclass
class CIDRInfo:
    cidr: str
    network: str
    mask: int
    netmask: str
    first_ip: str
    last_ip: str
    broadcast: str
    total_ips: int
    usable_ips: int
    wildcard: str


def ip_to_int(ip: str) -> int:
    """Convert IP address to 32-bit integer."""
    parts = ip.split(".")
    if len(parts) != 4:
        raise ValueError(f"Invalid IP address: {ip}")

    result = 0
    for octet_str in parts:
        num = int(octet_str)
        if num < 0 or num > 255:
            raise ValueError(f"Invalid octet: {octet_str} in IP {ip}")
        result = (result << 8) + num
    return result & 0xFFFFFFFF


def int_to_ip(value: int) -> str:
    """Convert 32-bit integer to IP address."""
    return ".".join([
        str((value >> 24) & 0xFF),
        str((value >> 16) & 0xFF),
        str((value >> 8) & 0xFF),
        str(value & 0xFF),
    ])


def is_valid_ip(ip: str) -> bool:
    """Validate IP address format."""
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        try:
            num = int(part)
        except ValueError:
            return False
        if num < 0 or num > 255 or part != str(num):
            return False
    return True


def parse_cidr(cidr: str) -> CIDRInfo:
    """Parse CIDR notation into detailed information."""
    parts = cidr.split("/")
    if len(parts) != 2:
        raise ValueError(f"Invalid CIDR notation: {cidr}")

    network_str, mask_str = parts
    mask = int(mask_str)

    if mask < 0 or mask > 32:
        raise ValueError(f"Invalid mask: {mask}. Must be 0-32.")

    if not is_valid_ip(network_str):
        raise ValueError(f"Invalid IP address: {network_str}")

    # Calculate mask and wildcard
    mask_int = (0xFFFFFFFF << (32 - mask)) & 0xFFFFFFFF
    wildcard_int = ~mask_int & 0xFFFFFFFF

    # Calculate network address
    ip_int = ip_to_int(network_str)
    network_int = ip_int & mask_int

    # Calculate broadcast address
    broadcast_int = network_int | wildcard_int

    # Total and usable IPs
    total_ips = 2 ** (32 - mask)
    if mask == 32:
        usable_ips = 1
    elif mask == 31:
        usable_ips = 2
    else:
        usable_ips = total_ips - 2

    return CIDRInfo(
        cidr=cidr,
        network=int_to_ip(network_int),
        mask=mask,
        netmask=int_to_ip(mask_int),
        first_ip=int_to_ip(network_int) if mask == 32 else int_to_ip(network_int + 1),
        last_ip=int_to_ip(network_int) if mask == 32 else int_to_ip(broadcast_int - 1),
        broadcast=int_to_ip(broadcast_int),
        total_ips=total_ips,
        usable_ips=usable_ips,
        wildcard=int_to_ip(wildcard_int),
    )


def is_ip_in_range(ip: str, cidr: str) -> bool:
    """Check if IP is in CIDR range."""
    cidr_info = parse_cidr(cidr)
    ip_int = ip_to_int(ip)
    first_int = ip_to_int(cidr_info.network)
    last_int = ip_to_int(cidr_info.broadcast)
    return first_int <= ip_int <= last_int


def generate_all_ips(cidr: str) -> Generator[str, None, None]:
    """Generate all IPs in CIDR range (use carefully for large ranges!)."""
    info = parse_cidr(cidr)
    if info.total_ips > 65536:
        raise ValueError(
            f"CIDR range too large ({info.total_ips} IPs). Use generate_ips_from_cidr with limit."
        )

    start_int = ip_to_int(info.network)
    end_int = ip_to_int(info.broadcast)

    for i in range(start_int, end_int + 1):
        yield int_to_ip(i)


def generate_ips_from_cidr(
    cidr: str,
    count: int,
    strategy: str = "distributed",
) -> list[str]:
    """Generate sample IPs from CIDR range."""
    info = parse_cidr(cidr)
    ips: list[str] = []

    first_int = ip_to_int(info.network)
    last_int = ip_to_int(info.broadcast)
    total_ips = last_int - first_int + 1

    if count > total_ips:
        count = total_ips

    if strategy == "first":
        for i in range(count):
            ips.append(int_to_ip(first_int + i))
    elif strategy == "last":
        for i in range(count):
            ips.append(int_to_ip(last_int - i))
    elif strategy == "random":
        selected: set[int] = set()
        while len(selected) < count:
            random_offset = random.randint(0, total_ips - 1)
            selected.add(first_int + random_offset)
        ips.extend(int_to_ip(v) for v in selected)
    elif strategy == "distributed":
        step = total_ips / count
        for i in range(count):
            offset = int(i * step)
            ips.append(int_to_ip(first_int + offset))

    return ips


def get_sample_recon_ips(cidr: str) -> list[str]:
    """Get sample IPs for reconnaissance (common gateway/server IPs)."""
    info = parse_cidr(cidr)
    samples: list[str] = []

    base = ".".join(info.network.split(".")[:3])

    common_offsets = [1, 2, 10, 50, 100, 254]

    for offset in common_offsets:
        ip = f"{base}.{offset}"
        if is_ip_in_range(ip, cidr):
            samples.append(ip)

    samples.append(info.first_ip)
    samples.append(info.last_ip)

    first_int = ip_to_int(info.first_ip)
    last_int = ip_to_int(info.last_ip)
    mid_int = (first_int + last_int) // 2
    samples.append(int_to_ip(mid_int))

    # Remove duplicates preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in samples:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def find_common_netblock(ips: list[str]) -> Optional[str]:
    """Find common netblock for multiple IPs."""
    if not ips:
        return None
    if len(ips) == 1:
        return f"{ips[0]}/32"

    ip_ints = [ip_to_int(ip) for ip in ips]

    for mask in range(32, -1, -1):
        mask_int = (0xFFFFFFFF << (32 - mask)) & 0xFFFFFFFF
        networks = {(ip & mask_int) & 0xFFFFFFFF for ip in ip_ints}
        if len(networks) == 1:
            network_int = networks.pop()
            return f"{int_to_ip(network_int)}/{mask}"

    return None


def split_cidr(cidr: str, new_mask: int) -> list[str]:
    """Split CIDR into smaller subnets."""
    info = parse_cidr(cidr)

    if new_mask <= info.mask:
        raise ValueError(
            f"New mask ({new_mask}) must be larger than current mask ({info.mask})"
        )

    subnet_count = 2 ** (new_mask - info.mask)
    first_int = ip_to_int(info.network)
    subnet_size = 2 ** (32 - new_mask)

    subnets: list[str] = []
    for i in range(subnet_count):
        subnet_int = first_int + i * subnet_size
        subnets.append(f"{int_to_ip(subnet_int)}/{new_mask}")

    return subnets


def aggregate_cidrs(cidrs: list[str]) -> list[str]:
    """Summarize multiple CIDRs into larger blocks (aggregate)."""
    sorted_infos = sorted(
        [parse_cidr(c) for c in cidrs],
        key=lambda x: ip_to_int(x.network),
    )

    aggregated: list[CIDRInfo] = []

    for current in sorted_infos:
        if not aggregated:
            aggregated.append(current)
            continue

        last = aggregated[-1]
        last_end = ip_to_int(last.broadcast)
        current_start = ip_to_int(current.network)

        if current_start == last_end + 1 and last.mask == current.mask:
            combined = f"{last.network}/{last.mask - 1}"
            try:
                combined_info = parse_cidr(combined)
                aggregated[-1] = combined_info
            except ValueError:
                aggregated.append(current)
        else:
            aggregated.append(current)

    return [info.cidr for info in aggregated]


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  CidrUtils.py <cidr>                  - Parse CIDR")
        print("  CidrUtils.py <cidr> sample <count>   - Generate sample IPs")
        print("  CidrUtils.py <cidr> split <mask>     - Split into subnets")
        sys.exit(1)

    cidr_arg = args[0]
    command = args[1] if len(args) > 1 else None

    if not command:
        info = parse_cidr(cidr_arg)
        output = {
            "cidr": info.cidr,
            "network": info.network,
            "mask": info.mask,
            "netmask": info.netmask,
            "firstIP": info.first_ip,
            "lastIP": info.last_ip,
            "broadcast": info.broadcast,
            "totalIPs": info.total_ips,
            "usableIPs": info.usable_ips,
            "wildcard": info.wildcard,
        }
        print(json.dumps(output, indent=2))
    elif command == "sample":
        count = int(args[2]) if len(args) > 2 else 10
        ips = generate_ips_from_cidr(cidr_arg, count)
        for ip in ips:
            print(ip)
    elif command == "split":
        new_mask = int(args[2])
        subnets = split_cidr(cidr_arg, new_mask)
        for subnet in subnets:
            print(subnet)
    elif command == "recon":
        samples = get_sample_recon_ips(cidr_arg)
        for ip in samples:
            print(ip)
