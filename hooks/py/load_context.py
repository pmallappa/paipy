#!/usr/bin/env python3
"""
SessionStart: Inject dynamic context into the session —
relationship notes, recent learnings, active work summary.
"""
import json
import os
import sys
from datetime import datetime, timezone

# ── paipy import check ─────────────────────────────────────────────────────
try:
    from paipy import read_stdin, inject, pai_dir, memory, load_settings, now_ym, now_date, is_subagent
except ImportError:
    _pai = os.environ.get("PAI_DIR", "?")
    _pp = os.environ.get("PYTHONPATH", "?")
    print(
        f"[PAI] FATAL: cannot import paipy. "
        f"PYTHONPATH={_pp} PAI_DIR={_pai} — "
        f"check settings.json env.PYTHONPATH includes ${{PAI_DIR}}",
        file=sys.stderr,
    )
    sys.exit(1)

MAX_RELATIONSHIP_LINES = 20
MAX_LEARNING_ENTRIES = 5
MAX_WORK_ENTRIES = 3


def load_relationship_notes() -> str:
    today = now_date()
    ym = now_ym()
    p = memory("RELATIONSHIP") / ym / f"{today}.md"
    if p.exists():
        lines = p.read_text().splitlines()
        return "\n".join(lines[:MAX_RELATIONSHIP_LINES])
    return ""


def load_recent_learnings() -> str:
    signals = memory("LEARNING") / "SIGNALS" / "ratings.jsonl"
    if not signals.exists():
        return ""
    entries = []
    try:
        for line in signals.read_text().splitlines()[-20:]:
            e = json.loads(line)
            if e.get("rating", 10) <= 4:
                entries.append(f"- Rating {e['rating']}/10: {e.get('prompt_snippet', '')[:80]}")
    except Exception:
        pass
    if not entries:
        return ""
    return "Recent low ratings:\n" + "\n".join(entries[-MAX_LEARNING_ENTRIES:])


def load_startup_files() -> list[str]:
    settings = load_settings()
    files = settings.get("loadAtStartup", {}).get("files", [])
    sections = []
    for rel_path in files:
        p = pai_dir() / rel_path
        if p.exists():
            content = p.read_text()
            sections.append(f"# {p.name}\n{content}")
    return sections


def main():
    # Don't inject context in subagents
    if is_subagent():
        return

    parts = []

    # Startup files
    for section in load_startup_files():
        parts.append(section)

    # Relationship context
    rel = load_relationship_notes()
    if rel:
        parts.append(f"## Recent relationship context\n{rel}")

    # Learning signals
    learnings = load_recent_learnings()
    if learnings:
        parts.append(f"## Recent feedback signals\n{learnings}")

    if parts:
        content = "\n\n---\n\n".join(parts)
        inject(content)


if __name__ == "__main__":
    main()
