#!/usr/bin/env python3
"""
Session Progress CLI

Manages session continuity files for multi-session work.
Based on Anthropic's claude-progress.txt pattern.

Usage:
  python SessionProgress.py <command> [options]
"""

import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Decision:
    timestamp: str
    decision: str
    rationale: str


@dataclass
class WorkItem:
    timestamp: str
    description: str
    artifacts: list[str] = field(default_factory=list)


@dataclass
class Blocker:
    timestamp: str
    blocker: str
    resolution: Optional[str] = None


@dataclass
class SessionProgressData:
    project: str
    created: str
    updated: str
    status: str  # 'active' | 'completed' | 'blocked'
    objectives: list[str] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)
    work_completed: list[dict] = field(default_factory=list)
    blockers: list[dict] = field(default_factory=list)
    handoff_notes: str = ""
    next_steps: list[str] = field(default_factory=list)


PROGRESS_DIR = Path(os.environ.get("HOME", "")) / ".claude" / "MEMORY" / "STATE" / "progress"


def get_progress_path(project: str) -> Path:
    return PROGRESS_DIR / f"{project}-progress.json"


def load_progress(project: str) -> Optional[dict]:
    path = get_progress_path(project)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def save_progress(progress: dict) -> None:
    progress["updated"] = datetime.now().isoformat()
    PROGRESS_DIR.mkdir(parents=True, exist_ok=True)
    get_progress_path(progress["project"]).write_text(json.dumps(progress, indent=2))


def create_progress(project: str, objectives: list[str]) -> None:
    path = get_progress_path(project)
    if path.exists():
        print(f"Progress file already exists for {project}")
        print(f"Use 'session-progress resume {project}' to continue")
        return

    progress = {
        "project": project,
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "status": "active",
        "objectives": objectives,
        "decisions": [],
        "work_completed": [],
        "blockers": [],
        "handoff_notes": "",
        "next_steps": [],
    }
    save_progress(progress)
    print(f"Created progress file: {path}")
    print(f"Objectives: {', '.join(objectives)}")


def add_decision(project: str, decision: str, rationale: str) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["decisions"].append({
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "rationale": rationale,
    })
    save_progress(progress)
    print(f"Added decision: {decision}")


def add_work(project: str, description: str, artifacts: list[str]) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["work_completed"].append({
        "timestamp": datetime.now().isoformat(),
        "description": description,
        "artifacts": artifacts,
    })
    save_progress(progress)
    print(f"Added work: {description}")


def add_blocker(project: str, blocker: str, resolution: Optional[str] = None) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["blockers"].append({
        "timestamp": datetime.now().isoformat(),
        "blocker": blocker,
        "resolution": resolution,
    })
    progress["status"] = "blocked"
    save_progress(progress)
    print(f"Added blocker: {blocker}")


def set_next_steps(project: str, steps: list[str]) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["next_steps"] = steps
    save_progress(progress)
    print(f"Set {len(steps)} next steps")


def set_handoff(project: str, notes: str) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["handoff_notes"] = notes
    save_progress(progress)
    print("Set handoff notes")


def resume_progress(project: str) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    sep = "=" * 60
    print(f"\n{sep}")
    print(f"SESSION RESUME: {project}")
    print(f"{sep}\n")

    print(f"Status: {progress['status']}")
    print(f"Last Updated: {progress['updated']}\n")

    print("OBJECTIVES:")
    for i, o in enumerate(progress.get("objectives", [])):
        print(f"  {i + 1}. {o}")

    decisions = progress.get("decisions", [])
    if decisions:
        print("\nKEY DECISIONS:")
        for d in decisions[-3:]:
            print(f"  - {d['decision']}")
            print(f"    Rationale: {d['rationale']}")

    work = progress.get("work_completed", [])
    if work:
        print("\nRECENT WORK:")
        for w in work[-5:]:
            print(f"  - {w['description']}")
            if w.get("artifacts"):
                print(f"    Artifacts: {', '.join(w['artifacts'])}")

    blockers = progress.get("blockers", [])
    if blockers:
        unresolved = [b for b in blockers if not b.get("resolution")]
        if unresolved:
            print("\nACTIVE BLOCKERS:")
            for b in unresolved:
                print(f"  - {b['blocker']}")

    if progress.get("handoff_notes"):
        print("\nHANDOFF NOTES:")
        print(f"  {progress['handoff_notes']}")

    next_steps = progress.get("next_steps", [])
    if next_steps:
        print("\nNEXT STEPS:")
        for i, s in enumerate(next_steps):
            print(f"  {i + 1}. {s}")

    print(f"\n{sep}\n")


