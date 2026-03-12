#!/usr/bin/env python3
"""
DNS Utilities

DNS enumeration, lookups, and analysis using dig/system DNS.

Usage:
  from DnsUtils import get_all_records, enumerate_subdomains_via_cert
  records = get_all_records("example.com")
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


@dataclass
class DNSRecord:
    type: str
    value: str
    ttl: Optional[int] = None


@dataclass
class EmailSecurityInfo:
    spf_configured: bool = False
    spf_record: Optional[str] = None
    spf_mechanism: Optional[str] = None
    dmarc_configured: bool = False
    dmarc_record: Optional[str] = None
    dmarc_policy: Optional[str] = None
    dkim_configured: bool = False
    dkim_selectors: list[str] = field(default_factory=list)


def dig_query(domain: str, record_type: str = "A") -> list[str]:
    """Query DNS records using dig."""
    try:
        result = subprocess.run(
            ["dig", domain, record_type, "+short"],
            capture_output=True, text=True, timeout=30,
        )
        return [line for line in result.stdout.strip().split("\n") if line]
    except Exception as error:
        print(f"dig query failed for {domain} {record_type}: {error}", file=sys.stderr)
        return []


def get_a_records(domain: str) -> list[str]:
    """Get A records (IPv4)."""
    return dig_query(domain, "A")


def get_aaaa_records(domain: str) -> list[str]:
    """Get AAAA records (IPv6)."""
    return dig_query(domain, "AAAA")


def get_mx_records(domain: str) -> list[dict[str, Any]]:
    """Get MX records (mail servers)."""
    records = dig_query(domain, "MX")
    result = []
    for record in records:
        parts = record.split()
        if len(parts) >= 2:
            result.append({
                "priority": int(parts[0]),
                "hostname": parts[1].rstrip("."),
            })
    return sorted(result, key=lambda x: x["priority"])


def get_ns_records(domain: str) -> list[str]:
    """Get NS records (name servers)."""
    records = dig_query(domain, "NS")
    return [ns.rstrip(".") for ns in records]


def get_txt_records(domain: str) -> list[str]:
    """Get TXT records."""
    records = dig_query(domain, "TXT")
    return [txt.strip('"') for txt in records]


def get_cname(domain: str) -> Optional[str]:
    """Get CNAME record."""
    records = dig_query(domain, "CNAME")
    return records[0].rstrip(".") if records else None


def get_soa(domain: str) -> Optional[dict[str, Any]]:
    """Get SOA record."""
    records = dig_query(domain, "SOA")
    if not records:
        return None

    parts = records[0].split()
    if len(parts) < 7:
        return None

    return {
        "mname": parts[0],
        "rname": parts[1],
        "serial": int(parts[2]),
        "refresh": int(parts[3]),
        "retry": int(parts[4]),
        "expire": int(parts[5]),
        "minimum": int(parts[6]),
    }


def reverse_dns(ip: str) -> Optional[str]:
    """Reverse DNS lookup."""
    try:
        result = subprocess.run(
            ["dig", "-x", ip, "+short"],
            capture_output=True, text=True, timeout=30,
        )
        hostname = result.stdout.strip()
        return hostname.rstrip(".") if hostname else None
    except Exception:
        return None


def get_all_records(domain: str) -> dict[str, Any]:
    """Get all DNS records for a domain."""
    return {
        "A": get_a_records(domain),
        "AAAA": get_aaaa_records(domain),
        "MX": get_mx_records(domain),
        "NS": get_ns_records(domain),
        "TXT": get_txt_records(domain),
        "CNAME": get_cname(domain),
        "SOA": get_soa(domain),
    }


def analyze_email_security(domain: str) -> dict[str, Any]:
    """Analyze email security configuration."""
    import re

    # SPF
    txt_records = get_txt_records(domain)
    spf_record = next((txt for txt in txt_records if txt.startswith("v=spf1")), None)

    spf_info: dict[str, Any] = {"configured": bool(spf_record)}
    if spf_record:
        spf_info["record"] = spf_record
        mechanism_match = re.search(r"[~\-+?]all", spf_record)
        if mechanism_match:
            spf_info["mechanism"] = mechanism_match.group(0)

    # DMARC
    dmarc_records = get_txt_records(f"_dmarc.{domain}")
    dmarc_record = next((txt for txt in dmarc_records if txt.startswith("v=DMARC1")), None)

    dmarc_info: dict[str, Any] = {"configured": bool(dmarc_record)}
    if dmarc_record:
        dmarc_info["record"] = dmarc_record
        policy_match = re.search(r"p=(none|quarantine|reject)", dmarc_record)
        if policy_match:
            dmarc_info["policy"] = policy_match.group(1)

    # DKIM
    common_selectors = [
        "default", "google", "k1", "k2", "selector1", "selector2", "dkim", "mail",
    ]
    dkim_selectors: list[str] = []

    for selector in common_selectors:
        dkim_records = get_txt_records(f"{selector}._domainkey.{domain}")
        if dkim_records and any("v=DKIM1" in r for r in dkim_records):
            dkim_selectors.append(selector)

    return {
        "spf": spf_info,
        "dmarc": dmarc_info,
        "dkim": {
            "configured": len(dkim_selectors) > 0,
            "selectors": dkim_selectors,
        },
    }


def enumerate_subdomains_via_cert(domain: str) -> list[str]:
    """Enumerate subdomains via certificate transparency."""
    try:
        url = f"https://crt.sh/?q=%.{domain}&output=json"
        with httpx.Client(timeout=30) as client:
            response = client.get(url)

        if response.status_code != 200:
            raise RuntimeError(f"crt.sh query failed: {response.status_code}")

        data = response.json()
        subdomains: set[str] = set()

        for cert in data:
            names = cert.get("name_value", "").split("\n")
            for name in names:
                name = name.lstrip("*.")
                if name.endswith(domain) or name == domain:
                    subdomains.add(name.lower())

        return sorted(subdomains)
    except Exception as error:
        print(f"Certificate transparency query failed: {error}", file=sys.stderr)
        return []


def enumerate_common_subdomains(domain: str) -> list[str]:
    """Enumerate subdomains using common names."""
    common_prefixes = [
        "www", "mail", "ftp", "localhost", "webmail", "smtp", "pop",
        "ns1", "ns2", "webdisk", "ns", "cpanel", "whm", "autodiscover",
        "autoconfig", "m", "imap", "test", "mx", "blog", "dev", "www2",
        "admin", "forum", "news", "vpn", "ns3", "mail2", "new", "mysql",
        "old", "lists", "support", "mobile", "mx1", "static", "api",
        "cdn", "media", "email", "portal", "beta", "stage", "staging",
        "demo", "intranet", "git", "shop", "app", "apps",
    ]

    found: list[str] = []
    for prefix in common_prefixes:
        subdomain = f"{prefix}.{domain}"
        records = get_a_records(subdomain)
        if records:
            found.append(subdomain)

    return found


def attempt_zone_transfer(domain: str) -> dict[str, Any]:
    """Attempt zone transfer (usually fails but worth trying)."""
    try:
        name_servers = get_ns_records(domain)
        if not name_servers:
            return {"success": False, "error": "No name servers found"}

        ns = name_servers[0]
        result = subprocess.run(
            ["dig", f"@{ns}", domain, "AXFR"],
            capture_output=True, text=True, timeout=30,
        )

        output = result.stdout
        if "Transfer failed" in output or "refused" in output:
            return {"success": False, "error": "Zone transfer refused (expected)"}

        records = [
            line for line in output.split("\n")
            if domain in line and not line.startswith(";")
        ]

        return {"success": True, "records": records}
    except Exception as error:
        return {"success": False, "error": str(error)}


def validate_forward_reverse(domain: str) -> dict[str, Any]:
    """Validate forward-reverse DNS match."""
    forward_ips = get_a_records(domain)
    reverse_domains: dict[str, Optional[str]] = {}

    for ip in forward_ips:
        reverse = reverse_dns(ip)
        reverse_domains[ip] = reverse

    matched = any(reverse == domain for reverse in reverse_domains.values())

    return {
        "matched": matched,
        "forwardIPs": forward_ips,
        "reverseDomains": reverse_domains,
    }


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  DnsUtils.py <domain>              - Get all records")
        print("  DnsUtils.py <domain> email        - Email security analysis")
        print("  DnsUtils.py <domain> subdomains   - Enumerate subdomains")
        print("  DnsUtils.py <domain> reverse <ip> - Reverse DNS")
        sys.exit(1)

    domain = args[0]
    command = args[1] if len(args) > 1 else None

    if not command:
        records = get_all_records(domain)
        print(json.dumps(records, indent=2))
    elif command == "email":
        email_sec = analyze_email_security(domain)
        print(json.dumps(email_sec, indent=2))
    elif command == "subdomains":
        print("Searching certificate transparency...")
        cert_subs = enumerate_subdomains_via_cert(domain)
        print(f"Found {len(cert_subs)} subdomains via cert transparency:")
        for sub in cert_subs:
            print(f"  {sub}")
        print("\nChecking common subdomains...")
        common_subs = enumerate_common_subdomains(domain)
        print(f"Found {len(common_subs)} common subdomains:")
        for sub in common_subs:
            print(f"  {sub}")
    elif command == "reverse" and len(args) > 2:
        hostname = reverse_dns(args[2])
        print(hostname or "No PTR record found")
