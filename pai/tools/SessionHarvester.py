#!/usr/bin/env python3
"""
SessionHarvester - Extract learnings from Claude Code session transcripts

Harvests insights from ~/.claude/projects/ sessions and writes to LEARNING/

Commands:
  --recent N     Harvest from N most recent sessions (default: 10)
  --all          Harvest from all sessions modified in last 7 days
  --session ID   Harvest from specific session UUID
  --dry-run      Show what would be harvested without writing

Examples:
  python SessionHarvester.py --recent 5
  python SessionHarvester.py --session abc-123
  python SessionHarvester.py --all --dry-run
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# ============================================================================
# Configuration
# ============================================================================

CLAUDE_DIR = Path(os.environ.get("HOME", "")) / ".claude"
CWD_SLUG = str(CLAUDE_DIR).replace("/", "-").replace(".", "-")
PROJECTS_DIR = CLAUDE_DIR / "projects" / CWD_SLUG
LEARNING_DIR = CLAUDE_DIR / "MEMORY" / "LEARNING"

# Patterns indicating learning moments
CORRECTION_PATTERNS = [
    re.compile(r"actually,?\s+", re.IGNORECASE),
    re.compile(r"wait,?\s+", re.IGNORECASE),
    re.compile(r"no,?\s+i meant", re.IGNORECASE),
    re.compile(r"let me clarify", re.IGNORECASE),
    re.compile(r"that's not (quite )?right", re.IGNORECASE),
    re.compile(r"you misunderstood", re.IGNORECASE),
    re.compile(r"i was wrong", re.IGNORECASE),
    re.compile(r"my mistake", re.IGNORECASE),
]

ERROR_PATTERNS = [
    re.compile(r"error:", re.IGNORECASE),
    re.compile(r"failed:", re.IGNORECASE),
    re.compile(r"exception:", re.IGNORECASE),
    re.compile(r"stderr:", re.IGNORECASE),
    re.compile(r"command failed", re.IGNORECASE),
    re.compile(r"permission denied", re.IGNORECASE),
    re.compile(r"not found", re.IGNORECASE),
]

INSIGHT_PATTERNS = [
    re.compile(r"learned that", re.IGNORECASE),
    re.compile(r"realized that", re.IGNORECASE),
    re.compile(r"discovered that", re.IGNORECASE),
    re.compile(r"key insight", re.IGNORECASE),
    re.compile(r"important:", re.IGNORECASE),
    re.compile(r"note to self", re.IGNORECASE),
    re.compile(r"for next time", re.IGNORECASE),
    re.compile(r"lesson:", re.IGNORECASE),
]


# ============================================================================
# Types
# ============================================================================


@dataclass
class HarvestedLearning:
    session_id: str
    timestamp: str
    category: str  # 'SYSTEM' | 'ALGORITHM'
    type: str  # 'correction' | 'error' | 'insight'
    context: str
    content: str
    source: str


# ============================================================================
# Helpers (simplified versions of learning-utils)
# ============================================================================


def get_learning_category(text: str) -> str:
    """Simplified category detection."""
    algorithm_keywords = re.compile(r"algorithm|pipeline|step|phase|mode|format|output", re.IGNORECASE)
    if algorithm_keywords.search(text):
        return "ALGORITHM"
    return "SYSTEM"


def is_learning_capture(text: str) -> bool:
    """Check if text contains a real learning moment."""
    return len(text) > 50 and not text.startswith("{")


# ============================================================================
# Session File Discovery
# ============================================================================


def get_session_files(recent: Optional[int] = None, all_sessions: bool = False, session_id: Optional[str] = None) -> list[Path]:
    if not PROJECTS_DIR.exists():
        print(f"Projects directory not found: {PROJECTS_DIR}", file=sys.stderr)
        return []

    files = []
    for f in PROJECTS_DIR.iterdir():
        if f.suffix == ".jsonl":
            files.append((f, f.stat().st_mtime))
    files.sort(key=lambda x: x[1], reverse=True)

    if session_id:
        match = next((f for f, _ in files if session_id in f.name), None)
        return [match] if match else []

    if all_sessions:
        import time
        seven_days_ago = time.time() - 7 * 24 * 60 * 60
        return [f for f, mtime in files if mtime > seven_days_ago]

    limit = recent or 10
    return [f for f, _ in files[:limit]]


# ============================================================================
# Content Extraction
# ============================================================================


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text" and c.get("text")
        )
    return ""


def matches_patterns(text: str, patterns: list[re.Pattern]) -> tuple[bool, Optional[str]]:
    for pattern in patterns:
        if pattern.search(text):
            return True, pattern.pattern
    return False, None


# ============================================================================
# Learning Extraction
# ============================================================================


def harvest_learnings(session_path: Path) -> list[HarvestedLearning]:
    learnings: list[HarvestedLearning] = []
    session_id = session_path.stem

    content = session_path.read_text()
    previous_context = ""

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            msg_content = entry.get("message", {}).get("content")
            if not msg_content:
                continue

            text_content = extract_text_content(msg_content)
            if not text_content or len(text_content) < 20:
                continue

            timestamp = entry.get("timestamp", datetime.now().isoformat())
            entry_type = entry.get("type", "")

            if entry_type == "user":
                matched, pattern = matches_patterns(text_content, CORRECTION_PATTERNS)
                if matched:
                    learnings.append(HarvestedLearning(
                        session_id=session_id,
                        timestamp=timestamp,
                        category=get_learning_category(text_content),
                        type="correction",
                        context=previous_context[:200],
                        content=text_content[:500],
                        source=pattern or "correction",
                    ))
                previous_context = text_content

            if entry_type == "assistant":
                error_matched, error_pattern = matches_patterns(text_content, ERROR_PATTERNS)
                if error_matched and is_learning_capture(text_content):
                    learnings.append(HarvestedLearning(
                        session_id=session_id,
                        timestamp=timestamp,
                        category=get_learning_category(text_content),
                        type="error",
                        context=previous_context[:200],
                        content=text_content[:500],
                        source=error_pattern or "error",
                    ))

                insight_matched, insight_pattern = matches_patterns(text_content, INSIGHT_PATTERNS)
                if insight_matched:
                    learnings.append(HarvestedLearning(
                        session_id=session_id,
                        timestamp=timestamp,
                        category=get_learning_category(text_content),
                        type="insight",
                        context=previous_context[:200],
                        content=text_content[:500],
                        source=insight_pattern or "insight",
                    ))

                previous_context = text_content
        except (json.JSONDecodeError, KeyError):
            continue

    return learnings


# ============================================================================
# Learning File Generation
# ============================================================================


def get_month_dir(category: str) -> Path:
    now = datetime.now()
    month_dir = LEARNING_DIR / category / f"{now.year}-{now.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)
    return month_dir


def generate_learning_filename(learning: HarvestedLearning) -> str:
    try:
        dt = datetime.fromisoformat(learning.timestamp.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now()
    date_str = dt.strftime("%Y-%m-%d")
    time_str = dt.strftime("%H%M")
    session_short = learning.session_id[:8]
    return f"{date_str}_{time_str}_{learning.type}_{session_short}.md"


def format_learning_file(learning: HarvestedLearning) -> str:
    return f"""# {learning.type.capitalize()} Learning

