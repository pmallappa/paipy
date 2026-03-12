#!/usr/bin/env python3
"""
WHOIS Parser

Execute and parse WHOIS lookups for domains and IP addresses.

Usage:
  from WhoisParser import whois_domain, whois_ip
  domain_info = whois_domain("example.com")
  ip_info = whois_ip("1.2.3.4")
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class DomainWhoisInfo:
    domain: str
    raw: str
    registrar: Optional[str] = None
    registrar_url: Optional[str] = None
    creation_date: Optional[str] = None
    expiration_date: Optional[str] = None
    updated_date: Optional[str] = None
    status: list[str] = field(default_factory=list)
    name_servers: list[str] = field(default_factory=list)
    registrant: Optional[dict[str, Optional[str]]] = None
    admin: Optional[dict[str, Optional[str]]] = None
    tech: Optional[dict[str, Optional[str]]] = None
    dnssec: Optional[bool] = None


@dataclass
class IPWhoisInfo:
    ip: str
    raw: str
    net_range: Optional[str] = None
    cidr: Optional[str] = None
    net_name: Optional[str] = None
    organization: Optional[str] = None
    country: Optional[str] = None
    registration_date: Optional[str] = None
    updated_date: Optional[str] = None
    abuse_email: Optional[str] = None
    abuse_phone: Optional[str] = None
    tech_email: Optional[str] = None
    rir: Optional[str] = None  # Regional Internet Registry


def execute_whois(query: str) -> str:
    """Execute WHOIS query."""
    try:
        result = subprocess.run(
            ["whois", query], capture_output=True, text=True, timeout=30,
        )
        return result.stdout
    except Exception as error:
        raise RuntimeError(f"WHOIS query failed: {error}") from error


def parse_whois_date(date_str: str) -> Optional[str]:
    """Parse WHOIS date format (returns ISO string)."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.isoformat()
    except ValueError:
        pass
    # Try standard parsing
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.isoformat()
        except ValueError:
            continue
    return date_str  # Return as-is if parsing fails


