#!/usr/bin/env python3
"""
PostToolUse (Write, Edit on PRD.md): Sync PRD frontmatter → work.json.
"""
import json
import re
import sys
from pathlib import Path

from paipy import read_stdin, pai_dir, memory, now_iso

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
FIELD_RE = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    return {k: v.strip() for k, v in FIELD_RE.findall(m.group(1))}


def load_work() -> dict:
    p = memory("STATE") / "current-work.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def save_work(work: dict):
    d = memory("STATE")
    d.mkdir(parents=True, exist_ok=True)
    (d / "current-work.json").write_text(json.dumps(work, indent=2))


def main():
    data = read_stdin()
    file_path = data.get("tool_input", {}).get("file_path", "")

    if "PRD" not in Path(file_path).name.upper():
        return

    p = Path(file_path)
    if not p.exists():
        return

    fm = parse_frontmatter(p.read_text())
    if not fm:
        return

    work = load_work()
    work.update({
        "task": fm.get("task", work.get("task", "")),
        "slug": fm.get("slug", work.get("slug", "")),
        "effort": fm.get("effort", work.get("effort", "")),
        "phase": fm.get("phase", work.get("phase", "")),
        "progress": fm.get("progress", work.get("progress", "")),
        "prd_path": str(file_path),
        "synced_at": now_iso(),
    })
    save_work(work)


if __name__ == "__main__":
    main()
