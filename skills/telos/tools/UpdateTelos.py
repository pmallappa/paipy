#!/usr/bin/env python3
"""
update-telos - Update TELOS life context with automatic backups and change tracking.

Usage:
    python UpdateTelos.py <file> "<content>" "<change-description>"
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TELOS_DIR = Path.home() / ".claude" / "context" / "life" / "telos"
BACKUPS_DIR = TELOS_DIR / "backups"
UPDATES_FILE = TELOS_DIR / "updates.md"

VALID_FILES = [
    "BELIEFS.md", "BOOKS.md", "CHALLENGES.md", "FRAMES.md", "GOALS.md",
    "LESSONS.md", "MISSION.md", "MODELS.md", "MOVIES.md", "NARRATIVES.md",
    "PREDICTIONS.md", "PROBLEMS.md", "PROJECTS.md", "STRATEGIES.md",
    "TELOS.md", "TRAUMAS.md", "WISDOM.md", "WRONG.md",
]


def get_timestamp() -> str:
    now = datetime.now()
    return now.strftime("%Y%m%d-%H%M%S")


def get_date_for_log() -> str:
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S PT")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 3:
        print("Usage: python UpdateTelos.py <file> \"<content>\" \"<change-description>\"", file=sys.stderr)
        print(f"\nValid files: {', '.join(VALID_FILES)}", file=sys.stderr)
        sys.exit(1)

    filename, content, change_description = args[0], args[1], args[2]

    if filename not in VALID_FILES:
        print(f"Invalid file: {filename}", file=sys.stderr)
        print(f"Valid files: {', '.join(VALID_FILES)}", file=sys.stderr)
        sys.exit(1)

    target_file = TELOS_DIR / filename
    if not target_file.exists():
        print(f"File does not exist: {target_file}", file=sys.stderr)
        sys.exit(1)

    # Step 1: Backup
    timestamp = get_timestamp()
    backup_filename = filename.replace(".md", f"-{timestamp}.md")
    backup_path = BACKUPS_DIR / backup_filename

    try:
        BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target_file, backup_path)
        print(f"Backup created: {backup_filename}")
    except Exception as e:
        print(f"Failed to create backup: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Update file
    try:
        current = target_file.read_text(encoding="utf-8").rstrip()
        target_file.write_text(current + "\n" + content + "\n", encoding="utf-8")
        print(f"Updated: {filename}")
    except Exception as e:
        print(f"Failed to update file: {e}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Log change
    try:
        log_timestamp = get_date_for_log()
        log_entry = f"""
## {log_timestamp}

- **File Modified**: {filename}
- **Change Type**: Content Addition
- **Description**: {change_description}
- **Backup Location**: `backups/{backup_filename}`

"""
        updates_content = UPDATES_FILE.read_text(encoding="utf-8")
        marker = "## Future Changes"
        idx = updates_content.find(marker)
        if idx != -1:
            before = updates_content[:idx + len(marker)]
            after = updates_content[idx + len(marker):]
            nl = after.find("\n")
            header = after[:nl + 1]
            rest = after[nl + 1:]
            UPDATES_FILE.write_text(before + header + log_entry + rest, encoding="utf-8")
        else:
            UPDATES_FILE.write_text(updates_content.rstrip() + "\n" + log_entry, encoding="utf-8")
        print("Change logged in updates.md")
    except Exception as e:
        print(f"Failed to update updates.md: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\nTELOS update complete!\n   File: {filename}\n   Backup: backups/{backup_filename}\n   Change: {change_description}")


if __name__ == "__main__":
    main()