def whois_domain(domain: str) -> DomainWhoisInfo:
    """Parse domain WHOIS data."""
    raw = execute_whois(domain)
    info = DomainWhoisInfo(domain=domain, raw=raw)

    # Parse registrar
    match = re.search(r"Registrar:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.registrar = match.group(1).strip()

    # Parse registrar URL
    match = re.search(r"Registrar URL:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.registrar_url = match.group(1).strip()

    # Parse dates
    match = re.search(r"Creation Date:\s*(.+)|Registered on:\s*(.+)", raw, re.IGNORECASE)
    if match:
        date_str = (match.group(1) or match.group(2)).strip()
        info.creation_date = parse_whois_date(date_str)

    match = re.search(r"Expir(?:ation|y) Date:\s*(.+)|Expiry date:\s*(.+)", raw, re.IGNORECASE)
    if match:
        date_str = (match.group(1) or match.group(2)).strip()
        info.expiration_date = parse_whois_date(date_str)

    match = re.search(r"Updated Date:\s*(.+)|Last updated:\s*(.+)", raw, re.IGNORECASE)
    if match:
        date_str = (match.group(1) or match.group(2)).strip()
        info.updated_date = parse_whois_date(date_str)

    # Parse status
    info.status = [
        m.group(1).strip().split()[0]
        for m in re.finditer(r"Domain Status:\s*(.+)", raw, re.IGNORECASE)
    ]

    # Parse name servers
    info.name_servers = [
        m.group(1).strip().lower()
        for m in re.finditer(r"Name Server:\s*(.+)", raw, re.IGNORECASE)
    ]

    # Parse registrant
    registrant_org = re.search(r"Registrant Organization:\s*(.+)", raw, re.IGNORECASE)
    registrant_email = re.search(r"Registrant Email:\s*(.+)", raw, re.IGNORECASE)
    registrant_country = re.search(r"Registrant Country:\s*(.+)", raw, re.IGNORECASE)

    if registrant_org or registrant_email or registrant_country:
        info.registrant = {
            "organization": registrant_org.group(1).strip() if registrant_org else None,
            "email": registrant_email.group(1).strip() if registrant_email else None,
            "country": registrant_country.group(1).strip() if registrant_country else None,
        }

    # Parse admin contact
    admin_org = re.search(r"Admin Organization:\s*(.+)", raw, re.IGNORECASE)
    admin_email = re.search(r"Admin Email:\s*(.+)", raw, re.IGNORECASE)

    if admin_org or admin_email:
        info.admin = {
            "organization": admin_org.group(1).strip() if admin_org else None,
            "email": admin_email.group(1).strip() if admin_email else None,
        }

    # Parse tech contact
    tech_org = re.search(r"Tech Organization:\s*(.+)", raw, re.IGNORECASE)
    tech_email = re.search(r"Tech Email:\s*(.+)", raw, re.IGNORECASE)

    if tech_org or tech_email:
        info.tech = {
            "organization": tech_org.group(1).strip() if tech_org else None,
            "email": tech_email.group(1).strip() if tech_email else None,
        }

    # Parse DNSSEC
    dnssec_match = re.search(r"DNSSEC:\s*(.+)", raw, re.IGNORECASE)
    if dnssec_match:
        info.dnssec = dnssec_match.group(1).strip().lower() != "unsigned"

    return info


def whois_ip(ip: str) -> IPWhoisInfo:
    """Parse IP/netblock WHOIS data."""
    raw = execute_whois(ip)
    info = IPWhoisInfo(ip=ip, raw=raw)

    # Detect RIR
    rir_map = {
        "whois.arin.net": "ARIN",
        "whois.ripe.net": "RIPE",
        "whois.apnic.net": "APNIC",
        "whois.lacnic.net": "LACNIC",
        "whois.afrinic.net": "AFRINIC",
    }
    for key, value in rir_map.items():
        if key in raw:
            info.rir = value
            break

    # Parse fields
    match = re.search(r"NetRange:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.net_range = match.group(1).strip()

    match = re.search(r"CIDR:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.cidr = match.group(1).strip()

    match = re.search(r"NetName:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.net_name = match.group(1).strip()

    match = (
        re.search(r"Organization:\s*(.+)", raw, re.IGNORECASE)
        or re.search(r"OrgName:\s*(.+)", raw, re.IGNORECASE)
        or re.search(r"org-name:\s*(.+)", raw, re.IGNORECASE)
    )
    if match:
        info.organization = match.group(1).strip()

    match = re.search(r"Country:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.country = match.group(1).strip()

    match = re.search(r"RegDate:\s*(.+)|created:\s*(.+)", raw, re.IGNORECASE)
    if match:
        date_str = (match.group(1) or match.group(2)).strip()
        info.registration_date = parse_whois_date(date_str)

    match = re.search(r"Updated:\s*(.+)|last-modified:\s*(.+)", raw, re.IGNORECASE)
    if match:
        date_str = (match.group(1) or match.group(2)).strip()
        info.updated_date = parse_whois_date(date_str)

    match = re.search(r"OrgAbuseEmail:\s*(.+)|abuse-c:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.abuse_email = (match.group(1) or "").strip() or None

    match = re.search(r"OrgAbusePhone:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.abuse_phone = match.group(1).strip()

    match = re.search(r"OrgTechEmail:\s*(.+)", raw, re.IGNORECASE)
    if match:
        info.tech_email = match.group(1).strip()

    return info


def days_until_expiration(whois_info: DomainWhoisInfo) -> Optional[int]:
    """Calculate days until domain expiration."""
    if not whois_info.expiration_date:
        return None
    try:
        expiry = datetime.fromisoformat(whois_info.expiration_date)
        now = datetime.now()
        return (expiry - now).days
    except ValueError:
        return None


def is_domain_expiring_soon(whois_info: DomainWhoisInfo, days_threshold: int = 30) -> bool:
    """Check if domain is about to expire (< 30 days)."""
    days = days_until_expiration(whois_info)
    return days is not None and 0 < days < days_threshold


def extract_emails(whois_info: DomainWhoisInfo | IPWhoisInfo) -> list[str]:
    """Extract all email addresses from WHOIS data."""
    emails: set[str] = set()

    if isinstance(whois_info, DomainWhoisInfo):
        if whois_info.registrant and whois_info.registrant.get("email"):
            emails.add(whois_info.registrant["email"])
        if whois_info.admin and whois_info.admin.get("email"):
            emails.add(whois_info.admin["email"])
        if whois_info.tech and whois_info.tech.get("email"):
            emails.add(whois_info.tech["email"])

    if isinstance(whois_info, IPWhoisInfo):
        if whois_info.abuse_email:
            emails.add(whois_info.abuse_email)
        if whois_info.tech_email:
            emails.add(whois_info.tech_email)

    # Extract from raw text
    email_regex = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    for match in email_regex.finditer(whois_info.raw):
        emails.add(match.group(0).lower())

    # Filter privacy/placeholder emails
    filtered = [
        e for e in emails
        if "privacy" not in e
        and "redacted" not in e
        and "please-contact-" not in e
    ]

    return filtered


def has_privacy_protection(whois_info: DomainWhoisInfo) -> bool:
    """Check if domain uses privacy protection."""
    raw_lower = whois_info.raw.lower()
    privacy_keywords = [
        "privacy", "redacted", "not disclosed", "data protected",
        "whoisguard", "protected",
    ]
    return any(kw in raw_lower for kw in privacy_keywords)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage:")
        print("  WhoisParser.py <domain>  - Domain WHOIS")
        print("  WhoisParser.py <ip>      - IP WHOIS")
        sys.exit(1)

    query = args[0]

    # Detect if IP or domain
    is_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", query))

    if is_ip:
        info = whois_ip(query)
        output = {
            "ip": info.ip,
            "netRange": info.net_range,
            "cidr": info.cidr,
            "netName": info.net_name,
            "organization": info.organization,
            "country": info.country,
            "rir": info.rir,
            "registrationDate": info.registration_date,
            "updatedDate": info.updated_date,
            "abuseEmail": info.abuse_email,
            "abusePhone": info.abuse_phone,
            "techEmail": info.tech_email,
        }
        print(json.dumps(output, indent=2))
    else:
        info_d = whois_domain(query)
        print("\n=== Domain WHOIS Information ===\n")
        print(f"Domain: {info_d.domain}")
        print(f"Registrar: {info_d.registrar or 'Unknown'}")
        print(f"Creation Date: {info_d.creation_date or 'Unknown'}")
        print(f"Expiration Date: {info_d.expiration_date or 'Unknown'}")

        days_left = days_until_expiration(info_d)
        if days_left is not None:
            expiring = " EXPIRING SOON" if days_left < 30 else ""
            print(f"Days Until Expiration: {days_left}{expiring}")

        print(f"Status: {', '.join(info_d.status) if info_d.status else 'Unknown'}")
        print(f"Name Servers: {', '.join(info_d.name_servers) if info_d.name_servers else 'Unknown'}")
        print(f"DNSSEC: {'Enabled' if info_d.dnssec else 'Disabled'}")

        if has_privacy_protection(info_d):
            print("Privacy Protection: Enabled")

        emails = extract_emails(info_d)
        if emails:
            print("\nContact Emails:")
            for email in emails:
                print(f"  - {email}")
