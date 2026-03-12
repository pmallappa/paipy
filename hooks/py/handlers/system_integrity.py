#!/usr/bin/env python3
"""
system_integrity.py -- Automatic system integrity maintenance handler.

Detects PAI system changes from the transcript and spawns background
IntegrityMaintenance process to update references and document changes.

TRIGGER: SessionEnd hook (via integrity_check entry point)

SIDE EFFECTS:
- Spawns background IntegrityMaintenance process
- Updates memory/state/integrity-state.json

THROTTLING:
- 2-minute cooldown between runs
- Deduplicates identical change sets
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from paipy import (
    FileChange,
    memory,
    parse_tool_use_blocks,
    is_significant_change,
    is_in_cooldown,
    is_duplicate_run,
    hash_changes,
    get_cooldown_end_time,
    determine_significance,
    infer_change_type,
    generate_descriptive_title,
)


_pai_dir: Optional[str] = None


def _get_pai_dir() -> str:
    global _pai_dir
    if _pai_dir is None:
        raw = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))
        _pai_dir = os.path.expandvars(raw).replace("~", str(Path.home()))
    return _pai_dir


def _pai_path(*segments: str) -> str:
    return os.path.join(_get_pai_dir(), *segments)


def _update_integrity_state(changes: list) -> None:
    """Update the integrity state file."""
    try:
        state_dir = memory("STATE")
        state_file = os.path.join(str(state_dir), "integrity-state.json")

        from datetime import datetime, timezone
        state = {
            "last_run": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "last_changes_hash": hash_changes(changes),
            "cooldown_until": get_cooldown_end_time(),
        }
        Path(state_file).write_text(json.dumps(state, indent=2))
        print("[SystemIntegrity] Updated state file", file=sys.stderr)
    except Exception as e:
        print(f"[SystemIntegrity] Failed to update state: {e}", file=sys.stderr)


def _spawn_integrity_maintenance(changes: list, session_id: str, transcript_path: str) -> None:
    """Spawn the IntegrityMaintenance script in the background."""
    try:
        integrity_script = _pai_path("PAI", "Tools", "IntegrityMaintenance.ts")
        if not os.path.exists(integrity_script):
            print(f"[SystemIntegrity] IntegrityMaintenance.ts not found: {integrity_script}", file=sys.stderr)
            return

        filtered_changes = [c for c in changes if c.category is not None]
        title = generate_descriptive_title(filtered_changes)
        significance = determine_significance(filtered_changes)
        change_type = infer_change_type(filtered_changes)

        print(f"[SystemIntegrity] Title: {title}", file=sys.stderr)
        print(f"[SystemIntegrity] Significance: {significance}", file=sys.stderr)
        print(f"[SystemIntegrity] Change type: {change_type}", file=sys.stderr)

        input_data = json.dumps({
            "session_id": session_id,
            "transcript_path": transcript_path,
            "changes": [
                {
                    "tool": c.tool,
                    "path": c.path,
                    "category": c.category,
                    "isPhilosophical": c.isPhilosophical,
                    "isStructural": c.isStructural,
                }
                for c in filtered_changes
            ],
        })

        child = subprocess.Popen(
            ["bun", integrity_script],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=None,  # inherit stderr
            start_new_session=True,
        )
        if child.stdin:
            child.stdin.write(input_data.encode())
            child.stdin.close()

        print(f"[SystemIntegrity] Spawned IntegrityMaintenance (pid: {child.pid})", file=sys.stderr)
    except Exception as e:
        print(f"[SystemIntegrity] Failed to spawn IntegrityMaintenance: {e}", file=sys.stderr)


def handle_system_integrity(session_id: str, transcript_path: str) -> None:
    """
    Handle system integrity check.

    1. Parses the transcript for file modification tool_use blocks
    2. Filters for PAI system paths (excludes WORK/, LEARNING/)
    3. Checks throttle cooldown
    4. Spawns background IntegrityMaintenance if changes detected
    """
    print("[SystemIntegrity] Checking for system changes...", file=sys.stderr)

    if is_in_cooldown():
        print("[SystemIntegrity] In cooldown period, skipping", file=sys.stderr)
        return

    changes = parse_tool_use_blocks(transcript_path)
    print(f"[SystemIntegrity] Found {len(changes)} file changes in transcript", file=sys.stderr)

    system_changes = [c for c in changes if c.category is not None]
    print(f"[SystemIntegrity] {len(system_changes)} are PAI system changes", file=sys.stderr)

    if not system_changes:
        print("[SystemIntegrity] No system changes detected, skipping", file=sys.stderr)
        return

    if not is_significant_change(system_changes):
        print("[SystemIntegrity] Changes not significant enough, skipping", file=sys.stderr)
        return

    if is_duplicate_run(changes):
        print("[SystemIntegrity] Duplicate change set, skipping", file=sys.stderr)
        return

    print("[SystemIntegrity] Significant changes detected:", file=sys.stderr)
    for change in system_changes[:5]:
        print(f"  - [{change.category}] {change.path}", file=sys.stderr)
    if len(system_changes) > 5:
        print(f"  ... and {len(system_changes) - 5} more", file=sys.stderr)

    _update_integrity_state(system_changes)
    _spawn_integrity_maintenance(system_changes, session_id, transcript_path)
    print("[SystemIntegrity] Background integrity check started", file=sys.stderr)
