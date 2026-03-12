#!/usr/bin/env python3
"""
IPInfo API Client

Wrapper for ipinfo.io API with error handling, rate limiting, and caching.
Requires IPINFO_API_KEY environment variable.

Usage:
  client = IPInfoClient()
  info = client.lookup("1.2.3.4")
  print(info.get("company"), info.get("loc"))
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


@dataclass
class IPInfoClient:
    api_key: str = ""
    base_url: str = "https://ipinfo.io"
    _cache: dict[str, dict] = field(default_factory=dict, repr=False)
    _last_request_time: float = field(default=0.0, repr=False)
    _min_request_interval: float = 0.1  # 100ms between requests

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("IPINFO_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "IPInfo API key not found. Set IPINFO_API_KEY environment variable."
            )

    def _rate_limit(self) -> None:
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def lookup(self, ip: str) -> dict:
        """Lookup single IP address."""
        if ip in self._cache:
            return self._cache[ip]

        self._rate_limit()
        url = f"{self.base_url}/{ip}/json?token={self.api_key}"

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url)

            if response.status_code == 429:
                raise RuntimeError("IPInfo API rate limit exceeded")
            if response.status_code == 401:
                raise RuntimeError("Invalid IPInfo API key")
            if response.status_code != 200:
                raise RuntimeError(f"IPInfo API error: {response.status_code}")

            data = response.json()
            self._cache[ip] = data
            return data
        except httpx.HTTPError as e:
            raise RuntimeError(f"IPInfo lookup failed for {ip}: {e}") from e

    def batch_lookup(self, ips: list[str]) -> dict[str, dict]:
        """Batch lookup multiple IPs (more efficient)."""
        if not ips:
            return {}

        uncached_ips = [ip for ip in ips if ip not in self._cache]

        if not uncached_ips:
            return {ip: self._cache[ip] for ip in ips}

        self._rate_limit()
        url = f"{self.base_url}/batch?token={self.api_key}"

        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    content=json.dumps(uncached_ips),
                )

            if response.status_code != 200:
                raise RuntimeError(f"IPInfo batch API error: {response.status_code}")

            data = response.json()
            for ip, info in data.items():
                self._cache[ip] = info

            result: dict[str, dict] = {}
            for ip in ips:
                if ip in self._cache:
                    result[ip] = self._cache[ip]
            return result
        except httpx.HTTPError as e:
            raise RuntimeError(f"IPInfo batch lookup failed: {e}") from e

    def get_location(self, ip: str) -> Optional[dict]:
        """Get geolocation info."""
        info = self.lookup(ip)

        if not all(info.get(k) for k in ("city", "region", "country", "loc")):
            return None

        lat, lon = info["loc"].split(",")
        return {
            "city": info["city"],
            "region": info["region"],
            "country": info["country"],
            "latitude": float(lat),
            "longitude": float(lon),
        }

    def get_asn(self, ip: str) -> Optional[dict]:
        """Get ASN info."""
        info = self.lookup(ip)
        asn = info.get("asn")
        if not asn:
            return None
        return {
            "asn": asn["asn"],
            "name": asn["name"],
            "route": asn["route"],
            "type": asn["type"],
        }

    def get_organization(self, ip: str) -> Optional[dict]:
        """Get organization info."""
        info = self.lookup(ip)
        company = info.get("company")
        if not company:
            return None
        return {
            "name": company["name"],
            "domain": company["domain"],
            "type": company["type"],
        }

    def is_proxy(self, ip: str) -> dict:
        """Check if IP is VPN/Proxy/Tor."""
        info = self.lookup(ip)
        privacy = info.get("privacy")

        if not privacy:
            return {
                "is_proxy": False,
                "vpn": False,
                "proxy": False,
                "tor": False,
                "relay": False,
                "hosting": False,
            }

        return {
            "is_proxy": (
                privacy.get("vpn", False)
                or privacy.get("proxy", False)
                or privacy.get("tor", False)
                or privacy.get("relay", False)
            ),
            "vpn": privacy.get("vpn", False),
            "proxy": privacy.get("proxy", False),
            "tor": privacy.get("tor", False),
            "relay": privacy.get("relay", False),
            "hosting": privacy.get("hosting", False),
        }

    def get_abuse_contact(self, ip: str) -> Optional[dict]:
        """Get abuse contact."""
        info = self.lookup(ip)
        abuse = info.get("abuse")
        if not abuse:
            return None
        return {
            "email": abuse["email"],
            "phone": abuse["phone"],
            "name": abuse["name"],
            "network": abuse["network"],
        }

    def clear_cache(self) -> None:
        """Clear cache."""
        self._cache.clear()

    def get_cache_size(self) -> int:
        """Get cache size."""
        return len(self._cache)


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print("Usage: IpinfoClient.py <ip> [ip2 ip3 ...]")
        print("       IPINFO_API_KEY=xxx python IpinfoClient.py 1.2.3.4")
        sys.exit(1)

    client = IPInfoClient()

    if len(args) == 1:
        info = client.lookup(args[0])
        print(json.dumps(info, indent=2))
    else:
        results = client.batch_lookup(args)
        print(json.dumps(results, indent=2))
