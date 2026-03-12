#!/usr/bin/env python3
"""
RelationshipReflect - Periodic reflection on relationship growth

PURPOSE:
Runs daily or on-demand to evolve the relationship files based on
accumulated evidence from sessions.

USAGE:
  python RelationshipReflect.py                    # Full reflection
  python RelationshipReflect.py --opinions-only    # Just update opinion confidence
  python RelationshipReflect.py --milestones-only  # Just check for milestones
  python RelationshipReflect.py --dry-run          # Show what would change

ACTIONS:
1. Scan memory/relationship/ for recent notes
2. Update OPINIONS.md confidence scores based on evidence
3. Check for milestone achievements -> OUR_STORY.md
4. Notify on major changes (>15% confidence shift)
"""

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

PAI_DIR = Path(os.environ.get("PAI_DIR", Path(os.environ.get("HOME", "")) / ".claude"))


@dataclass
class RelationshipNote:
    type: str  # 'W' | 'B' | 'O'
    entity: str
    content: str
    confidence: Optional[float] = None
    date: str = ""


@dataclass
class OpinionEvidence:
    statement: str
    supporting: int = 0
    counter: int = 0
    confirmations: int = 0
    contradictions: int = 0


@dataclass
class ReflectionResult:
    opinions_updated: int = 0
    major_shifts: list[str] = field(default_factory=list)
    milestones_detected: list[str] = field(default_factory=list)
    soul_updates_queued: int = 0


# Milestone definitions
MILESTONES = [
    {
        "id": "first-pushback",
        "description": "First time DA correctly pushed back on user's approach",
        "pattern": re.compile(r"pushed back|disagreed|suggested alternative|recommended against", re.IGNORECASE),
    },
    {
        "id": "genuine-unknown",
        "description": "First genuine 'I don't know' that led to discovery",
        "pattern": re.compile(r"don't know|uncertain|not sure|discovered|found out", re.IGNORECASE),
    },
    {
        "id": "voice-smile",
        "description": "First voice notification that made user smile",
        "pattern": re.compile(r"voice.*(?:worked|success)|notification.*(?:good|great|smile)", re.IGNORECASE),
    },
    {
        "id": "100-sessions",
        "description": "100 sessions working together",
        "pattern": None,
    },
]


def get_iso_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def get_pst_components() -> dict[str, str]:
    now = datetime.now()
    return {
        "year": str(now.year),
        "month": f"{now.month:02d}",
        "day": f"{now.day:02d}",
    }


def parse_relationship_notes(content: str, date: str) -> list[RelationshipNote]:
    notes: list[RelationshipNote] = []
    for line in content.splitlines():
        trimmed = line.strip()
        if not trimmed.startswith("- "):
            continue
        note_content = trimmed[2:]
        match = re.match(r"^([WBO])(?:\(c=([\d.]+)\))?\s+(@\w+):\s*(.+)$", note_content)
        if match:
            notes.append(RelationshipNote(
                type=match.group(1),
                entity=match.group(3),
                content=match.group(4),
                confidence=float(match.group(2)) if match.group(2) else None,
                date=date,
            ))
    return notes


def load_recent_notes(days_back: int = 7) -> list[RelationshipNote]:
    all_notes: list[RelationshipNote] = []
    components = get_pst_components()
    year, month = components["year"], components["month"]

    months = [f"{year}-{month}"]
    if int(month) == 1:
        months.append(f"{int(year) - 1}-12")
    else:
        months.append(f"{year}-{int(month) - 1:02d}")

    for month_str in months:
        month_dir = PAI_DIR / "MEMORY" / "RELATIONSHIP" / month_str
        if not month_dir.exists():
            continue
        try:
            files = sorted(
                [f for f in month_dir.iterdir() if f.suffix == ".md" and f.name != "INDEX.md"],
                reverse=True,
            )[:days_back]
            for file in files:
                content = file.read_text()
                date = file.stem
                notes = parse_relationship_notes(content, date)
                all_notes.extend(notes)
        except Exception:
            pass

    return all_notes


