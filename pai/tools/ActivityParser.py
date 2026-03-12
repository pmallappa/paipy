#!/usr/bin/env python3
"""
ActivityParser - Parse session activity for PAI repo update documentation

Commands:
  --today              Parse all today's activity
  --session <id>       Parse specific session only
  --generate           Generate memory/PAISYSTEMUPDATES/ file (outputs path)

Examples:
  python ActivityParser.py --today
  python ActivityParser.py --today --generate
  python ActivityParser.py --session abc-123
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

# ============================================================================
# Configuration
# ============================================================================

HOME = os.environ.get("HOME", str(Path.home()))
CLAUDE_DIR = os.path.join(HOME, ".claude")
MEMORY_DIR = os.path.join(CLAUDE_DIR, "MEMORY")
USERNAME = os.environ.get("USER", os.getlogin() if hasattr(os, "getlogin") else "user")
PROJECTS_DIR = os.path.join(CLAUDE_DIR, "projects", f"-Users-{USERNAME}--claude")
SYSTEM_UPDATES_DIR = os.path.join(MEMORY_DIR, "PAISYSTEMUPDATES")

# ============================================================================
# Types
# ============================================================================


@dataclass
class FileChange:
    file: str
    action: str  # "created" | "modified"
    relative_path: str


@dataclass
class ParsedActivity:
    date: str
    session_id: Optional[str]
    categories: dict[str, list[FileChange]]
    summary: str
    files_modified: list[str]
    files_created: list[str]
    skills_affected: list[str]


# ============================================================================
# Category Detection
# ============================================================================

SKIP_PATTERNS = [
    re.compile(r"memory/PAISYSTEMUPDATES/"),
    re.compile(r"memory/"),
    re.compile(r"WORK/.*/scratch/"),
    re.compile(r"\.quote-cache$"),
    re.compile(r"history\.jsonl$"),
    re.compile(r"cache/"),
    re.compile(r"plans/", re.IGNORECASE),
]

CATEGORY_PATTERNS = {
    "skills": re.compile(r"skills/[^/]+/(SKILL\.md|Workflows/|Tools/|Data/)"),
    "workflows": re.compile(r"Workflows/.*\.md$"),
    "tools": re.compile(r"skills/[^/]+/tools/.*\.ts$"),
    "hooks": re.compile(r"hooks/.*\.ts$"),
    "architecture": re.compile(r"(ARCHITECTURE|PAISYSTEMARCHITECTURE|SKILLSYSTEM)\.md$", re.IGNORECASE),
    "documentation": re.compile(r"\.(md|txt)$"),
}


def should_skip(file_path: str) -> bool:
    return any(pattern.search(file_path) for pattern in SKIP_PATTERNS)


def categorize_file(file_path: str) -> Optional[str]:
    if should_skip(file_path):
        return None
    if "/.claude/" not in file_path:
        return None

    for category, pattern in CATEGORY_PATTERNS.items():
        if pattern.search(file_path):
            return category

    return "other"


def extract_skill_name(file_path: str) -> Optional[str]:
    match = re.search(r"skills/([^/]+)/", file_path)
    return match.group(1) if match else None


def get_relative_path(file_path: str) -> str:
    claude_index = file_path.find("/.claude/")
    if claude_index == -1:
        return file_path
    return file_path[claude_index + 9:]


# ============================================================================
# Event Parsing
# ============================================================================


def get_today_session_files() -> list[str]:
    if not os.path.exists(PROJECTS_DIR):
        return []

    now = time.time()
    one_day_ago = now - 24 * 60 * 60

    files_info = []
    for f in os.listdir(PROJECTS_DIR):
        if not f.endswith(".jsonl"):
            continue
        full_path = os.path.join(PROJECTS_DIR, f)
        mtime = os.path.getmtime(full_path)
        if mtime > one_day_ago:
            files_info.append((full_path, mtime))

    files_info.sort(key=lambda x: x[1], reverse=True)
    return [f[0] for f in files_info]


def empty_activity(date: str, session_id: Optional[str]) -> ParsedActivity:
    return ParsedActivity(
        date=date,
        session_id=session_id,
        categories={
            "skills": [], "workflows": [], "tools": [],
            "hooks": [], "architecture": [], "documentation": [], "other": [],
        },
        summary="no changes detected",
        files_modified=[],
        files_created=[],
        skills_affected=[],
    )


def parse_events(session_filter: Optional[str] = None) -> ParsedActivity:
    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    session_files = get_today_session_files()
    if not session_files:
        print(f"No session files found for today in: {PROJECTS_DIR}", file=sys.stderr)
        return empty_activity(date_str, session_filter)

    entries: list[dict[str, Any]] = []

    for session_file in session_files:
        if session_filter and session_filter not in session_file:
            continue

        try:
            content = Path(session_file).read_text()
        except OSError:
            continue

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                entries.append(entry)
            except json.JSONDecodeError:
                pass

    files_modified: set[str] = set()
    files_created: set[str] = set()

    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message", {})
        content_items = message.get("content", [])
        if not isinstance(content_items, list):
            continue

        for item in content_items:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            inp = item.get("input", {})
            file_path = inp.get("file_path", "")

            if item.get("name") == "Write" and file_path and "/.claude/" in file_path:
                files_created.add(file_path)
            elif item.get("name") == "Edit" and file_path and "/.claude/" in file_path:
                files_modified.add(file_path)

    # Remove from modified if also in created
    for f in files_created:
        files_modified.discard(f)

    categories: dict[str, list[FileChange]] = {
        "skills": [], "workflows": [], "tools": [],
        "hooks": [], "architecture": [], "documentation": [], "other": [],
    }
    skills_affected: set[str] = set()

    def process_file(file: str, action: str) -> None:
        category = categorize_file(file)
        if not category:
            return
        change = FileChange(file=file, action=action, relative_path=get_relative_path(file))
        categories[category].append(change)
        skill = extract_skill_name(file)
        if skill:
            skills_affected.add(skill)

    for f in files_created:
        process_file(f, "created")
    for f in files_modified:
        process_file(f, "modified")

    summary_parts: list[str] = []
    if skills_affected:
        summary_parts.append(f"{len(skills_affected)} skill(s) affected")
    if categories["tools"]:
        summary_parts.append(f"{len(categories['tools'])} tool(s)")
    if categories["hooks"]:
        summary_parts.append(f"{len(categories['hooks'])} hook(s)")
    if categories["workflows"]:
        summary_parts.append(f"{len(categories['workflows'])} workflow(s)")
    if categories["architecture"]:
        summary_parts.append("architecture changes")

    return ParsedActivity(
        date=date_str,
        session_id=session_filter,
        categories=categories,
        summary=", ".join(summary_parts) or "documentation updates",
        files_modified=list(files_modified),
        files_created=list(files_created),
        skills_affected=list(skills_affected),
    )


# ============================================================================
# Update File Generation
# ============================================================================

SIGNIFICANCE_LABELS = ("trivial", "minor", "moderate", "major", "critical")
CHANGE_TYPES = (
    "skill_update", "structure_change", "doc_update", "hook_update",
    "workflow_update", "config_update", "tool_update", "multi_area",
)


def determine_change_type(activity: ParsedActivity) -> str:
    cats = activity.categories
    total_categories = sum(
        1 for key, items in cats.items() if key != "other" and items
    )
    if total_categories >= 3:
        return "multi_area"
    if cats["hooks"]:
        return "hook_update"
    if cats["tools"]:
        return "tool_update"
    if cats["workflows"]:
        return "workflow_update"
    if cats["architecture"]:
        return "structure_change"
    if cats["skills"]:
        return "skill_update"
    return "doc_update"


def determine_significance(activity: ParsedActivity) -> str:
    cats = activity.categories
    total_files = len(activity.files_created) + len(activity.files_modified)
    has_architecture = bool(cats["architecture"])
    has_new_skill = any(c.action == "created" and c.file.endswith("SKILL.md") for c in cats["skills"])
    has_new_tool = any(c.action == "created" for c in cats["tools"])
    has_new_workflow = any(c.action == "created" for c in cats["workflows"])

    if has_architecture and total_files >= 10:
        return "critical"
    if has_new_skill or has_architecture:
        return "major"
    if (has_new_tool or has_new_workflow) and total_files >= 5:
        return "major"
    if has_new_tool or has_new_workflow or total_files >= 5 or cats["hooks"]:
        return "moderate"
    if total_files >= 2:
        return "minor"
    return "trivial"


def generate_title(activity: ParsedActivity) -> str:
    cats = activity.categories
    skills = activity.skills_affected

    def extract_name(file_path: str) -> str:
        base = os.path.splitext(os.path.basename(file_path))[0]
        return re.sub(r"[-_]", " ", base).title()

    def plural(count: int, word: str) -> str:
        return word if count == 1 else f"{word}s"

    if any(c.action == "created" for c in cats["tools"]):
        new_tool = next(c for c in cats["tools"] if c.action == "created")
        name = extract_name(new_tool.file)
        if len(skills) == 1:
            return f"Added {name} Tool to {skills[0]} Skill"
        return f"Created {name} Tool for System"

    if any(c.action == "created" for c in cats["workflows"]):
        new_wf = next(c for c in cats["workflows"] if c.action == "created")
        name = extract_name(new_wf.file)
        if len(skills) == 1:
            return f"Added {name} Workflow to {skills[0]}"
        return f"Created {name} Workflow"

    if cats["hooks"]:
        hook_names = [extract_name(h.file) for h in cats["hooks"]][:2]
        if len(hook_names) == 1:
            return f"Updated {hook_names[0]} Hook Handler"
        return f"Updated {hook_names[0]} and {len(hook_names) - 1} Other {plural(len(hook_names) - 1, 'Hook')}"

    if len(skills) == 1:
        skill = skills[0]
        if cats["workflows"] and cats["tools"]:
            return f"Enhanced {skill} Workflows and Tools"
        if cats["workflows"]:
            return f"Updated {skill} Workflow Configuration"
        if cats["tools"]:
            return f"Modified {skill} Tool Implementation"
        if any(c.file.endswith("SKILL.md") for c in cats["skills"]):
            return f"Updated {skill} Skill Documentation"
        return f"Updated {skill} Skill Files"

    if len(skills) > 1:
        top_two = skills[:2]
        if len(skills) == 2:
            return f"Updated {top_two[0]} and {top_two[1]} Skills"
        return f"Updated {top_two[0]} and {len(skills) - 1} Other Skills"

    if cats["architecture"]:
        arch_file = extract_name(cats["architecture"][0].file)
        return f"Modified {arch_file} Architecture Document"

    if cats["documentation"]:
        doc_count = len(cats["documentation"])
        if doc_count == 1:
            doc_name = extract_name(cats["documentation"][0].file)
            return f"Updated {doc_name} Documentation"
        return f"Updated {doc_count} Documentation {plural(doc_count, 'File')}"

    return f"System Updates for {activity.date}"


def to_kebab_case(s: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return result.strip("-")


def get_significance_badge(significance: str) -> str:
    badges = {
        "critical": "Red Critical",
        "major": "Orange Major",
        "moderate": "Yellow Moderate",
        "minor": "Green Minor",
        "trivial": "White Trivial",
    }
    return badges.get(significance, significance)


def format_change_type(change_type: str) -> str:
    labels = {
        "skill_update": "Skill Update",
        "structure_change": "Structure Change",
        "doc_update": "Documentation Update",
        "hook_update": "Hook Update",
        "workflow_update": "Workflow Update",
        "config_update": "Config Update",
        "tool_update": "Tool Update",
        "multi_area": "Multi-Area",
    }
    return labels.get(change_type, change_type)


def generate_purpose(activity: ParsedActivity) -> str:
    cats = activity.categories
    if any(c.action == "created" for c in cats["tools"]):
        return "Add new tooling capability to the system"
    if any(c.action == "created" for c in cats["workflows"]):
        return "Introduce new workflow for improved task execution"
    if cats["hooks"]:
        return "Update hook system for better lifecycle management"
    if activity.skills_affected:
        names = " and ".join(activity.skills_affected[:2])
        return f"Improve {names} skill functionality"
    if cats["architecture"]:
        return "Refine system architecture documentation"
    return "Maintain and improve system documentation"


def generate_expected_improvement(activity: ParsedActivity) -> str:
    cats = activity.categories
    if any(c.action == "created" for c in cats["tools"]):
        return "New capabilities available for system tasks"
    if any(c.action == "created" for c in cats["workflows"]):
        return "Streamlined execution of related tasks"
    if cats["hooks"]:
        return "More reliable system event handling"
    if activity.skills_affected:
        return "Enhanced skill behavior and documentation clarity"
    if cats["architecture"]:
        return "Clearer understanding of system design"
    return "Better documentation accuracy"


def generate_update_file(activity: ParsedActivity) -> str:
    title = generate_title(activity)
    significance = determine_significance(activity)
    change_type = determine_change_type(activity)
    purpose = generate_purpose(activity)
    expected_improvement = generate_expected_improvement(activity)

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    update_id = f"{activity.date}-{to_kebab_case(title)}"

    all_files = [
        get_relative_path(f)
        for f in (activity.files_created + activity.files_modified)
        if not should_skip(f)
    ]

    files_yaml = "\n".join(f'  - "{f}"' for f in all_files[:20])

    category_names = {
        "skills": "Skills", "workflows": "Workflows", "tools": "Tools",
        "hooks": "Hooks", "architecture": "Architecture",
        "documentation": "Documentation", "other": "Other",
    }

    changes_section = ""
    for key, display_name in category_names.items():
        items = activity.categories[key]
        if items:
            changes_section += f"### {display_name}\n"
            for item in items:
                changes_section += f"- `{item.relative_path}` - {item.action}\n"
            changes_section += "\n"

    content = f"""---
