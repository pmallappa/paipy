#!/usr/bin/env python3
"""
prd.py -- PRD management: templates, frontmatter, and work.json registry.

Merged from: prd_utils.py + prd_template.py
Wraps all PRD functions in the PRD class.
Preserves CriterionEntry class.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._paths import Paths


class CriterionEntry:
    """A single criterion or anti-criterion from a PRD."""

    def __init__(self, id: str, description: str, type: str, status: str):
        self.id = id
        self.description = description
        self.type = type  # 'criterion' | 'anti-criterion'
        self.status = status  # 'pending' | 'completed'

    def to_dict(self) -> Dict[str, str]:
        return {"id": self.id, "description": self.description, "type": self.type, "status": self.status}


class PRD:
    """PRD template generation, frontmatter parsing, and work.json registry management."""

    # ── Template Constants ────────────────────────────────────────────

    ISC_MINIMUMS = {
        "TRIVIAL":       {"min": 2,  "target": "2-4"},
        "QUICK":         {"min": 4,  "target": "4-8"},
        "STANDARD":      {"min": 8,  "target": "8-16"},
        "EXTENDED":      {"min": 16, "target": "16-32"},
        "ADVANCED":      {"min": 24, "target": "24-48"},
        "DEEP":          {"min": 40, "target": "40-80"},
        "COMPREHENSIVE": {"min": 64, "target": "64-150"},
        "LOOP":          {"min": 16, "target": "16-64"},
    }

    APPETITE_MAP = {
        "TRIVIAL":       {"budget": "<10s",     "circuitBreaker": "1 session"},
        "QUICK":         {"budget": "<1min",    "circuitBreaker": "1 session"},
        "STANDARD":      {"budget": "<2min",    "circuitBreaker": "1 session"},
        "EXTENDED":      {"budget": "<8min",    "circuitBreaker": "2 sessions"},
        "ADVANCED":      {"budget": "<16min",   "circuitBreaker": "3 sessions"},
        "DEEP":          {"budget": "<32min",   "circuitBreaker": "3 sessions"},
        "COMPREHENSIVE": {"budget": "<120m",    "circuitBreaker": "5 sessions"},
        "LOOP":          {"budget": "unbounded", "circuitBreaker": "max iterations"},
    }

    # ── Path Helpers ──────────────────────────────────────────────────

    @staticmethod
    def get_work_dir() -> str:
        return Paths.memory_str("WORK")

    @staticmethod
    def get_work_json() -> str:
        return Paths.memory_str("STATE", "work.json")

    # ── PRD Discovery ─────────────────────────────────────────────────

    @staticmethod
    def find_latest_prd() -> Optional[str]:
        """Find the most recently modified PRD.md file."""
        work_dir = PRD.get_work_dir()
        if not os.path.isdir(work_dir):
            return None

        latest: Optional[str] = None
        latest_mtime = 0.0

        for dir_name in os.listdir(work_dir):
            prd = os.path.join(work_dir, dir_name, "PRD.md")
            try:
                s = os.stat(prd)
                if s.st_mtime > latest_mtime:
                    latest_mtime = s.st_mtime
                    latest = prd
            except OSError:
                pass

        return latest

    # ── Frontmatter ───────────────────────────────────────────────────

    @staticmethod
    def parse_frontmatter(content: str) -> Optional[Dict[str, str]]:
        """Parse YAML frontmatter from content."""
        match = re.match(r"^---\n([\s\S]*?)\n---", content)
        if not match:
            return None

        fm: Dict[str, str] = {}
        for line in match.group(1).split("\n"):
            idx = line.find(":")
            if idx > 0:
                key = line[:idx].strip()
                value = line[idx + 1:].strip().strip("\"'")
                fm[key] = value
        return fm

    @staticmethod
    def write_frontmatter_field(content: str, field: str, value: str) -> str:
        """Update a single field in existing frontmatter."""
        fm_match = re.match(r"^(---\n)([\s\S]*?)(\n---)", content)
        if not fm_match:
            return content

        lines = fm_match.group(2).split("\n")
        found = False
        for i, line in enumerate(lines):
            if line.startswith(f"{field}:"):
                lines[i] = f"{field}: {value}"
                found = True
                break

        if not found:
            lines.append(f"{field}: {value}")

        return fm_match.group(1) + "\n".join(lines) + fm_match.group(3) + content[fm_match.end():]

    # ── Criteria ──────────────────────────────────────────────────────

    @staticmethod
    def count_criteria(content: str) -> Dict[str, int]:
        """Count checked/unchecked in Criteria section."""
        criteria_match = re.search(r"## Criteria\n([\s\S]*?)(?=\n## |\n---|$)", content)
        if not criteria_match:
            return {"checked": 0, "total": 0}

        lines = [l for l in criteria_match.group(1).split("\n") if re.match(r"^- \[[ x]\]", l)]
        checked = len([l for l in lines if l.startswith("- [x]")])
        return {"checked": checked, "total": len(lines)}

    @staticmethod
    def parse_criteria_list(content: str) -> List[CriterionEntry]:
        """Parse criteria list from PRD content."""
        criteria_match = re.search(r"## Criteria\n([\s\S]*?)(?=\n## |\n---|$)", content)
        if not criteria_match:
            return []

        result = []
        for line in criteria_match.group(1).split("\n"):
            if not re.match(r"^- \[[ x]\]", line):
                continue
            checked = line.startswith("- [x]")
            text_match = re.match(r"^- \[[ x]\]\s*(ISC-[\w-]+):\s*(.*)", line)
            if not text_match:
                continue
            cid = text_match.group(1)
            description = text_match.group(2).strip()
            is_anti = "-A-" in cid
            result.append(CriterionEntry(
                id=cid,
                description=description,
                type="anti-criterion" if is_anti else "criterion",
                status="completed" if checked else "pending",
            ))
        return result

    # ── Work JSON Registry ────────────────────────────────────────────

    @staticmethod
    def read_registry() -> Dict[str, Any]:
        """Read work.json registry."""
        work_json = PRD.get_work_json()
        try:
            data = json.loads(Path(work_json).read_text())
            return data if "sessions" in data else {"sessions": {}}
        except Exception:
            return {"sessions": {}}

    @staticmethod
    def write_registry(reg: Dict[str, Any]) -> None:
        """Write work.json registry atomically."""
        work_json = PRD.get_work_json()
        state_dir = os.path.dirname(work_json)
        os.makedirs(state_dir, exist_ok=True)
        tmp = work_json + ".tmp"
        Path(tmp).write_text(json.dumps(reg, indent=2))
        os.rename(tmp, work_json)

    @staticmethod
    def sync_to_work_json(
        fm: Dict[str, str],
        prd_path: str,
        content: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Upsert session into work.json from frontmatter."""
        if not fm.get("slug"):
            return

        pai_dir = Paths.pai_str()
        relative_prd = prd_path.replace(pai_dir + "/", "")
        registry = PRD.read_registry()

        # Migration: remove placeholder entries
        if session_id:
            for slug in list(registry["sessions"].keys()):
                session = registry["sessions"][slug]
                if (session.get("sessionUUID") == session_id
                        and session.get("mode") in ("starting", "native")
                        and slug != fm["slug"]):
                    del registry["sessions"][slug]
                    break

        existing = registry["sessions"].get(fm["slug"], {})
        new_phase = fm.get("phase", "observe")
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Look up session name
        session_name = existing.get("sessionName", "")
        if session_id:
            try:
                names_path = Paths.memory_str("STATE", "session-names.json")
                if os.path.exists(names_path):
                    names = json.loads(Path(names_path).read_text())
                    if session_id in names:
                        session_name = names[session_id]
            except Exception:
                pass

        # Build phase history
        phase_history = existing.get("phaseHistory", [])
        last_phase = phase_history[-1] if phase_history else None
        if not last_phase or last_phase.get("phase") != new_phase.upper():
            if last_phase and not last_phase.get("completedAt"):
                last_phase["completedAt"] = int(time.time() * 1000)
            phase_history.append({
                "phase": new_phase.upper(),
                "startedAt": int(datetime.now(timezone.utc).timestamp() * 1000),
                "criteriaCount": 0,
                "agentCount": 0,
            })

        criteria = [c.to_dict() for c in PRD.parse_criteria_list(content)] if content else existing.get("criteria", [])

        if phase_history:
            phase_history[-1]["criteriaCount"] = len(criteria)

        entry: Dict[str, Any] = {
            "prd": relative_prd,
            "task": fm.get("task", ""),
            "phase": new_phase,
            "progress": fm.get("progress", "0/0"),
            "effort": fm.get("effort", "standard"),
            "mode": fm.get("mode", "interactive"),
            "started": fm.get("started", timestamp),
            "updatedAt": timestamp,
            "criteria": criteria,
            "phaseHistory": phase_history,
        }
        if session_name:
            entry["sessionName"] = session_name
        if session_id or existing.get("sessionUUID"):
            entry["sessionUUID"] = session_id or existing.get("sessionUUID")
        if fm.get("iteration"):
            try:
                entry["iteration"] = int(fm["iteration"])
            except ValueError:
                entry["iteration"] = 1

        registry["sessions"][fm["slug"]] = entry

        # Clean stale sessions
        now = int(time.time() * 1000)
        seven_days = 7 * 86400000
        for slug in list(registry["sessions"].keys()):
            session = registry["sessions"][slug]
            try:
                updated = int(datetime.fromisoformat(
                    (session.get("updatedAt") or session.get("started") or "1970-01-01T00:00:00Z").replace("Z", "+00:00")
                ).timestamp() * 1000)
            except Exception:
                updated = 0
            if session.get("phase") == "complete" and now - updated > 86400000:
                del registry["sessions"][slug]
            elif now - updated > seven_days:
                del registry["sessions"][slug]

        PRD.write_registry(registry)

    @staticmethod
    def update_session_name_in_work_json(session_uuid: str, session_name: str) -> None:
        """Update sessionName in work.json for a given session UUID."""
        try:
            registry = PRD.read_registry()
            best_slug: Optional[str] = None
            best_time = 0
            for slug, session in registry["sessions"].items():
                if session.get("sessionUUID") != session_uuid:
                    continue
                if session.get("phase") == "complete":
                    continue
                try:
                    t = int(datetime.fromisoformat(
                        (session.get("updatedAt") or session.get("started") or "1970-01-01T00:00:00Z").replace("Z", "+00:00")
                    ).timestamp() * 1000)
                except Exception:
                    t = 0
                if t > best_time:
                    best_time = t
                    best_slug = slug

            if best_slug:
                registry["sessions"][best_slug]["sessionName"] = session_name
                registry["sessions"][best_slug]["updatedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                PRD.write_registry(registry)
        except Exception:
            pass

    @staticmethod
    def upsert_session(
        session_uuid: str,
        session_name: str,
        task: str,
        mode: str = "native",
    ) -> None:
        """
        Upsert a session into work.json -- handles BOTH native and algorithm modes.
        Called by session_auto_name on first prompt for ALL sessions.
        """
        try:
            registry = PRD.read_registry()
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

            existing_slug: Optional[str] = None
            for slug, session in registry["sessions"].items():
                if session.get("sessionUUID") == session_uuid and session.get("mode") in ("native", "starting"):
                    existing_slug = slug
                    break

            if existing_slug:
                registry["sessions"][existing_slug]["updatedAt"] = timestamp
                if session_name:
                    registry["sessions"][existing_slug]["sessionName"] = session_name
            else:
                now = datetime.now(timezone.utc)
                date_prefix = now.strftime("%Y%m%d-%H%M00")
                task_slug = re.sub(r"[^a-z0-9]+", "-", (task or session_name or "session").lower()).strip("-")[:40]
                slug = f"{date_prefix}_{task_slug}"

                registry["sessions"][slug] = {
                    "task": task or session_name or ("Native session" if mode == "native" else "Starting..."),
                    "sessionName": session_name or None,
                    "sessionUUID": session_uuid,
                    "phase": "native" if mode == "native" else "starting",
                    "progress": "0/0",
                    "effort": "native" if mode == "native" else "standard",
                    "mode": mode,
                    "started": timestamp,
                    "updatedAt": timestamp,
                }

            PRD.write_registry(registry)
        except Exception:
            pass

    # Deprecated alias
    upsert_native_session = upsert_session

    # ── Template Generation ───────────────────────────────────────────

    @staticmethod
    def curate_title(raw_prompt: str) -> str:
        """
        Curate a title from raw user prompt into a readable PRD title.
        Heuristic -- no inference call, runs instantly.
        """
        title = raw_prompt.strip()

        title = re.sub(
            r"^(okay|ok|hey|so|um|uh|well|right|alright|please|can you|i want you to|i need you to|i want to|we need to|lets|let's)\s+",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(
            r"\b(fuck|fucking|shit|shitty|damn|damnit|ass|bitch|motherfuck\w*|dumbass|goddamn)\b\s*",
            "",
            title,
            flags=re.IGNORECASE,
        )

        title = re.sub(r"\s+", " ", title).strip()

        if title:
            title = title[0].upper() + title[1:]

        if len(title) > 80:
            truncated = title[:80]
            last_space = truncated.rfind(" ")
            title = truncated[:last_space] if last_space > 40 else truncated

        return title or "Untitled Task"

    @staticmethod
    def generate_prd_filename(slug: str) -> str:
        """Generate a PRD filename: PRD-{YYYYMMDD}-{slug}.md"""
        now = datetime.now(timezone.utc)
        return f"PRD-{now.strftime('%Y%m%d')}-{slug}.md"

    @staticmethod
    def generate_prd_id(slug: str) -> str:
        """Generate a PRD ID: PRD-{YYYYMMDD}-{slug}"""
        now = datetime.now(timezone.utc)
        return f"PRD-{now.strftime('%Y%m%d')}-{slug}"

    @staticmethod
    def generate_prd_template(
        title: str,
        slug: str,
        effort_level: str = "Standard",
        mode: str = "interactive",
        prompt: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Generate a consolidated PRD file -- single source of truth for each work item."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        timestamp = datetime.now(timezone.utc).isoformat() + "Z"
        prd_id = PRD.generate_prd_id(slug)
        effort = effort_level
        effort_upper = effort.upper()

        curated_title = PRD.curate_title(prompt) if prompt else title

        prompt_section = (
            f"### Problem Space\n{prompt[:500]}\n"
            if prompt
            else "### Problem Space\n_To be populated during OBSERVE phase._\n"
        )

        isc_guide = PRD.ISC_MINIMUMS.get(effort_upper, PRD.ISC_MINIMUMS["STANDARD"])
        appetite = PRD.APPETITE_MAP.get(effort_upper, PRD.APPETITE_MAP["STANDARD"])

        escaped_title = curated_title.replace('"', '\\"')

        return f"""---
prd: true
id: {prd_id}
title: "{escaped_title}"
session_id: "{session_id or 'unknown'}"
status: ACTIVE
mode: {mode}
effort_level: {effort}
created: {today}
updated: {today}
completed_at: null
iteration: 0
maxIterations: 128
loopStatus: null
last_phase: null
failing_criteria: []
verification_summary: "0/0"
parent: null
children: []
---

# {curated_title}

> _To be populated during OBSERVE: what this achieves and why it matters._

## STATUS

| What | State |
|------|-------|
| Progress | 0/0 criteria passing |
| Phase | ACTIVE |
| Next action | OBSERVE phase -- create ISC |
| Blocked by | nothing |

## APPETITE

| Budget | Circuit Breaker | ISC Target |
|--------|----------------|------------|
| {appetite['budget']} | {appetite['circuitBreaker']} | {isc_guide['target']} criteria |

## CONTEXT

{prompt_section}
### Key Files
_To be populated during exploration._

## RISKS & RABBIT HOLES

_To be populated during THINK phase._

## PLAN

_To be populated during PLAN phase._

## IDEAL STATE CRITERIA (Verification Criteria)

### Criteria

### Anti-Criteria

## DECISIONS

_Non-obvious technical decisions logged here during BUILD/EXECUTE._

## CHANGELOG

- {timestamp} | CREATED | {effort} effort | {isc_guide['target']} ISC target
"""
