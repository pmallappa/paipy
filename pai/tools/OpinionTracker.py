#!/usr/bin/env python3
"""
OpinionTracker - Track and evolve confidence-based opinions

PURPOSE:
Manages the OPINIONS.md file with confidence-tracked beliefs about
working with the user. Opinions evolve based on evidence from sessions.

USAGE:
  python OpinionTracker.py add "User prefers concise responses" --category communication
  python OpinionTracker.py evidence "User prefers concise responses" --supporting "Got positive reaction to brief answer"
  python OpinionTracker.py evidence "User prefers concise responses" --counter "Long explanation was appreciated"
  python OpinionTracker.py list
  python OpinionTracker.py show "User prefers concise responses"

CONFIDENCE UPDATE RULES:
- Each supporting instance: +0.02 (capped at 0.99)
- Each counter instance: -0.05
- Explicit confirmation: +0.10
- Explicit contradiction: -0.20
- Changes >0.15 trigger notification
"""

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

PAI_DIR = Path(os.environ.get("PAI_DIR", Path(os.environ.get("HOME", "")) / ".claude"))
OPINIONS_FILE = PAI_DIR / "PAI" / "USER" / "OPINIONS.md"
RELATIONSHIP_LOG = PAI_DIR / "MEMORY" / "RELATIONSHIP"


@dataclass
class Evidence:
    date: str
    type: str  # 'supporting' | 'counter' | 'confirmation' | 'contradiction'
    description: str
    session_id: Optional[str] = None


@dataclass
class Opinion:
    statement: str
    confidence: float
    category: str  # 'communication' | 'technical' | 'relationship' | 'work_style'
    evidence: list[Evidence] = field(default_factory=list)
    last_updated: str = ""
    created: str = ""


CONFIDENCE_ADJUSTMENTS = {
    "supporting": 0.02,
    "counter": -0.05,
    "confirmation": 0.10,
    "contradiction": -0.20,
}

NOTIFICATION_THRESHOLD = 0.15


def get_iso_date() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def ensure_relationship_dir() -> None:
    month_dir = RELATIONSHIP_LOG / datetime.now().strftime("%Y-%m")
    month_dir.mkdir(parents=True, exist_ok=True)


def parse_opinions() -> dict[str, Opinion]:
    """Parse OPINIONS.md into structured data."""
    opinions: dict[str, Opinion] = {}

    if not OPINIONS_FILE.exists():
        return opinions

    content = OPINIONS_FILE.read_text()
    opinion_blocks = re.split(r"^### ", content, flags=re.MULTILINE)[1:]

    for block in opinion_blocks:
        lines = block.split("\n")
        statement = lines[0].strip() if lines else ""
        if not statement:
            continue

        conf_match = re.search(r"\*\*Confidence:\*\*\s*([\d.]+)", block)
        confidence = float(conf_match.group(1)) if conf_match else 0.5

        cat_match = re.search(r"## (\w+) Opinions", content[:content.find(block)], re.IGNORECASE)
        category = cat_match.group(1).lower() if cat_match else "relationship"

        updated_match = re.search(r"\*Last updated:\s*([^*]+)\*", block)
        last_updated = updated_match.group(1).strip() if updated_match else get_iso_date()

        evidence: list[Evidence] = []
        table_rows = re.findall(r"\| (Supporting|Counter) \| ([^|]+) \|", block, re.IGNORECASE)
        for type_str, desc in table_rows:
            evidence.append(Evidence(
                date=get_iso_date(),
                type=type_str.lower(),
                description=desc.strip(),
            ))

        opinions[statement.lower()] = Opinion(
            statement=statement,
            confidence=confidence,
            category=category,
            evidence=evidence,
            last_updated=last_updated,
            created=last_updated,
        )

    return opinions


def add_evidence(
    statement: str,
    evidence_type: str,
    description: str,
    session_id: Optional[str] = None,
) -> tuple[Opinion, float, bool]:
    """Add new evidence to an opinion and update confidence."""
    opinions = parse_opinions()
    key = statement.lower()

    opinion = opinions.get(key)
    if not opinion:
        raise ValueError(f'Opinion not found: "{statement}"')

    old_confidence = opinion.confidence
    adjustment = CONFIDENCE_ADJUSTMENTS.get(evidence_type, 0)

    opinion.confidence = max(0.01, min(0.99, opinion.confidence + adjustment))
    opinion.last_updated = get_iso_date()

    opinion.evidence.append(Evidence(
        date=get_iso_date(),
        type=evidence_type,
        description=description,
        session_id=session_id,
    ))

    confidence_change = opinion.confidence - old_confidence
    needs_notification = abs(confidence_change) >= NOTIFICATION_THRESHOLD

    log_relationship_event("opinion_update", {
        "statement": opinion.statement,
        "old_confidence": old_confidence,
        "new_confidence": opinion.confidence,
        "evidence_type": evidence_type,
        "description": description,
    })

    return opinion, confidence_change, needs_notification


