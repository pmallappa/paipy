#!/usr/bin/env python3
"""
GetCounts.py - Single Source of Truth for PAI System Counts

Provides deterministic, consistent counts for PAI system metrics.

Usage:
  python GetCounts.py           # JSON output
  python GetCounts.py --shell   # Shell-sourceable output
  python GetCounts.py --single skills  # Single value output
"""

import json
import os
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
PAI_DIR = os.environ.get("PAI_DIR", os.path.join(HOME, ".claude"))


def count_files_recursive(directory: str, extension: str | None = None) -> int:
    count = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=False):
                count += count_files_recursive(entry.path, extension)
            elif entry.is_file():
                if extension is None or entry.name.endswith(extension):
                    count += 1
    except (OSError, PermissionError):
        pass
    return count


def count_workflow_files(directory: str) -> int:
    count = 0
    try:
        for entry in os.scandir(directory):
            if entry.is_dir(follow_symlinks=False):
                if entry.name.lower() == "workflows":
                    count += count_files_recursive(entry.path, ".md")
                else:
                    count += count_workflow_files(entry.path)
    except (OSError, PermissionError):
        pass
    return count


def count_skills() -> int:
    count = 0
    skills_dir = os.path.join(PAI_DIR, "skills")
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


def count_hooks() -> int:
    count = 0
    hooks_dir = os.path.join(PAI_DIR, "hooks")
    try:
        for entry in os.scandir(hooks_dir):
            if entry.is_file() and entry.name.endswith(".ts"):
                count += 1
    except (OSError, PermissionError):
        pass
    return count


def count_ratings() -> int:
    ratings_file = os.path.join(PAI_DIR, "memory/learning/SIGNALS/ratings.jsonl")
    try:
        content = Path(ratings_file).read_text()
        return len([line for line in content.splitlines() if line.strip()])
    except (OSError, PermissionError):
        return 0


def count_work_dirs() -> int:
    count = 0
    work_dir = os.path.join(PAI_DIR, "memory/work")
    try:
        for entry in os.scandir(work_dir):
            if entry.is_dir():
                count += 1
    except (OSError, PermissionError):
        pass
    return count


def get_counts() -> dict[str, int]:
    return {
        "skills": count_skills(),
        "workflows": count_workflow_files(os.path.join(PAI_DIR, "skills")),
        "hooks": count_hooks(),
        "signals": count_files_recursive(os.path.join(PAI_DIR, "memory/learning"), ".md"),
        "files": count_files_recursive(os.path.join(PAI_DIR, "pai/user")),
        "work": count_work_dirs(),
        "research": (
            count_files_recursive(os.path.join(PAI_DIR, "memory/RESEARCH"), ".md") +
            count_files_recursive(os.path.join(PAI_DIR, "memory/RESEARCH"), ".json")
        ),
        "ratings": count_ratings(),
    }


def main() -> None:
    args = sys.argv[1:]
    shell_mode = "--shell" in args
    single_key = None

    if "--single" in args:
        idx = args.index("--single")
        if idx + 1 < len(args):
            single_key = args[idx + 1]

    counts = get_counts()

    if single_key and single_key in counts:
        print(counts[single_key])
    elif shell_mode:
        for key, value in counts.items():
            print(f"{key}_count={value}")
    else:
        print(json.dumps(counts))


if __name__ == "__main__":
    main()
