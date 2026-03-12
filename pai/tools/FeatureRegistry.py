#!/usr/bin/env python3
"""
Feature Registry CLI

JSON-based feature tracking for complex multi-feature tasks.

Usage:
  python FeatureRegistry.py <command> [options]

Commands:
  init <project>              Initialize feature registry for project
  add <project> <feature>     Add feature to registry
  update <project> <id>       Update feature status
  list <project>              List all features
  verify <project>            Run verification for all features
  next <project>              Show next priority feature
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

REGISTRY_DIR = os.path.join(
    os.environ.get("HOME", str(Path.home())), ".claude", "MEMORY", "progress"
)


def get_registry_path(project: str) -> str:
    return os.path.join(REGISTRY_DIR, f"{project}-features.json")


def load_registry(project: str) -> Optional[dict]:
    path = get_registry_path(project)
    if not os.path.exists(path):
        return None
    return json.loads(Path(path).read_text())


def calculate_summary(features: list[dict]) -> dict:
    return {
        "total": len(features),
        "passing": sum(1 for f in features if f["status"] == "passing"),
        "failing": sum(1 for f in features if f["status"] == "failing"),
        "pending": sum(1 for f in features if f["status"] == "pending"),
        "blocked": sum(1 for f in features if f["status"] == "blocked"),
    }


def save_registry(registry: dict) -> None:
    path = get_registry_path(registry["project"])
    registry["updated"] = datetime.utcnow().isoformat() + "Z"
    registry["completion_summary"] = calculate_summary(registry["features"])
    Path(path).write_text(json.dumps(registry, indent=2))


def generate_id(features: list[dict]) -> str:
    max_id = 0
    for f in features:
        try:
            num = int(f["id"].replace("feat-", ""))
            if num > max_id:
                max_id = num
        except ValueError:
            pass
    return f"feat-{max_id + 1}"


def init_registry(project: str) -> None:
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    path = get_registry_path(project)
    if os.path.exists(path):
        print(f"Registry already exists for {project}")
        return
    registry = {
        "project": project,
        "created": datetime.utcnow().isoformat() + "Z",
        "updated": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "features": [],
        "completion_summary": {"total": 0, "passing": 0, "failing": 0, "pending": 0, "blocked": 0},
    }
    save_registry(registry)
    print(f"Initialized feature registry: {path}")


def add_feature(project: str, name: str, description: str = "",
                priority: str = "P2", criteria: list[str] | None = None,
                steps: list[str] | None = None) -> None:
    registry = load_registry(project)
    if not registry:
        print(f"No registry found for {project}. Run: python FeatureRegistry.py init {project}", file=sys.stderr)
        sys.exit(1)

    feature = {
        "id": generate_id(registry["features"]),
        "name": name,
        "description": description,
        "priority": priority,
        "status": "pending",
        "test_steps": [{"step": s, "status": "pending"} for s in (steps or [])],
        "acceptance_criteria": criteria or [],
        "blocked_by": [],
        "started_at": None,
        "completed_at": None,
        "notes": [],
    }
    registry["features"].append(feature)
    save_registry(registry)
    print(f"Added feature {feature['id']}: {name}")


def update_feature(project: str, feature_id: str,
                   status: Optional[str] = None, note: Optional[str] = None) -> None:
    registry = load_registry(project)
    if not registry:
        print(f"No registry found for {project}", file=sys.stderr)
        sys.exit(1)

    feature = next((f for f in registry["features"] if f["id"] == feature_id), None)
    if not feature:
        print(f"Feature {feature_id} not found", file=sys.stderr)
        sys.exit(1)

    if status:
        feature["status"] = status
        if status == "in_progress" and not feature.get("started_at"):
            feature["started_at"] = datetime.utcnow().isoformat() + "Z"
        if status == "passing":
            feature["completed_at"] = datetime.utcnow().isoformat() + "Z"

    if note:
        feature["notes"].append(f"[{datetime.utcnow().isoformat()}Z] {note}")

    save_registry(registry)
    print(f"Updated {feature_id}: status={feature['status']}")


def list_features(project: str) -> None:
    registry = load_registry(project)
    if not registry:
        print(f"No registry found for {project}", file=sys.stderr)
        sys.exit(1)

    print(f"\nFeature Registry: {project}")
    print(f"Updated: {registry['updated']}")
    print("-" * 37)

    summary = registry["completion_summary"]
    print(f"Progress: {summary['passing']}/{summary['total']} passing")
    print(f"  Pending: {summary['pending']} | Failing: {summary['failing']} | Blocked: {summary['blocked']}")
    print("-" * 37 + "\n")

    by_priority: dict[str, list] = {"P1": [], "P2": [], "P3": []}
    for f in registry["features"]:
        by_priority.setdefault(f["priority"], []).append(f)

    status_icons = {
        "pending": "\u25cb", "in_progress": "\u25d0",
        "passing": "\u2713", "failing": "\u2717", "blocked": "\u2298",
    }

    for priority, features in by_priority.items():
        if not features:
            continue
        print(f"{priority} Features:")
        for f in features:
            icon = status_icons.get(f["status"], "?")
            print(f"  {icon} [{f['id']}] {f['name']} ({f['status']})")
        print()


def verify_features(project: str) -> None:
    registry = load_registry(project)
    if not registry:
        print(f"No registry found for {project}", file=sys.stderr)
        sys.exit(1)

    print(f"\nVerification Report: {project}")
    print("=" * 39 + "\n")

    all_passing = True
    for feature in registry["features"]:
        icon = "PASS" if feature["status"] == "passing" else "FAIL"
        print(f"{icon} {feature['id']}: {feature['name']}")
        if feature["status"] != "passing":
            all_passing = False
            print(f"   Status: {feature['status']}")
        for step in feature.get("test_steps", []):
            si = {"passing": "\u2713", "failing": "\u2717"}.get(step["status"], "\u25cb")
            print(f"   {si} {step['step']}")
        print()

    print("=" * 39)
    if all_passing:
        print("ALL FEATURES PASSING - Ready for completion")
    else:
        print("INCOMPLETE - Some features not passing")


def next_feature(project: str) -> None:
    registry = load_registry(project)
    if not registry:
        print(f"No registry found for {project}", file=sys.stderr)
        sys.exit(1)

    in_progress = next((f for f in registry["features"] if f["status"] == "in_progress"), None)
    if in_progress:
        print(f"\nCurrent: [{in_progress['id']}] {in_progress['name']}")
        print(f"Status: {in_progress['status']}")
        print(f"Started: {in_progress['started_at']}")
        return

    for priority in ["P1", "P2", "P3"]:
        nxt = next((f for f in registry["features"]
                     if f["priority"] == priority and f["status"] == "pending"), None)
        if nxt:
            print(f"\nNext: [{nxt['id']}] {nxt['name']} ({nxt['priority']})")
            print(f"Description: {nxt['description'] or 'None'}")
            print(f"\nTo start: python FeatureRegistry.py update {project} {nxt['id']} in_progress")
            return

    print("\nNo pending features. All features processed!")


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else None

    if command == "init":
        if len(args) < 2:
            print("Usage: python FeatureRegistry.py init <project>", file=sys.stderr)
            sys.exit(1)
        init_registry(args[1])
    elif command == "add":
        if len(args) < 3:
            print("Usage: python FeatureRegistry.py add <project> <name> [--description ...] [--priority P1|P2|P3]", file=sys.stderr)
            sys.exit(1)
        desc = args[args.index("--description") + 1] if "--description" in args else ""
        prio = args[args.index("--priority") + 1] if "--priority" in args else "P2"
        add_feature(args[1], args[2], desc, prio)
    elif command == "update":
        if len(args) < 3:
            print("Usage: python FeatureRegistry.py update <project> <id> [status] [--note ...]", file=sys.stderr)
            sys.exit(1)
        valid = ["pending", "in_progress", "passing", "failing", "blocked"]
        status = args[3] if len(args) > 3 and args[3] in valid else None
        note = args[args.index("--note") + 1] if "--note" in args else None
        update_feature(args[1], args[2], status, note)
    elif command == "list":
        if len(args) < 2:
            print("Usage: python FeatureRegistry.py list <project>", file=sys.stderr)
            sys.exit(1)
        list_features(args[1])
    elif command == "verify":
        if len(args) < 2:
            print("Usage: python FeatureRegistry.py verify <project>", file=sys.stderr)
            sys.exit(1)
        verify_features(args[1])
    elif command == "next":
        if len(args) < 2:
            print("Usage: python FeatureRegistry.py next <project>", file=sys.stderr)
            sys.exit(1)
        next_feature(args[1])
    else:
        print("""
Feature Registry CLI - JSON-based feature tracking

Commands:
  init <project>              Initialize feature registry
  add <project> <name>        Add feature (--description, --priority P1|P2|P3)
  update <project> <id>       Update status (pending|in_progress|passing|failing|blocked)
  list <project>              List all features with status
  verify <project>            Run verification report
  next <project>              Show next priority feature
""")


if __name__ == "__main__":
    main()
