#!/usr/bin/env python3
"""
update_counts.py -- Update settings.json with fresh system counts.

PURPOSE:
Updates the counts section of settings.json at the end of each session.
Banner and statusline then read from settings.json (instant, no execution).

ARCHITECTURE:
SessionEnd hook -> UpdateCounts -> settings.json
Session start -> Banner reads settings.json (instant)
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from paipy import memory


_pai_dir: Optional[str] = None


def _get_pai_dir() -> str:
    global _pai_dir
    if _pai_dir is None:
        raw = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))
        _pai_dir = os.path.expandvars(raw).replace("~", str(Path.home()))
    return _pai_dir


def _get_settings_path() -> str:
    return os.path.join(_get_pai_dir(), "settings.json")


def _count_files_recursive(directory: str, extension: Optional[str] = None) -> int:
    """Count files matching criteria recursively."""
    count = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=False):
                count += _count_files_recursive(entry.path, extension)
            elif entry.is_file():
                if not extension or entry.name.endswith(extension):
                    count += 1
    except (OSError, PermissionError):
        pass
    return count


def _count_workflow_files(directory: str) -> int:
    """Count .md files inside any Workflows directory."""
    count = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=True):
                if entry.name.lower() == "workflows":
                    count += _count_files_recursive(entry.path, ".md")
                else:
                    count += _count_workflow_files(entry.path)
    except (OSError, PermissionError):
        pass
    return count


def _count_skills(pai_dir: str) -> int:
    """Count skills (directories with SKILL.md file)."""
    count = 0
    skills_dir = os.path.join(pai_dir, "skills")
    try:
        for entry in os.scandir(skills_dir):
            is_dir = entry.is_dir(follow_symlinks=True)
            if is_dir:
                skill_file = os.path.join(skills_dir, entry.name, "SKILL.md")
                if os.path.exists(skill_file):
                    count += 1
    except (OSError, PermissionError):
        pass
    return count


def _count_hooks(pai_dir: str) -> int:
    """Count hooks (.ts files in hooks/ at depth 1)."""
    count = 0
    hooks_dir = os.path.join(pai_dir, "hooks")
    try:
        for entry in os.scandir(hooks_dir):
            if entry.is_file() and entry.name.endswith(".ts"):
                count += 1
    except (OSError, PermissionError):
        pass
    return count


def _count_ratings_lines(file_path: str) -> int:
    """Count non-empty lines in a JSONL file."""
    try:
        if not os.path.isfile(file_path):
            return 0
        return len([l for l in Path(file_path).read_text().split("\n") if l.strip()])
    except Exception:
        return 0


def _count_subdirs(directory: str) -> int:
    """Count immediate subdirectories."""
    try:
        return len([e for e in os.scandir(directory) if e.is_dir()])
    except (OSError, PermissionError):
        return 0


def _get_counts(pai_dir: str) -> Dict[str, Any]:
    """Get all counts."""
    ratings_path = str(memory("LEARNING/SIGNALS") / "ratings.jsonl")
    return {
        "skills": _count_skills(pai_dir),
        "workflows": _count_workflow_files(os.path.join(pai_dir, "skills")),
        "hooks": _count_hooks(pai_dir),
        "signals": _count_files_recursive(str(memory("LEARNING")), ".md"),
        "files": _count_files_recursive(os.path.join(pai_dir, "pai/user")),
        "work": _count_subdirs(str(memory("WORK"))),
        "sessions": _count_files_recursive(str(memory()), ".jsonl"),
        "research": (
            _count_files_recursive(str(memory("RESEARCH")), ".md")
            + _count_files_recursive(str(memory("RESEARCH")), ".json")
        ),
        "ratings": _count_ratings_lines(ratings_path),
        "updatedAt": datetime.utcnow().isoformat() + "Z",
    }


def _refresh_usage_cache(pai_dir: str) -> None:
    """Refresh usage cache from Anthropic OAuth API."""
    usage_cache_path = str(memory("STATE") / "usage-cache.json")

    try:
        # Extract OAuth token
        import platform
        if platform.system() == "Darwin":
            cred_json = subprocess.check_output(
                'security find-generic-password -s "Claude Code-credentials" -w 2>/dev/null',
                shell=True, timeout=3, text=True,
            ).strip()
        else:
            cred_path = os.path.join(os.environ.get("HOME", ""), ".claude", ".credentials.json")
            cred_json = Path(cred_path).read_text().strip()

        parsed = json.loads(cred_json)
        token = parsed.get("claudeAiOauth", {}).get("accessToken")
        if not token:
            return

        req = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
            },
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status != 200:
                return
            data = json.loads(resp.read().decode())

        if not data.get("five_hour"):
            return

        # Try workspace cost if admin key available
        admin_key = os.environ.get("ANTHROPIC_ADMIN_API_KEY")
        if admin_key:
            try:
                now = datetime.utcnow()
                start_of_month = f"{now.year}-{now.month:02d}-01T00:00:00Z"
                cost_req = urllib.request.Request(
                    f"https://api.anthropic.com/v1/organizations/cost_report?starting_at={start_of_month}",
                    headers={
                        "x-api-key": admin_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                with urllib.request.urlopen(cost_req, timeout=5) as cost_resp:
                    if cost_resp.status == 200:
                        cost_data = json.loads(cost_resp.read().decode())
                        total_cost_cents = 0.0
                        for day in (cost_data.get("data") or []):
                            for entry in (day.get("results") or []):
                                total_cost_cents += float(entry.get("amount", "0"))
                        data["workspace_cost"] = {
                            "month_used_cents": round(total_cost_cents),
                            "updated_at": datetime.utcnow().isoformat() + "Z",
                        }
                        print(f"[UpdateCounts] Workspace cost: ${total_cost_cents / 100:.2f} this month", file=sys.stderr)
            except Exception:
                pass

        Path(usage_cache_path).write_text(json.dumps(data, indent=2) + "\n")
        five_hour = data.get("five_hour", {})
        seven_day = data.get("seven_day", {})
        print(
            f"[UpdateCounts] Usage cache refreshed: 5H={five_hour.get('utilization')}% 7D={seven_day.get('utilization')}%",
            file=sys.stderr,
        )
    except Exception:
        pass


def handle_update_counts() -> None:
    """Handler called by the update_counts entry point."""
    pai_dir = _get_pai_dir()
    settings_path = _get_settings_path()

    try:
        counts = _get_counts(pai_dir)
        _refresh_usage_cache(pai_dir)

        settings = json.loads(Path(settings_path).read_text())
        settings["counts"] = counts

        # Extract Algorithm version from CLAUDE.md
        try:
            claude_md = Path(os.path.join(pai_dir, "CLAUDE.md")).read_text()
            algo_match = re.search(r"Algorithm/v([\d.]+)\.md", claude_md)
            if algo_match:
                settings.setdefault("pai", {})["algorithmVersion"] = algo_match.group(1)
        except Exception:
            pass

        Path(settings_path).write_text(json.dumps(settings, indent=2) + "\n")
        print(
            f"[UpdateCounts] Updated: SK:{counts['skills']} WF:{counts['workflows']} "
            f"HK:{counts['hooks']} SIG:{counts['signals']} F:{counts['files']} "
            f"W:{counts['work']} SESS:{counts['sessions']} RES:{counts['research']} "
            f"RAT:{counts['ratings']}",
            file=sys.stderr,
        )
    except Exception as e:
        print(f"[UpdateCounts] Failed to update counts: {e}", file=sys.stderr)


if __name__ == "__main__":
    handle_update_counts()
