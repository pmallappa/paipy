#!/usr/bin/env python3
"""
SessionEnd: Extract relationship notes (preferences, frustrations, milestones)
from the session transcript. Appends to memory/relationship/{YYYY-MM}/{date}.md
"""
import json
import re
import sys
from paipy import read_stdin, memory, now_iso, now_ym, now_date

# Note type prefixes: W=World, B=Biographical, O=Opinion
PATTERNS = [
    (r"\bi (?:prefer|like|love|hate|dislike|always|never)\b.{10,80}", "O"),
    (r"\bplease (?:always|never|don'?t|do|use|avoid)\b.{10,80}", "O"),
    (r"\bthat'?s (?:great|perfect|exactly|wrong|not what|annoying)\b.{0,80}", "O"),
    (r"\bi'?m (?:a |an |working on |building )\w.{10,80}", "B"),
    (r"\bmy (?:project|company|team|system|workflow|preference)\b.{10,80}", "B"),
]


def extract_notes(transcript_path: str) -> list[tuple[str, str]]:
    notes = []
    try:
        for line in Path(transcript_path).read_text().splitlines():
            try:
                entry = json.loads(line)
                if entry.get("role") != "user":
                    continue
                content = entry.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content
                        if isinstance(b, dict) and b.get("type") == "text"
                    )
                for pattern, note_type in PATTERNS:
                    for m in re.finditer(pattern, content, re.IGNORECASE):
                        note = m.group(0).strip().rstrip(".,;")
                        if len(note) > 15:
                            notes.append((note_type, note))
            except Exception:
                continue
    except Exception:
        pass
    return notes


def main():
    data = read_stdin()
    transcript_path = data.get("transcript_path", "")
    if not transcript_path:
        return

    notes = extract_notes(transcript_path)
    if not notes:
        return

    ym = now_ym()
    today = now_date()
    rel_dir = memory("RELATIONSHIP") / ym
    rel_dir.mkdir(parents=True, exist_ok=True)
    rel_file = rel_dir / f"{today}.md"

    lines = [f"\n## {now_iso()}"]
    for note_type, note in notes:
        lines.append(f"- [{note_type}] {note}")

    with open(rel_file, "a") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
