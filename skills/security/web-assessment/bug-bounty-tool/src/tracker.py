#!/usr/bin/env python3
"""Main bug bounty tracker with two-tier detection."""

from __future__ import annotations

import time
from datetime import datetime, timedelta

from .config import CONFIG
from .github import GitHubClient
from .state import StateManager
from .types import DiscoveryResult, ProgramMetadata, TrackerState


class BugBountyTracker:
    def __init__(self) -> None:
        self.github = GitHubClient()
        self.state = StateManager()

    def initialize(self) -> None:
        """Initialize the tracker (first-time setup)."""
        print("Initializing bug bounty tracker...")

        current_state = self.state.load_state()

        if current_state.initialized:
            print("Tracker already initialized")
            return

        # Get latest commits for all tracked files
        domains_commit = self.github.get_latest_commit(CONFIG["files"]["domains_txt"])
        hackerone_commit = self.github.get_latest_commit(CONFIG["files"]["hackerone"])
        bugcrowd_commit = self.github.get_latest_commit(CONFIG["files"]["bugcrowd"])
        intigriti_commit = self.github.get_latest_commit(CONFIG["files"]["intigriti"])
        yeswehack_commit = self.github.get_latest_commit(CONFIG["files"]["yeswehack"])

        new_state = TrackerState(
            last_check=datetime.now().isoformat(),
            tracked_commits={
                "domains_txt": (domains_commit or {}).get("sha", ""),
                "hackerone": (hackerone_commit or {}).get("sha", ""),
                "bugcrowd": (bugcrowd_commit or {}).get("sha", ""),
                "intigriti": (intigriti_commit or {}).get("sha", ""),
                "yeswehack": (yeswehack_commit or {}).get("sha", ""),
            },
            initialized=True,
        )

        self.state.save_state(new_state)

        print("Tracker initialized successfully")
        print(f"   Last check: {new_state.last_check}")
        print("   Tracking commits from all platforms")

    def update(self) -> DiscoveryResult:
        """Update bug bounty programs (main workflow)."""
        start_time = time.time()
        print("Checking for new bug bounty programs...\n")

        current_state = self.state.load_state()

        if not current_state.initialized:
            print("Tracker not initialized. Run initialization first.")
            self.initialize()
            return DiscoveryResult(
                total_checked=0,
                check_duration_ms=(time.time() - start_time) * 1000,
            )

        # TIER 1: Fast detection
        print("TIER 1: Fast change detection")
        domain_commits = self.github.get_commits_since(
            CONFIG["files"]["domains_txt"],
            current_state.last_check,
        )

        if not domain_commits:
            print("No changes detected - all programs up to date\n")
            return DiscoveryResult(
                total_checked=5,
                check_duration_ms=(time.time() - start_time) * 1000,
            )

        print(f"Changes detected! {len(domain_commits)} commits since last check\n")

        # TIER 2: Detailed analysis
        print("TIER 2: Detailed analysis of platform changes")
        results = self._analyze_changes(current_state)

        # Update state
        latest_domains = self.github.get_latest_commit(CONFIG["files"]["domains_txt"])
        if latest_domains:
            current_state.tracked_commits["domains_txt"] = latest_domains["sha"]
        current_state.last_check = datetime.now().isoformat()
        self.state.save_state(current_state)

        # Save discoveries
        all_changes = (
            results["new_programs"]
            + results["scope_expansions"]
            + results["upgraded_programs"]
        )

        if all_changes:
            existing_changes = self.state.load_recent_changes()
            self.state.save_recent_changes(existing_changes + all_changes)
            self.state.log_discovery(
                datetime.now().isoformat(),
                f"Discovered {len(all_changes)} changes",
                {
                    "new_programs": len(results["new_programs"]),
                    "scope_expansions": len(results["scope_expansions"]),
                    "upgraded_programs": len(results["upgraded_programs"]),
                },
            )

        duration = (time.time() - start_time) * 1000
        print(f"\nCompleted in {duration / 1000:.1f}s")

        return DiscoveryResult(
            new_programs=results["new_programs"],
            scope_expansions=results["scope_expansions"],
            upgraded_programs=results["upgraded_programs"],
            total_checked=5,
            check_duration_ms=duration,
        )

    def _analyze_changes(self, current_state: TrackerState) -> dict[str, list[ProgramMetadata]]:
        """Analyze changes in each platform."""
        new_programs: list[ProgramMetadata] = []
        scope_expansions: list[ProgramMetadata] = []
        upgraded_programs: list[ProgramMetadata] = []

        metadata = self.state.load_metadata()

        platforms = ["hackerone", "bugcrowd", "intigriti", "yeswehack"]

        for platform in platforms:
            print(f"  Checking {platform}...")

            file_key = platform
            commits = self.github.get_commits_since(
                CONFIG["files"][file_key],
                current_state.last_check,
            )

            if not commits:
                print("    No changes")
                continue

            print(f"    {len(commits)} commits found")

            latest_data = self.github.fetch_file(CONFIG["files"][file_key])
            programs = self.github.parse_programs(latest_data, platform)

            for program in programs:
                key = f"{program.platform}:{program.handle}"
                existing = metadata.get(key)

                if not existing:
                    meta = ProgramMetadata(
                        name=program.name,
                        platform=program.platform,
                        handle=program.handle,
                        url=program.url,
                        offers_bounties=program.offers_bounties,
                        key_scopes=program.key_scopes,
                        discovered_at=datetime.now().isoformat(),
                        max_severity=program.max_severity,
                        change_type="new_program",
                    )
                    new_programs.append(meta)
                    metadata[key] = meta
                else:
                    if not existing.offers_bounties and program.offers_bounties:
                        meta = ProgramMetadata(
                            name=existing.name,
                            platform=existing.platform,
                            handle=existing.handle,
                            url=existing.url,
                            offers_bounties=True,
                            key_scopes=existing.key_scopes,
                            discovered_at=datetime.now().isoformat(),
                            max_severity=existing.max_severity,
                            change_type="upgraded_to_paid",
                        )
                        upgraded_programs.append(meta)
                        metadata[key] = meta
                    elif len(program.key_scopes) > len(existing.key_scopes):
                        meta = ProgramMetadata(
                            name=existing.name,
                            platform=existing.platform,
                            handle=existing.handle,
                            url=existing.url,
                            offers_bounties=existing.offers_bounties,
                            key_scopes=program.key_scopes,
                            discovered_at=datetime.now().isoformat(),
                            max_severity=existing.max_severity,
                            change_type="scope_expansion",
                        )
                        scope_expansions.append(meta)
                        metadata[key] = meta

            latest_commit = self.github.get_latest_commit(CONFIG["files"][file_key])
            if latest_commit:
                current_state.tracked_commits[platform] = latest_commit["sha"]

        self.state.save_metadata(metadata)

        return {
            "new_programs": new_programs,
            "scope_expansions": scope_expansions,
            "upgraded_programs": upgraded_programs,
        }

    def get_recent_discoveries(self, hours_ago: int = 24) -> list[ProgramMetadata]:
        """Get recent discoveries within a time window."""
        changes = self.state.load_recent_changes()
        cutoff_date = datetime.now() - timedelta(hours=hours_ago)

        return [
            p for p in changes
            if datetime.fromisoformat(p.discovered_at) >= cutoff_date
        ]

    def get_all_programs(self) -> list[ProgramMetadata]:
        """Get all cached programs."""
        metadata = self.state.load_metadata()
        return list(metadata.values())

    def search_programs(self, query: str) -> list[ProgramMetadata]:
        """Search programs by name or platform."""
        metadata = self.state.load_metadata()
        lower_query = query.lower()

        return [
            p for p in metadata.values()
            if lower_query in p.name.lower()
            or lower_query in p.platform.lower()
            or lower_query in p.handle.lower()
        ]