def list_active() -> None:
    if not PROGRESS_DIR.exists():
        print("No progress files found")
        return

    files = [f for f in PROGRESS_DIR.iterdir() if f.name.endswith("-progress.json")]
    if not files:
        print("No active progress files")
        return

    print("\nActive Progress Files:\n")

    for file in files:
        progress = json.loads(file.read_text())
        status_icons = {"active": "[Active]", "completed": "[Done]", "blocked": "[Blocked]"}
        icon = status_icons.get(progress.get("status", ""), "[?]")

        print(f"{icon} {progress['project']} ({progress.get('status', 'unknown')})")
        print(f"   Updated: {progress.get('updated', 'unknown')[:10]}")
        print(f"   Work items: {len(progress.get('work_completed', []))}")
        next_steps = progress.get("next_steps", [])
        if next_steps:
            print(f"   Next: {next_steps[0]}")
        print()


def complete_progress(project: str) -> None:
    progress = load_progress(project)
    if not progress:
        print(f"No progress file for {project}", file=sys.stderr)
        sys.exit(1)

    progress["status"] = "completed"
    progress["handoff_notes"] = f"Completed at {datetime.now().isoformat()}"
    save_progress(progress)
    print(f"Marked {project} as completed")


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else None

    if command == "create":
        if len(args) < 2:
            print("Usage: session-progress create <project> [objective1] [objective2] ...", file=sys.stderr)
            sys.exit(1)
        create_progress(args[1], args[2:])

    elif command == "decision":
        if len(args) < 3:
            print('Usage: session-progress decision <project> "<decision>" "<rationale>"', file=sys.stderr)
            sys.exit(1)
        add_decision(args[1], args[2], args[3] if len(args) > 3 else "")

    elif command == "work":
        if len(args) < 3:
            print('Usage: session-progress work <project> "<description>" [artifact1] [artifact2] ...', file=sys.stderr)
            sys.exit(1)
        add_work(args[1], args[2], args[3:])

    elif command == "blocker":
        if len(args) < 3:
            print('Usage: session-progress blocker <project> "<blocker>" ["resolution"]', file=sys.stderr)
            sys.exit(1)
        add_blocker(args[1], args[2], args[3] if len(args) > 3 else None)

    elif command == "next":
        if len(args) < 2:
            print("Usage: session-progress next <project> <step1> <step2> ...", file=sys.stderr)
            sys.exit(1)
        set_next_steps(args[1], args[2:])

    elif command == "handoff":
        if len(args) < 3:
            print('Usage: session-progress handoff <project> "<notes>"', file=sys.stderr)
            sys.exit(1)
        set_handoff(args[1], args[2])

    elif command == "resume":
        if len(args) < 2:
            print("Usage: session-progress resume <project>", file=sys.stderr)
            sys.exit(1)
        resume_progress(args[1])

    elif command == "list":
        list_active()

    elif command == "complete":
        if len(args) < 2:
            print("Usage: session-progress complete <project>", file=sys.stderr)
            sys.exit(1)
        complete_progress(args[1])

    else:
        print("""
Session Progress CLI - Multi-session continuity management

Commands:
  create <project> [objectives...]    Create new progress file
  decision <project> <decision> <rationale>  Record a decision
  work <project> <description> [artifacts...]  Record completed work
  blocker <project> <blocker> [resolution]    Add blocker
  next <project> <step1> <step2>...   Set next steps
  handoff <project> <notes>           Set handoff notes
  resume <project>                    Display context for resuming
  list                                List all active progress files
  complete <project>                  Mark project as completed

Examples:
  session-progress create auth-feature "Implement user authentication"
  session-progress decision auth-feature "Using JWT" "Simpler than sessions for our API"
  session-progress work auth-feature "Created User model" src/models/user.ts
  session-progress next auth-feature "Write auth tests" "Implement login endpoint"
  session-progress resume auth-feature
""")


if __name__ == "__main__":
    main()
