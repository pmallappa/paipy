#!/usr/bin/env python3
"""Type definitions for bug bounty tracking system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class ProgramScope:
    asset_identifier: str
    asset_type: str
    eligible_for_bounty: bool
    eligible_for_submission: bool
    max_severity: str


@dataclass
class Program:
    name: str
    platform: str  # 'hackerone' | 'bugcrowd' | 'intigriti' | 'yeswehack' | 'federacy'
    handle: str
    url: str
    offers_bounties: bool
    offers_swag: bool
    submission_state: str
    key_scopes: list[str] = field(default_factory=list)
    discovered_at: str = ""
    website: Optional[str] = None
    max_severity: Optional[str] = None
    managed_program: Optional[bool] = None


@dataclass
class ProgramMetadata:
    name: str
    platform: str
    handle: str
    url: str
    offers_bounties: bool
    key_scopes: list[str] = field(default_factory=list)
    discovered_at: str = ""
    max_severity: Optional[str] = None
    change_type: Optional[str] = None  # 'new_program' | 'scope_expansion' | 'upgraded_to_paid'


@dataclass
class TrackerState:
    last_check: str
    tracked_commits: dict[str, str] = field(default_factory=lambda: {
        "domains_txt": "",
        "hackerone": "",
        "bugcrowd": "",
        "intigriti": "",
        "yeswehack": "",
    })
    initialized: bool = False


@dataclass
class GitHubCommit:
    sha: str
    commit: dict = field(default_factory=dict)
    # commit.author.date, commit.author.name, commit.message


@dataclass
class DiscoveryResult:
    new_programs: list[ProgramMetadata] = field(default_factory=list)
    scope_expansions: list[ProgramMetadata] = field(default_factory=list)
    upgraded_programs: list[ProgramMetadata] = field(default_factory=list)
    total_checked: int = 0
    check_duration_ms: float = 0