def add_opinion(
    statement: str,
    category: str,
    initial_confidence: float = 0.5,
) -> Opinion:
    """Add a new opinion."""
    opinion = Opinion(
        statement=statement,
        confidence=initial_confidence,
        category=category,
        evidence=[],
        last_updated=get_iso_date(),
        created=get_iso_date(),
    )

    log_relationship_event("opinion_created", {
        "statement": statement,
        "category": category,
        "initial_confidence": initial_confidence,
    })

    return opinion


def log_relationship_event(event_type: str, data: dict) -> None:
    """Log an event to the relationship memory."""
    ensure_relationship_dir()

    today = get_iso_date()
    month_dir = RELATIONSHIP_LOG / today[:7]
    log_file = month_dir / f"{today}.jsonl"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        **data,
    }

    line = json.dumps(entry) + "\n"

    existing = log_file.read_text() if log_file.exists() else ""
    log_file.write_text(existing + line)


def list_opinions() -> None:
    """List all opinions with their confidence levels."""
    opinions = parse_opinions()
    print("\nCurrent Opinions\n")

    categories: dict[str, list[Opinion]] = {}
    for opinion in opinions.values():
        categories.setdefault(opinion.category, []).append(opinion)

    for category, opinion_list in categories.items():
        print(f"\n## {category.capitalize()}\n")
        for op in sorted(opinion_list, key=lambda o: o.confidence, reverse=True):
            filled = round(op.confidence * 10)
            bar = "\u2588" * filled + "\u2591" * (10 - filled)
            print(f"  [{bar}] {op.confidence * 100:.0f}% - {op.statement}")

    print()


def show_opinion(statement: str) -> None:
    """Show details for a specific opinion."""
    opinions = parse_opinions()
    opinion = opinions.get(statement.lower())

    if not opinion:
        print(f'Opinion not found: "{statement}"', file=sys.stderr)
        sys.exit(1)

    print(f"""
Opinion Details

**Statement:** {opinion.statement}
**Confidence:** {opinion.confidence * 100:.0f}%
**Category:** {opinion.category}
**Created:** {opinion.created}
**Last Updated:** {opinion.last_updated}

## Evidence ({len(opinion.evidence)} items)
""")

    supporting = [e for e in opinion.evidence if e.type in ("supporting", "confirmation")]
    counter = [e for e in opinion.evidence if e.type in ("counter", "contradiction")]

    if supporting:
        print("### Supporting")
        for e in supporting:
            print(f"  - [{e.date}] {e.description}")

    if counter:
        print("\n### Counter")
        for e in counter:
            print(f"  - [{e.date}] {e.description}")


def main() -> None:
    args = sys.argv[1:]
    command = args[0] if args else None

    if command == "add":
        statement = args[1] if len(args) > 1 else None
        category = "relationship"
        if "--category" in args:
            idx = args.index("--category")
            if idx + 1 < len(args):
                category = args[idx + 1]

        if not statement:
            print('Usage: python OpinionTracker.py add "statement" [--category communication|technical|relationship|work_style]', file=sys.stderr)
            sys.exit(1)

        add_opinion(statement, category)
        print(f'Added opinion: "{statement}" ({category}, confidence: 50%)')

    elif command == "evidence":
        statement = args[1] if len(args) > 1 else None
        evidence_type = None
        description = None

        for flag, etype in [("--supporting", "supporting"), ("--counter", "counter"),
                            ("--confirmation", "confirmation"), ("--contradiction", "contradiction")]:
            if flag in args:
                evidence_type = etype
                idx = args.index(flag)
                description = args[idx + 1] if idx + 1 < len(args) else None
                break

        if not statement or not evidence_type or not description:
            print('Usage: python OpinionTracker.py evidence "statement" --supporting|--counter|--confirmation|--contradiction "description"', file=sys.stderr)
            sys.exit(1)

        try:
            opinion, change, needs_notify = add_evidence(statement, evidence_type, description)
            print(f'Added {evidence_type} evidence to "{statement}"')
            print(f"   Confidence: {opinion.confidence * 100:.0f}% ({'+' if change > 0 else ''}{change * 100:.1f}%)")
            if needs_notify:
                print("\n   SIGNIFICANT CHANGE - user should be notified")
        except ValueError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)

    elif command == "list":
        list_opinions()

    elif command == "show":
        statement = args[1] if len(args) > 1 else None
        if not statement:
            print('Usage: python OpinionTracker.py show "statement"', file=sys.stderr)
            sys.exit(1)
        show_opinion(statement)

    else:
        print("""
OpinionTracker - Manage confidence-tracked opinions

Commands:
  add "statement" [--category <cat>]           Add new opinion
  evidence "statement" --supporting "desc"     Add supporting evidence
  evidence "statement" --counter "desc"        Add counter evidence
  evidence "statement" --confirmation "desc"   Explicitly confirmed
  evidence "statement" --contradiction "desc"  Explicitly contradicted
  list                                         List all opinions
  show "statement"                             Show opinion details

Categories: communication, technical, relationship, work_style
""")


if __name__ == "__main__":
    main()