**Session:** {learning.session_id}
**Timestamp:** {learning.timestamp}
**Category:** {learning.category}
**Source Pattern:** {learning.source}

---

## Context

{learning.context}

## Learning

{learning.content}

---

*Harvested by SessionHarvester from projects/ transcript*
"""


def write_learning(learning: HarvestedLearning) -> str:
    month_dir = get_month_dir(learning.category)
    filename = generate_learning_filename(learning)
    filepath = month_dir / filename

    if filepath.exists():
        return f"{filepath} (skipped - exists)"

    filepath.write_text(format_learning_file(learning))
    return str(filepath)


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="SessionHarvester - Extract learnings from Claude Code sessions")
    parser.add_argument("--recent", type=int, help="Harvest from N most recent sessions (default: 10)")
    parser.add_argument("--all", action="store_true", help="Harvest from all sessions (7 days)")
    parser.add_argument("--session", type=str, help="Harvest from specific session ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    session_files = get_session_files(
        recent=args.recent,
        all_sessions=args.all,
        session_id=args.session,
    )

    if not session_files:
        print("No sessions found to harvest")
        sys.exit(0)

    print(f"Scanning {len(session_files)} session(s)...")

    all_learnings: list[HarvestedLearning] = []

    for session_file in session_files:
        session_name = session_file.stem[:8]
        learnings = harvest_learnings(session_file)
        if learnings:
            print(f"  {session_name}: {len(learnings)} learning(s)")
            all_learnings.extend(learnings)

    if not all_learnings:
        print("No new learnings found")
        sys.exit(0)

    print(f"\nFound {len(all_learnings)} learning(s)")
    print(f"   - Corrections: {sum(1 for l in all_learnings if l.type == 'correction')}")
    print(f"   - Errors: {sum(1 for l in all_learnings if l.type == 'error')}")
    print(f"   - Insights: {sum(1 for l in all_learnings if l.type == 'insight')}")

    if args.dry_run:
        print("\nDRY RUN - Would write:")
        for learning in all_learnings:
            month_dir = get_month_dir(learning.category)
            filename = generate_learning_filename(learning)
            print(f"   {learning.category}/{month_dir.name}/{filename}")
    else:
        print("\nWriting learning files...")
        for learning in all_learnings:
            result = write_learning(learning)
            print(f"   {Path(result).name}")
        print(f"\nHarvested {len(all_learnings)} learning(s) to memory/learning/")


if __name__ == "__main__":
    main()