def load_recent_ratings(days_back: int = 7) -> list[dict]:
    ratings_path = PAI_DIR / "MEMORY" / "LEARNING" / "SIGNALS" / "ratings.jsonl"
    if not ratings_path.exists():
        return []

    ratings: list[dict] = []
    cutoff = datetime.now() - timedelta(days=days_back)

    try:
        for line in ratings_path.read_text().strip().splitlines():
            try:
                entry = json.loads(line)
                entry_date = datetime.fromisoformat(
                    (entry.get("timestamp") or entry.get("date", "")).replace("Z", "+00:00")
                ).replace(tzinfo=None)
                if entry_date >= cutoff:
                    ratings.append({
                        "rating": entry.get("rating", 0),
                        "date": entry_date.strftime("%Y-%m-%d"),
                    })
            except Exception:
                pass
    except Exception:
        pass

    return ratings


def aggregate_evidence(
    notes: list[RelationshipNote],
    ratings: list[dict],
) -> dict[str, OpinionEvidence]:
    evidence: dict[str, OpinionEvidence] = {}

    positive_ratings = sum(1 for r in ratings if r["rating"] >= 4)
    negative_ratings = sum(1 for r in ratings if r["rating"] <= 2)

    opinion_patterns = [
        {
            "statement": "User prefers concise responses for simple tasks",
            "support_pattern": re.compile(r"concise|brief|short|direct", re.IGNORECASE),
            "counter_pattern": re.compile(r"too short|need more|elaborate", re.IGNORECASE),
        },
        {
            "statement": "User values verification over claims of completion",
            "support_pattern": re.compile(r"verif|test|confirm|check|proof", re.IGNORECASE),
            "counter_pattern": re.compile(r"just do it|skip test|trust me", re.IGNORECASE),
        },
        {
            "statement": "User appreciates when I catch my own mistakes",
            "support_pattern": re.compile(r"catch|found|notice|correct.*mistake|self-correct", re.IGNORECASE),
            "counter_pattern": re.compile(r"didn't notice|missed|should have", re.IGNORECASE),
        },
    ]

    for pattern in opinion_patterns:
        ev = OpinionEvidence(statement=pattern["statement"])
        for note in notes:
            if pattern["support_pattern"].search(note.content):
                ev.supporting += 1
            if pattern["counter_pattern"].search(note.content):
                ev.counter += 1
        ev.supporting += positive_ratings // 3
        ev.counter += negative_ratings // 2
        evidence[pattern["statement"].lower()] = ev

    return evidence


def parse_opinions() -> dict[str, dict]:
    opinions: dict[str, dict] = {}
    opinions_path = PAI_DIR / "PAI" / "USER" / "OPINIONS.md"
    if not opinions_path.exists():
        return opinions

    content = opinions_path.read_text()
    blocks = re.split(r"^### ", content, flags=re.MULTILINE)[1:]

    for block in blocks:
        lines = block.split("\n")
        statement = lines[0].strip() if lines else ""
        conf_match = re.search(r"\*\*Confidence:\*\*\s*([\d.]+)", block)
        confidence = float(conf_match.group(1)) if conf_match else 0.5

        section_matches = re.findall(r"## (\w+) Opinions", content[:content.find(block)], re.IGNORECASE)
        section = section_matches[-1] if section_matches else "relationship"

        if statement:
            opinions[statement.lower()] = {"confidence": confidence, "section": section}

    return opinions


def escape_regex(s: str) -> str:
    return re.escape(s)


def update_opinion_confidence(
    evidence: dict[str, OpinionEvidence],
    dry_run: bool,
) -> tuple[int, list[str]]:
    opinions_path = PAI_DIR / "PAI" / "USER" / "OPINIONS.md"
    if not opinions_path.exists():
        return 0, []

    content = opinions_path.read_text()
    current_opinions = parse_opinions()
    updated = 0
    major_shifts: list[str] = []

    for key, ev in evidence.items():
        current = current_opinions.get(key)
        if not current:
            continue

        supporting_delta = ev.supporting * 0.02
        counter_delta = ev.counter * -0.05
        confirm_delta = ev.confirmations * 0.10
        contradict_delta = ev.contradictions * -0.20
        total_delta = supporting_delta + counter_delta + confirm_delta + contradict_delta

        if abs(total_delta) < 0.01:
            continue

        new_confidence = max(0.01, min(0.99, current["confidence"] + total_delta))
        actual_delta = new_confidence - current["confidence"]

        if abs(actual_delta) >= 0.15:
            major_shifts.append(f"{key}: {current['confidence'] * 100:.0f}% -> {new_confidence * 100:.0f}%")

        if not dry_run and abs(actual_delta) >= 0.01:
            escaped = escape_regex(key[0].upper() + key[1:])
            pattern = re.compile(
                rf"(###\s+{escaped}[\s\S]*?\*\*Confidence:\*\*\s*)(\d\.\d+)",
                re.IGNORECASE,
            )
            if pattern.search(content):
                content = pattern.sub(rf"\g<1>{new_confidence:.2f}", content)
                updated += 1

    if not dry_run and updated > 0:
        today = get_iso_date()
        content = re.sub(
            r"\*Last updated: \d{4}-\d{2}-\d{2}\*",
            f"*Last updated: {today}*",
            content,
        )
        opinions_path.write_text(content)

    return updated, major_shifts


