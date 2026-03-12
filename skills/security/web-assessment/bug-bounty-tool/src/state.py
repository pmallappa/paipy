#!/usr/bin/env python3
"""State management for bug bounty tracker."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import CONFIG
from .types import ProgramMetadata, TrackerState


class StateManager:
    def __init__(self) -> None:
        self.state_path = os.path.expanduser(CONFIG["paths"]["state"])
        self.metadata_path = os.path.join(
            os.path.expanduser(CONFIG["paths"]["cache"]),
            CONFIG["cache"]["metadata_file"],
        )
        self.recent_changes_path = os.path.join(
            os.path.expanduser(CONFIG["paths"]["cache"]),
            CONFIG["cache"]["recent_changes_file"],
        )

    def ensure_directories(self) -> None:
        cache_dir = os.path.expanduser(CONFIG["paths"]["cache"])
        logs_dir = os.path.expanduser(CONFIG["paths"]["logs"])
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        Path(logs_dir).mkdir(parents=True, exist_ok=True)

    def load_state(self) -> TrackerState:
        try:
            data = json.loads(Path(self.state_path).read_text())
            return TrackerState(
                last_check=data.get("last_check", "1970-01-01T00:00:00Z"),
                tracked_commits=data.get("tracked_commits", {
                    "domains_txt": "",
                    "hackerone": "",
                    "bugcrowd": "",
                    "intigriti": "",
                    "yeswehack": "",
                }),
                initialized=data.get("initialized", False),
            )
        except (FileNotFoundError, json.JSONDecodeError):
            return TrackerState(
                last_check="1970-01-01T00:00:00Z",
                tracked_commits={
                    "domains_txt": "",
                    "hackerone": "",
                    "bugcrowd": "",
                    "intigriti": "",
                    "yeswehack": "",
                },
                initialized=False,
            )

    def save_state(self, state: TrackerState) -> None:
        self.ensure_directories()
        data = {
            "last_check": state.last_check,
            "tracked_commits": state.tracked_commits,
            "initialized": state.initialized,
        }
        Path(self.state_path).write_text(json.dumps(data, indent=2))

    def load_metadata(self) -> dict[str, ProgramMetadata]:
        try:
            data = json.loads(Path(self.metadata_path).read_text())
            result: dict[str, ProgramMetadata] = {}
            for program in data:
                key = f"{program['platform']}:{program['handle']}"
                result[key] = ProgramMetadata(
                    name=program["name"],
                    platform=program["platform"],
                    handle=program["handle"],
                    url=program["url"],
                    offers_bounties=program.get("offers_bounties", False),
                    key_scopes=program.get("key_scopes", []),
                    discovered_at=program.get("discovered_at", ""),
                    max_severity=program.get("max_severity"),
                    change_type=program.get("change_type"),
                )
            return result
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_metadata(self, metadata: dict[str, ProgramMetadata]) -> None:
        self.ensure_directories()
        cutoff_date = datetime.now() - timedelta(days=CONFIG["cache"]["max_age_days"])

        programs = []
        for pm in metadata.values():
            try:
                discovered = datetime.fromisoformat(pm.discovered_at)
                if discovered < cutoff_date:
                    continue
            except ValueError:
                pass
            programs.append({
                "name": pm.name,
                "platform": pm.platform,
                "handle": pm.handle,
                "url": pm.url,
                "offers_bounties": pm.offers_bounties,
                "key_scopes": pm.key_scopes,
                "discovered_at": pm.discovered_at,
                "max_severity": pm.max_severity,
                "change_type": pm.change_type,
            })

        Path(self.metadata_path).write_text(json.dumps(programs, indent=2))

    def load_recent_changes(self) -> list[ProgramMetadata]:
        try:
            data = json.loads(Path(self.recent_changes_path).read_text())
            return [
                ProgramMetadata(
                    name=p["name"],
                    platform=p["platform"],
                    handle=p["handle"],
                    url=p["url"],
                    offers_bounties=p.get("offers_bounties", False),
                    key_scopes=p.get("key_scopes", []),
                    discovered_at=p.get("discovered_at", ""),
                    max_severity=p.get("max_severity"),
                    change_type=p.get("change_type"),
                )
                for p in data
            ]
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def save_recent_changes(self, changes: list[ProgramMetadata]) -> None:
        self.ensure_directories()
        cutoff_date = datetime.now() - timedelta(days=CONFIG["cache"]["max_age_days"])

        filtered = []
        for pm in changes:
            try:
                discovered = datetime.fromisoformat(pm.discovered_at)
                if discovered < cutoff_date:
                    continue
            except ValueError:
                pass
            filtered.append({
                "name": pm.name,
                "platform": pm.platform,
                "handle": pm.handle,
                "url": pm.url,
                "offers_bounties": pm.offers_bounties,
                "key_scopes": pm.key_scopes,
                "discovered_at": pm.discovered_at,
                "max_severity": pm.max_severity,
                "change_type": pm.change_type,
            })

        Path(self.recent_changes_path).write_text(json.dumps(filtered, indent=2))

    def log_discovery(self, timestamp: str, message: str, data: Optional[dict] = None) -> None:
        self.ensure_directories()
        log_path = os.path.join(
            os.path.expanduser(CONFIG["paths"]["logs"]),
            "discovery.jsonl",
        )
        log_entry = {
            "timestamp": timestamp,
            "message": message,
            "data": data,
        }

        try:
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as error:
            print(f"Failed to write log: {error}")
