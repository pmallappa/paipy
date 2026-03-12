#!/usr/bin/env python3
"""
changes.py -- Utilities for detecting PAI system changes.

Renamed from: change_detection.py
Wraps all detection functions in the ChangeDetector class.
Preserves FileChange and IntegrityState dataclasses.
"""

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Literal, Optional, Set

from ._paths import Paths


# ── Types ─────────────────────────────────────────────────────────────────

ChangeCategory = Literal[
    "skill", "hook", "workflow", "config",
    "core-system", "memory-system", "documentation",
]

SignificanceLabel = Literal["trivial", "minor", "moderate", "major", "critical"]

ChangeType = Literal[
    "skill_update", "structure_change", "doc_update", "hook_update",
    "workflow_update", "config_update", "tool_update", "multi_area",
]


@dataclass
class FileChange:
    tool: str  # 'Write' | 'Edit' | 'MultiEdit'
    path: str
    category: Optional[ChangeCategory]
    isPhilosophical: bool
    isStructural: bool


@dataclass
class IntegrityState:
    last_run: str
    last_changes_hash: str
    cooldown_until: Optional[str]


class ChangeDetector:
    """Utilities for detecting and categorizing PAI system changes."""

    # ── Path Constants ────────────────────────────────────────────────

    EXCLUDED_PATHS = [
        "memory/work/", "memory/learning/", "memory/state/",
        "plans/", "projects/", ".git/", "node_modules/", "ShellSnapshots/",
    ]

    HIGH_PRIORITY_PATHS = [
        "pai/", "PAISYSTEMARCHITECTURE.md", "SKILLSYSTEM.md",
        "MEMORYSYSTEM.md", "THEHOOKSYSTEM.md", "THEDELEGATIONSYSTEM.md",
        "THENOTIFICATIONSYSTEM.md", "settings.json",
    ]

    PHILOSOPHICAL_PATTERNS = [
        re.compile(r"pai/", re.IGNORECASE),
        re.compile(r"ARCHITECTURE", re.IGNORECASE),
        re.compile(r"PRINCIPLES", re.IGNORECASE),
        re.compile(r"FOUNDING", re.IGNORECASE),
        re.compile(r"IDENTITY", re.IGNORECASE),
    ]

    STRUCTURAL_PATTERNS = [
        re.compile(r"/SKILL\.md$", re.IGNORECASE),
        re.compile(r"/workflows/", re.IGNORECASE),
        re.compile(r"settings\.json$", re.IGNORECASE),
        re.compile(r"frontmatter", re.IGNORECASE),
    ]

    COOLDOWN_MINUTES = 2

    # ── Private Helpers ───────────────────────────────────────────────

    @staticmethod
    def _state_file() -> str:
        return Paths.memory_str("STATE", "integrity-state.json")

    @staticmethod
    def _normalize_to_relative_path(absolute_path: str) -> str:
        pai_dir = Paths.pai_str()
        if absolute_path.startswith(pai_dir):
            return os.path.relpath(absolute_path, pai_dir)
        return absolute_path

    @staticmethod
    def _create_file_change(tool: str, path: str) -> FileChange:
        return FileChange(
            tool=tool,
            path=path,
            category=ChangeDetector.categorize_change(path),
            isPhilosophical=ChangeDetector._is_philosophical_path(path),
            isStructural=ChangeDetector._is_structural_path(path),
        )

    @staticmethod
    def _is_philosophical_path(path: str) -> bool:
        for pattern in ChangeDetector.PHILOSOPHICAL_PATTERNS:
            if pattern.search(path):
                return True
        for high_priority in ChangeDetector.HIGH_PRIORITY_PATHS:
            if high_priority in path:
                return True
        return False

    @staticmethod
    def _is_structural_path(path: str) -> bool:
        for pattern in ChangeDetector.STRUCTURAL_PATTERNS:
            if pattern.search(path):
                return True
        return False

    # ── Transcript Parsing ────────────────────────────────────────────

    @staticmethod
    def parse_tool_use_blocks(transcript_path: str) -> List[FileChange]:
        """Parse tool_use blocks from a transcript that modify files."""
        try:
            if not os.path.exists(transcript_path):
                print(f"[ChangeDetector] Transcript not found: {transcript_path}", file=sys.stderr)
                return []

            content = Path(transcript_path).read_text()
            lines = content.strip().split("\n")
            changes: List[FileChange] = []
            seen_paths: Set[str] = set()

            for line in lines:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "assistant" and entry.get("message", {}).get("content"):
                        content_array = entry["message"]["content"]
                        if not isinstance(content_array, list):
                            content_array = []

                        for block in content_array:
                            if block.get("type") != "tool_use":
                                continue
                            tool_name = block.get("name", "")
                            inp = block.get("input", {})

                            if tool_name == "Write" and inp.get("file_path"):
                                path = ChangeDetector._normalize_to_relative_path(inp["file_path"])
                                if path not in seen_paths:
                                    seen_paths.add(path)
                                    changes.append(ChangeDetector._create_file_change("Write", path))
                            elif tool_name == "Edit" and inp.get("file_path"):
                                path = ChangeDetector._normalize_to_relative_path(inp["file_path"])
                                if path not in seen_paths:
                                    seen_paths.add(path)
                                    changes.append(ChangeDetector._create_file_change("Edit", path))
                            elif tool_name == "MultiEdit" and inp.get("edits"):
                                for edit in inp["edits"]:
                                    if edit.get("file_path"):
                                        path = ChangeDetector._normalize_to_relative_path(edit["file_path"])
                                        if path not in seen_paths:
                                            seen_paths.add(path)
                                            changes.append(ChangeDetector._create_file_change("Edit", path))
                except Exception:
                    pass

            return changes
        except Exception as e:
            print(f"[ChangeDetector] Error parsing transcript: {e}", file=sys.stderr)
            return []

    # ── Change Categorization ─────────────────────────────────────────

    @staticmethod
    def categorize_change(path: str) -> Optional[ChangeCategory]:
        """Categorize a file path by its location in the PAI system."""
        pai_dir = Paths.pai_str()

        for excluded in ChangeDetector.EXCLUDED_PATHS:
            if excluded in path:
                return None

        absolute_path = path if path.startswith("/") else os.path.join(pai_dir, path)
        if not absolute_path.startswith(pai_dir):
            return None

        if "skills/" in path:
            skill_match = re.search(r"skills/(_[^/]+)", path)
            if skill_match:
                return None
            if "/workflows/" in path:
                return "workflow"
            if re.search(r"pai/(?:PAISYSTEM|THEHOOKSYSTEM|THEDELEGATION|MEMORYSYSTEM|AISTEERINGRULES)", path):
                return "core-system"
            return "skill"

        if "hooks/" in path:
            return "hook"
        if "memory/PAISYSTEMUPDATES/" in path:
            return "documentation"
        if "memory/" in path:
            return "memory-system"
        if path.endswith("settings.json"):
            return "config"
        if path.endswith(".md") and "WORK/" not in path:
            return "documentation"

        return None

    # ── Significance Detection ────────────────────────────────────────

    @staticmethod
    def is_significant_change(changes: List[FileChange]) -> bool:
        """Determine if changes are significant enough to warrant background integrity check."""
        system_changes = [c for c in changes if c.category is not None]
        if not system_changes:
            return False

        if any(c.isPhilosophical or c.isStructural for c in system_changes):
            return True

        categories = set(c.category for c in system_changes)
        if len(categories) >= 1 and len(system_changes) >= 2:
            return True

        important_categories = {"skill", "hook", "core-system", "workflow"}
        if any(c.category in important_categories for c in system_changes):
            return True

        return False

    @staticmethod
    def should_document_changes(changes: List[FileChange]) -> bool:
        """Check if changes warrant documentation."""
        system_changes = [c for c in changes if c.category is not None]
        if not system_changes:
            return False

        if any(c.isPhilosophical or c.isStructural for c in system_changes):
            return True

        important_categories = {"skill", "hook", "workflow", "core-system", "config"}
        if any(c.category in important_categories for c in system_changes):
            return True

        if len(system_changes) >= 2:
            return True

        new_files = [c for c in system_changes if c.tool == "Write"]
        if new_files:
            return True

        if any("/tools/" in c.path and c.path.endswith(".py") for c in system_changes):
            return True

        return False

    # ── Throttling ────────────────────────────────────────────────────

    @staticmethod
    def read_integrity_state() -> Optional[IntegrityState]:
        """Read the current integrity state."""
        state_file = ChangeDetector._state_file()
        try:
            if not os.path.exists(state_file):
                return None
            content = Path(state_file).read_text()
            data = json.loads(content)
            return IntegrityState(
                last_run=data.get("last_run", ""),
                last_changes_hash=data.get("last_changes_hash", ""),
                cooldown_until=data.get("cooldown_until"),
            )
        except Exception:
            return None

    @staticmethod
    def is_in_cooldown() -> bool:
        """Check if we're within the cooldown period."""
        state = ChangeDetector.read_integrity_state()
        if not state or not state.cooldown_until:
            return False
        try:
            cooldown_until = datetime.fromisoformat(state.cooldown_until.replace("Z", "+00:00"))
            return datetime.now(cooldown_until.tzinfo) < cooldown_until
        except Exception:
            return False

    @staticmethod
    def hash_changes(changes: List[FileChange]) -> str:
        """Generate a hash of changes for deduplication."""
        sorted_items = sorted(f"{c.tool}:{c.path}" for c in changes)
        joined = "|".join(sorted_items)

        h = 0
        for char in joined:
            h = ((h << 5) - h) + ord(char)
            h &= 0xFFFFFFFF
        if h > 0x7FFFFFFF:
            h -= 0x100000000
        return hex(h)

    @staticmethod
    def is_duplicate_run(changes: List[FileChange]) -> bool:
        """Check if changes are duplicates of the last run."""
        state = ChangeDetector.read_integrity_state()
        if not state or not state.last_changes_hash:
            return False
        return ChangeDetector.hash_changes(changes) == state.last_changes_hash

    @staticmethod
    def get_cooldown_end_time() -> str:
        """Get the cooldown end time."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(minutes=ChangeDetector.COOLDOWN_MINUTES)
        return end.isoformat().replace("+00:00", "Z")

    # ── Significance and Change Type ──────────────────────────────────

    @staticmethod
    def determine_significance(changes: List[FileChange]) -> SignificanceLabel:
        """Determine the significance label based on change characteristics."""
        count = len(changes)
        has_structural = any(c.isStructural for c in changes)
        has_philosophical = any(c.isPhilosophical for c in changes)
        has_new_files = any(c.tool == "Write" for c in changes)

        categories = set(c.category for c in changes if c.category)
        has_core_system = any(c.category == "core-system" for c in changes)
        has_hooks = any(c.category == "hook" for c in changes)
        has_skills = any(c.category == "skill" for c in changes)

        if has_structural and has_philosophical and count >= 5:
            return "critical"
        if has_new_files and (has_structural or has_philosophical):
            return "major"
        if has_core_system or len(categories) >= 3:
            return "major"
        if has_hooks and count >= 3:
            return "major"
        if count >= 3 or len(categories) >= 2:
            return "moderate"
        if has_skills and count >= 2:
            return "moderate"
        if count == 1 and not has_structural and not has_philosophical:
            return "minor"
        if count == 1 and changes[0].category == "documentation":
            return "trivial"

        return "minor"

    @staticmethod
    def infer_change_type(changes: List[FileChange]) -> ChangeType:
        """Determine the change type based on affected files."""
        categories = [c.category for c in changes if c.category]
        unique_categories = set(categories)

        if len(unique_categories) >= 3:
            return "multi_area"

        if len(unique_categories) == 1:
            cat = list(unique_categories)[0]
            mapping = {
                "hook": "hook_update",
                "workflow": "workflow_update",
                "config": "config_update",
                "core-system": "structure_change",
                "documentation": "doc_update",
            }
            if cat == "skill":
                return "structure_change" if any(c.isStructural for c in changes) else "skill_update"
            return mapping.get(cat, "skill_update")  # type: ignore

        if "hook" in unique_categories:
            return "hook_update"
        if "skill" in unique_categories:
            return "skill_update"
        if "workflow" in unique_categories:
            return "workflow_update"
        if "config" in unique_categories:
            return "config_update"

        return "multi_area"

    @staticmethod
    def generate_descriptive_title(changes: List[FileChange]) -> str:
        """Generate a descriptive 4-8 word title based on the changes."""
        paths = [c.path for c in changes]

        skill_names: Set[str] = set()
        for p in paths:
            match = re.search(r"skills/([^/]+)/", p)
            if match and match.group(1) != "PAI":
                skill_names.add(match.group(1))

        has_skill_md = any(p.endswith("SKILL.md") for p in paths)
        has_workflows = any("/workflows/" in p for p in paths)
        has_tools = any("/tools/" in p and p.endswith(".py") for p in paths)
        has_hooks = any("hooks/" in p for p in paths)
        has_config = any(p.endswith("settings.json") for p in paths)
        has_core_system = any(
            re.search(r"pai/(?:PAISYSTEM|THEHOOKSYSTEM|THEDELEGATION|MEMORYSYSTEM|AISTEERINGRULES)", p)
            for p in paths
        )
        has_core_user = any("pai/user/" in p for p in paths)

        title = ""

        if len(skill_names) == 1:
            skill = list(skill_names)[0]
            if has_skill_md:
                title = f"{skill} Skill Definition Update"
            elif has_workflows:
                wf_names = [
                    os.path.splitext(os.path.basename(p))[0]
                    for p in paths if "/workflows/" in p
                ]
                if len(wf_names) == 1:
                    title = f"{skill} {wf_names[0]} Workflow Update"
                else:
                    title = f"{skill} Workflows Updated"
            elif has_tools:
                tool_names = [
                    os.path.splitext(os.path.basename(p))[0]
                    for p in paths if "/tools/" in p
                ]
                if len(tool_names) == 1:
                    title = f"{skill} {tool_names[0]} Tool Update"
                else:
                    title = f"{skill} Tools Updated"
            else:
                title = f"{skill} Skill Files Updated"
        elif 1 < len(skill_names) <= 3:
            skills = " and ".join(list(skill_names)[:3])
            title = f"{skills} Skills Updated"
        elif has_hooks:
            hook_names = [
                os.path.splitext(os.path.basename(p))[0].replace(".hook", "")
                for p in paths if "hooks/" in p
            ]
            if len(hook_names) == 1:
                title = f"{hook_names[0]} Hook Updated"
            elif len(hook_names) <= 3:
                title = f"{', '.join(hook_names[:3])} Hooks Updated"
            else:
                title = "Hook System Updates"
        elif has_config:
            title = "System Configuration Updated"
        elif has_core_system:
            doc_names = [
                os.path.splitext(os.path.basename(p))[0]
                for p in paths
                if re.search(r"pai/(?:PAISYSTEM|THEHOOKSYSTEM|THEDELEGATION|MEMORYSYSTEM|AISTEERINGRULES)", p)
            ]
            if len(doc_names) == 1:
                title = f"{doc_names[0]} Documentation Updated"
            else:
                title = "PAI System Documentation Updated"
        elif has_core_user:
            doc_names = [
                os.path.splitext(os.path.basename(p))[0]
                for p in paths if "pai/user/" in p
            ]
            if len(doc_names) == 1:
                title = f"{doc_names[0]} User Config Updated"
            else:
                title = "User Configuration Updated"
        else:
            cats = set(c.category for c in changes if c.category)
            if len(cats) == 1:
                cat = list(cats)[0]
                title = f"{(cat or 'System').capitalize()} Updates Applied"
            else:
                title = "Multi-Area System Updates Applied"

        words = title.split()
        if len(words) < 4:
            title = f"PAI {title}"
        elif len(words) > 8:
            title = " ".join(words[:8])

        return title
