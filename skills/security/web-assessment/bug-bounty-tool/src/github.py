#!/usr/bin/env python3
"""GitHub API client for bug bounty tracking."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

import httpx

from .config import CONFIG
from .types import GitHubCommit, Program


class GitHubClient:
    def __init__(self) -> None:
        self.base_url = CONFIG["api"]["base"]
        self.repo_path = f"repos/{CONFIG['repo']['owner']}/{CONFIG['repo']['name']}"

    def get_commits_since(self, file_path: str, since: str) -> list[dict]:
        """TIER 1: Fast check - Get commits for a specific file."""
        url = f"{self.base_url}/{self.repo_path}/commits?path={file_path}&since={since}"

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url)
            if response.status_code != 200:
                raise RuntimeError(f"GitHub API error: {response.status_code}")
            return response.json()
        except Exception as error:
            print(f"Failed to fetch commits: {error}")
            return []

    def get_latest_commit(self, file_path: str) -> Optional[dict]:
        """Get the latest commit for a file."""
        url = f"{self.base_url}/{self.repo_path}/commits?path={file_path}&per_page=1"

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url)
            if response.status_code != 200:
                return None
            commits = response.json()
            return commits[0] if commits else None
        except Exception:
            return None

    def get_compare_diff(self, base_commit: str, head_commit: str) -> str:
        """TIER 2: Detailed analysis - Get the diff between two commits."""
        url = f"{self.base_url}/{self.repo_path}/compare/{base_commit}...{head_commit}"

        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url)
            if response.status_code != 200:
                raise RuntimeError(f"GitHub API error: {response.status_code}")
            data = response.json()
            return json.dumps(data, indent=2)
        except Exception as error:
            print(f"Failed to fetch diff: {error}")
            return ""

    def fetch_file(self, file_path: str, commit: Optional[str] = None) -> str:
        """Fetch a specific file from the repository."""
        branch = commit or "main"
        url = f"{CONFIG['api']['raw_base']}/{CONFIG['repo']['owner']}/{CONFIG['repo']['name']}/{branch}/{file_path}"

        try:
            with httpx.Client(timeout=60) as client:
                response = client.get(url)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to fetch file: {response.status_code}")
            return response.text
        except Exception as error:
            print(f"Failed to fetch file: {error}")
            return ""

    def parse_programs(self, json_data: str, platform: str) -> list[Program]:
        """Parse program data from JSON."""
        try:
            data = json.loads(json_data)
            if not isinstance(data, list):
                return []
            return [self._normalize_program(item, platform) for item in data]
        except Exception as error:
            print(f"Failed to parse programs: {error}")
            return []

    def _normalize_program(self, data: dict, platform: str) -> Program:
        """Normalize program data from different platforms."""
        return Program(
            name=data.get("name", "Unknown"),
            platform=platform,
            handle=data.get("handle", data.get("id", "unknown")),
            url=data.get("url", ""),
            website=data.get("website"),
            offers_bounties=data.get("offers_bounties", data.get("bounty", False)),
            offers_swag=data.get("offers_swag", data.get("swag", False)),
            submission_state=data.get("submission_state", "unknown"),
            key_scopes=self._extract_scopes(data),
            discovered_at=datetime.now().isoformat(),
            max_severity=self._extract_max_severity(data),
            managed_program=data.get("managed_program"),
        )

    def _extract_scopes(self, data: dict) -> list[str]:
        """Extract scope domains from program data."""
        if isinstance(data.get("domains"), list):
            return data["domains"]

        targets = data.get("targets", {})
        in_scope = targets.get("in_scope", [])
        if isinstance(in_scope, list):
            return [
                t.get("asset_identifier", "")
                for t in in_scope
                if t.get("asset_identifier")
            ][:10]

        return []

    def _extract_max_severity(self, data: dict) -> Optional[str]:
        """Extract maximum severity from program data."""
        targets = data.get("targets", {})
        in_scope = targets.get("in_scope", [])
        if isinstance(in_scope, list):
            severities = [
                t.get("max_severity", "")
                for t in in_scope
                if t.get("max_severity")
            ]
            for level in ("critical", "high", "medium", "low"):
                if level in severities:
                    return level
        return None
