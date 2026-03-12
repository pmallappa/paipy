#!/usr/bin/env python3
"""
SessionEnd: Extract learnings from completed work sessions.
Writes to memory/learning/{category}/{YYYY-MM}/{datetime}_work_{slug}.md
"""
import json
import re
import sys
from pathlib import Path

from paipy import read_stdin, memory, now_iso, now_filename, now_ym


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40]


def categorize(slug: str, content: str) -> str:
    """SYSTEM = infrastructure changes. ALGORITHM = task execution."""
    infra_keywords = ["hook", "setting", "config", "install", "setup", "deploy", "ci", "pipeline"]
    for kw in infra_keywords:
        if kw in slug or kw in content.lower():
            return "SYSTEM"
    return "ALGORITHM"


def extract_prd_summary(session_id: str) -> dict:
    """Try to find a PRD related to this session."""
    state_dir = memory("STATE")
    work_file = state_dir / "current-work.json"
    if work_file.exists():
        try:
            return json.loads(work_file.read_text())
        except Exception:
            pass
    return {}


def main():
    data = read_stdin()
    session_id = data.get("session_id", "")

    work = extract_prd_summary(session_id)
    if not work:
        return

    task = work.get("task", work.get("slug", "unknown-task"))
    slug = slugify(task)
    category = categorize(slug, task)

    ym = now_ym()
    learn_dir = memory("LEARNING") / category / ym
    learn_dir.mkdir(parents=True, exist_ok=True)

    isc_pass = work.get("isc_pass", 0)
    isc_total = work.get("isc_total", 0)

    content = f"""# Work Completion Learning — {task}

**Session:** {session_id}
**Completed:** {now_iso()}
**Category:** {category}

## Summary
- Task: {task}
- ISC passed: {isc_pass}/{isc_total}
- Status: {work.get("status", "COMPLETED")}

## Context
{json.dumps(work, indent=2)}
"""

    filename = f"{now_filename()}_work_{slug}.md"
    (learn_dir / filename).write_text(content)


if __name__ == "__main__":
    main()