id: "{update_id}"
timestamp: "{timestamp}"
title: "{title}"
significance: "{significance}"
change_type: "{change_type}"
files_affected:
{files_yaml}
purpose: "{purpose}"
expected_improvement: "{expected_improvement}"
integrity_work:
  references_found: 0
  references_updated: 0
  locations_checked: []
---

# {title}

**Timestamp:** {timestamp}
**Significance:** {get_significance_badge(significance)}
**Change Type:** {format_change_type(change_type)}

---

## Purpose

{purpose}

## Expected Improvement

{expected_improvement}

## Summary

Session activity documentation for {activity.date}.
{activity.summary}.

## Changes Made

{changes_section}## Integrity Check

- **References Found:** 0 files reference the changed paths
- **References Updated:** 0

## Verification

*Auto-generated from session activity.*

---

**Status:** Auto-generated
"""
    return content


def write_update_file(activity: ParsedActivity) -> str:
    title = generate_title(activity)
    slug = to_kebab_case(title)
    year, month = activity.date.split("-")[:2]
    filename = f"{activity.date}_{slug}.md"

    year_month_dir = os.path.join(SYSTEM_UPDATES_DIR, year, month)
    filepath = os.path.join(year_month_dir, filename)

    os.makedirs(year_month_dir, exist_ok=True)

    content = generate_update_file(activity)
    Path(filepath).write_text(content)

    return filepath


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ActivityParser - Parse session activity for PAI repo updates"
    )
    parser.add_argument("--session", type=str, help="Parse specific session")
    parser.add_argument("--today", action="store_true", help="Parse all today's activity")
    parser.add_argument("--generate", action="store_true", help="Generate update file")

    args = parser.parse_args()

    # Default to --today if no option specified
    use_today = args.today or not args.session

    activity = parse_events(args.session)

    if args.generate:
        filepath = write_update_file(activity)
        output = {
            "filepath": filepath,
            "activity": {
                "date": activity.date,
                "session_id": activity.session_id,
                "summary": activity.summary,
                "files_modified": activity.files_modified,
                "files_created": activity.files_created,
                "skills_affected": activity.skills_affected,
            },
        }
        print(json.dumps(output, indent=2))
    else:
        output = {
            "date": activity.date,
            "session_id": activity.session_id,
            "summary": activity.summary,
            "files_modified": activity.files_modified,
            "files_created": activity.files_created,
            "skills_affected": activity.skills_affected,
        }
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
