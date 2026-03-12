#!/usr/bin/env python3
"""
SessionEnd: Mark active work complete, clear state files.
"""
import json
import sys
from paipy import read_stdin, memory, now_iso


def main():
    data = read_stdin()
    session_id = data.get("session_id", "")

    state_dir = memory("STATE")
    work_file = state_dir / "current-work.json"

    if work_file.exists():
        try:
            work = json.loads(work_file.read_text())
            if work.get("session_id") == session_id:
                work["status"] = "COMPLETED"
                work["completed_at"] = now_iso()
                work_file.write_text(json.dumps(work, indent=2))
        except Exception:
            pass

    # Remove session from names tracking if empty
    names_file = state_dir / "session-names.json"
    if names_file.exists() and session_id:
        try:
            names = json.loads(names_file.read_text())
            # Keep names — they're useful for history; just mark ended
            if session_id in names:
                names[session_id]["ended_at"] = now_iso()
                names_file.write_text(json.dumps(names, indent=2))
        except Exception:
            pass


if __name__ == "__main__":
    main()
