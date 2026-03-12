#!/usr/bin/env python3
"""
SessionEnd: Count skills, hooks, workflows and update settings.json counts.
"""
import json
import sys
from pathlib import Path

from paipy import pai_dir, memory, settings_path, load_settings, now_iso


def count_files(directory: Path, pattern: str) -> int:
    if not directory.exists():
        return 0
    return len(list(directory.rglob(pattern)))


def main():
    base = pai_dir()
    counts = {
        "skills": count_files(base / "skills", "*.md"),
        "hooks": count_files(base / "hooks", "*.py") + count_files(base / "hooks" / "py", "*.py"),
        "workflows": count_files(base / "skills", "*.md"),  # same as skills for now
        "signals": count_files(memory("LEARNING") / "SIGNALS", "*.jsonl"),
        "updatedAt": now_iso(),
    }

    settings_file = settings_path()
    if not settings_file.exists():
        return

    try:
        settings = load_settings()
        settings["counts"] = counts
        settings_file.write_text(json.dumps(settings, indent=2))
    except Exception as e:
        print(f"update_counts: failed to write settings: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
