#!/usr/bin/env python3
"""
WisdomDomainClassifier - Route requests to relevant Wisdom Frames

Simple keyword-based classifier that maps request content to domain frame files.
Returns the list of relevant frame paths, ordered by relevance.

Usage:
  echo "deploy the worker" | python WisdomDomainClassifier.py
  python WisdomDomainClassifier.py --text "fix the login bug"
  python WisdomDomainClassifier.py --list

Output: JSON array of { domain, path, relevance } objects
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

BASE_DIR = Path(os.environ.get("PAI_DIR", Path(os.environ.get("HOME", "")) / ".claude"))
FRAMES_DIR = BASE_DIR / "MEMORY" / "WISDOM" / "FRAMES"

# ── Domain Keyword Map ──


@dataclass
class DomainKeywords:
    domain: str
    primary: list[re.Pattern]
    secondary: list[re.Pattern]


DOMAIN_MAP: list[DomainKeywords] = [
    DomainKeywords(
        domain="communication",
        primary=[
            re.compile(r"\b(response|format|output|verbose|concise|summary|explain)\b", re.IGNORECASE),
            re.compile(r"\b(tone|voice|style|wording|phrasing)\b", re.IGNORECASE),
            re.compile(r"\b(greeting|rating|feedback)\b", re.IGNORECASE),
        ],
        secondary=[
            re.compile(r"\b(short|long|brief|detail)\b", re.IGNORECASE),
            re.compile(r"\b(say|tell|write|read)\b", re.IGNORECASE),
        ],
    ),
    DomainKeywords(
        domain="development",
        primary=[
            re.compile(r"\b(code|function|class|module|import|export)\b", re.IGNORECASE),
            re.compile(r"\b(bug|fix|refactor|implement|build|create|add)\b", re.IGNORECASE),
            re.compile(r"\b(typescript|javascript|python|bun|npm|git)\b", re.IGNORECASE),
            re.compile(r"\b(test|lint|type.?check|compile)\b", re.IGNORECASE),
            re.compile(r"\b(hook|skill|tool|agent|algorithm)\b", re.IGNORECASE),
        ],
        secondary=[
            re.compile(r"\b(file|path|directory|folder)\b", re.IGNORECASE),
            re.compile(r"\b(error|crash|broken|issue)\b", re.IGNORECASE),
        ],
    ),
    DomainKeywords(
        domain="deployment",
        primary=[
            re.compile(r"\b(deploy|push|ship|release|publish)\b", re.IGNORECASE),
            re.compile(r"\b(cloudflare|worker|pages|wrangler|vercel)\b", re.IGNORECASE),
            re.compile(r"\b(production|staging|live|remote)\b", re.IGNORECASE),
            re.compile(r"\b(git\s+push|git\s+remote)\b", re.IGNORECASE),
        ],
        secondary=[
            re.compile(r"\b(build|compile|bundle)\b", re.IGNORECASE),
            re.compile(r"\b(url|domain|dns|ssl)\b", re.IGNORECASE),
        ],
    ),
    DomainKeywords(
        domain="content-creation",
        primary=[
            re.compile(r"\b(blog|post|article|newsletter|write)\b", re.IGNORECASE),
            re.compile(r"\b(draft|edit|proofread|publish)\b", re.IGNORECASE),
            re.compile(r"\b(social|tweet|linkedin)\b", re.IGNORECASE),
            re.compile(r"\b(video|podcast|youtube)\b", re.IGNORECASE),
        ],
        secondary=[
            re.compile(r"\b(header|image|thumbnail)\b", re.IGNORECASE),
            re.compile(r"\b(audience|reader|subscriber)\b", re.IGNORECASE),
        ],
    ),
    DomainKeywords(
        domain="system-architecture",
        primary=[
            re.compile(r"\b(architecture|design|system|infrastructure)\b", re.IGNORECASE),
            re.compile(r"\b(memory|state|hook|skill|algorithm)\b", re.IGNORECASE),
            re.compile(r"\b(pai|framework|platform)\b", re.IGNORECASE),
        ],
        secondary=[
            re.compile(r"\b(pattern|structure|flow|pipeline)\b", re.IGNORECASE),
            re.compile(r"\b(integration|component|module)\b", re.IGNORECASE),
        ],
    ),
]


# ── Classification ──


def classify_domains(text: str) -> list[dict]:
    results: list[dict] = []

    for entry in DOMAIN_MAP:
        score = 0
        primary_hits = 0
        secondary_hits = 0

        for pattern in entry.primary:
            matches = pattern.findall(text)
            if matches:
                primary_hits += len(matches)
                score += len(matches) * 2

        for pattern in entry.secondary:
            matches = pattern.findall(text)
            if matches:
                secondary_hits += len(matches)
                score += len(matches)

        if primary_hits >= 1 or secondary_hits >= 2:
            frame_path = FRAMES_DIR / f"{entry.domain}.md"
            results.append({
                "domain": entry.domain,
                "path": str(frame_path) if frame_path.exists() else "",
                "relevance": min(score / 10, 1.0),
            })

    results.sort(key=lambda r: r["relevance"], reverse=True)
    return results


def load_relevant_frames(text: str, max_frames: int = 3) -> list[dict]:
    """Load and return the content of relevant frames for a given text."""
    classified = classify_domains(text)
    loaded: list[dict] = []

    for result in classified[:max_frames]:
        if result["path"] and Path(result["path"]).exists():
            loaded.append({
                "domain": result["domain"],
                "content": Path(result["path"]).read_text(),
            })

    return loaded


def list_frames() -> list[dict]:
    """List all available frames."""
    if not FRAMES_DIR.exists():
        return []

    results = []
    for f in FRAMES_DIR.iterdir():
        if f.suffix == ".md":
            content = f.read_text()
            conf_match = re.search(r"\*\*Confidence:\*\*\s*(\d+%)", content)
            results.append({
                "domain": f.stem,
                "path": str(f),
                "confidence": conf_match.group(1) if conf_match else "unknown",
            })
    return results


# ── CLI ──


def main() -> None:
    parser = argparse.ArgumentParser(description="WisdomDomainClassifier")
    parser.add_argument("--text", "-t", type=str, help="Text to classify")
    parser.add_argument("--list", "-l", action="store_true", help="List available frames")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_frames(), indent=2))
        sys.exit(0)

    text = args.text or ""
    if not text:
        # Read from stdin
        if not sys.stdin.isatty():
            text = sys.stdin.read()

    if not text.strip():
        print("No text provided", file=sys.stderr)
        sys.exit(1)

    results = classify_domains(text.strip())
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