def check_milestones(notes: list[RelationshipNote]) -> list[str]:
    achieved: list[str] = []
    story_path = PAI_DIR / "PAI" / "USER" / "OUR_STORY.md"
    if not story_path.exists():
        return achieved

    story_content = story_path.read_text()
    all_note_text = " ".join(n.content for n in notes)

    for milestone in MILESTONES:
        if f"[x] {milestone['description']}" in story_content:
            continue
        if milestone["pattern"] and milestone["pattern"].search(all_note_text):
            achieved.append(milestone["description"])

    return achieved


def add_milestone(description: str, dry_run: bool) -> bool:
    story_path = PAI_DIR / "PAI" / "USER" / "OUR_STORY.md"
    if not story_path.exists():
        return False

    content = story_path.read_text()
    unchecked = f"- [ ] {description}"
    checked = f"- [x] {description} *(achieved {get_iso_date()})*"

    if unchecked in content:
        if not dry_run:
            content = content.replace(unchecked, checked)
            story_path.write_text(content)
        return True
    return False


def send_notification(message: str) -> None:
    print(f"[Notification] {message}")
    topic = os.environ.get("NTFY_TOPIC")
    if topic:
        try:
            subprocess.run(
                ["bash", "-c", f'curl -s -d "{message}" ntfy.sh/{topic} 2>/dev/null || true'],
                capture_output=True, timeout=3,
            )
        except Exception:
            pass


def reflect(
    opinions_only: bool = False,
    milestones_only: bool = False,
    dry_run: bool = False,
) -> ReflectionResult:
    result = ReflectionResult()

    print("\nRelationship Reflection\n")

    notes = load_recent_notes(7)
    ratings = load_recent_ratings(7)

    print(f"Loaded {len(notes)} relationship notes from last 7 days")
    print(f"Loaded {len(ratings)} ratings from last 7 days")

    if not milestones_only:
        evidence = aggregate_evidence(notes, ratings)
        updated, major_shifts = update_opinion_confidence(evidence, dry_run)
        result.opinions_updated = updated
        result.major_shifts = major_shifts

        if updated > 0:
            print(f"\nUpdated {updated} opinion confidence scores")
        if major_shifts:
            print("\nMajor confidence shifts:")
            for shift in major_shifts:
                print(f"  - {shift}")
                if not dry_run:
                    send_notification(f"Opinion shift: {shift}")

    if not opinions_only:
        milestones = check_milestones(notes)
        result.milestones_detected = milestones

        if milestones:
            print("\nMilestones detected:")
            for m in milestones:
                print(f"  - {m}")
                if not dry_run:
                    added = add_milestone(m, False)
                    if added:
                        send_notification(f"Milestone achieved: {m}")

    if dry_run:
        print("\n[DRY RUN] No changes were made")

    print("\nReflection complete.\n")
    return result


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print("""
RelationshipReflect - Periodic reflection on relationship growth

Usage:
  python RelationshipReflect.py [options]

Options:
  --opinions-only    Only update opinion confidence scores
  --milestones-only  Only check for milestone achievements
  --dry-run          Show what would change without making changes
  --help, -h         Show this help

This tool:
  1. Scans memory/relationship/ for recent notes
  2. Updates OPINIONS.md confidence based on evidence
  3. Checks for milestone achievements in OUR_STORY.md
  4. Notifies on major changes (>15% confidence shift)
""")
        sys.exit(0)

    reflect(
        opinions_only="--opinions-only" in args,
        milestones_only="--milestones-only" in args,
        dry_run="--dry-run" in args,
    )


if __name__ == "__main__":
    main()
