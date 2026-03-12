#!/usr/bin/env python3
"""
WisdomCrossFrameSynthesizer - Extract shared principles across Wisdom Frames

Scans all frames for repeated principles, anti-patterns, and predictions
that appear across 2+ domains. Writes verified cross-domain principles
to WISDOM/PRINCIPLES/verified.md.

Usage:
  python WisdomCrossFrameSynthesizer.py              # Run synthesis
  python WisdomCrossFrameSynthesizer.py --dry-run     # Preview without writing
  python WisdomCrossFrameSynthesizer.py --health       # Show frame health metrics

Designed to be run periodically (weekly) or after significant frame updates.
"""

import argparse
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(os.environ.get("PAI_DIR", Path(os.environ.get("HOME", "")) / ".claude"))
WISDOM_DIR = BASE_DIR / "MEMORY" / "WISDOM"
FRAMES_DIR = WISDOM_DIR / "FRAMES"
PRINCIPLES_DIR = WISDOM_DIR / "PRINCIPLES"
META_DIR = WISDOM_DIR / "META"


# ── Types ──


@dataclass
class FrameData:
    domain: str
    path: str
    confidence: int
    observation_count: int
    last_crystallized: str
    principles: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)
    cross_connections: list[str] = field(default_factory=list)


@dataclass
class CrossPrinciple:
    principle: str
    domains: list[str]
    confidence: int
    evidence: str


@dataclass
class FrameHealth:
    domain: str
    confidence: int
    observation_count: int
    last_crystallized: str
    principle_count: int
    anti_pattern_count: int
    cross_connection_count: int
    health: str  # 'growing' | 'stable' | 'stale'


# ── Frame Parsing ──


def parse_frame(filepath: Path) -> FrameData:
    content = filepath.read_text()
    domain = filepath.stem

    conf_match = re.search(r"\*\*Confidence:\*\*\s*(\d+)%", content)
    obs_match = re.search(r"\*\*Observation Count:\*\*\s*(\d+)", content)
    cryst_match = re.search(r"\*\*Last Crystallized:\*\*\s*(\S+)", content)

    # Extract principles with [CRYSTAL] tag
    principles = [m.group(1).strip() for m in re.finditer(r"### (.+?) \[CRYSTAL", content)]

    # Extract anti-patterns
    anti_patterns: list[str] = []
    anti_section = content.find("## Anti-Patterns")
    if anti_section != -1:
        after_anti = content[anti_section:]
        next_section = after_anti.find("\n## ", 1)
        anti_content = after_anti[:next_section] if next_section != -1 else after_anti
        anti_patterns = [m.group(1).strip() for m in re.finditer(r"### (.+)", anti_content)]

    # Extract cross-frame connections
    cross_connections: list[str] = []
    cross_section = content.find("## Cross-Frame Connections")
    if cross_section != -1:
        after_cross = content[cross_section:]
        next_section = after_cross.find("\n## ", 1)
        cross_content = after_cross[:next_section] if next_section != -1 else after_cross
        cross_connections = [m.group(1).strip() for m in re.finditer(r"\*\*(.+?)\*\*", cross_content)]

    return FrameData(
        domain=domain,
        path=str(filepath),
        confidence=int(conf_match.group(1)) if conf_match else 50,
        observation_count=int(obs_match.group(1)) if obs_match else 0,
        last_crystallized=cryst_match.group(1) if cryst_match else "unknown",
        principles=principles,
        anti_patterns=anti_patterns,
        cross_connections=cross_connections,
    )


# ── Cross-Frame Analysis ──


STOPWORDS = frozenset([
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "of", "in", "to",
    "for", "with", "on", "at", "by", "from", "as", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "over", "and", "but", "or", "not", "no", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "than",
    "too", "very",
])


def compute_similarity(a: str, b: str) -> float:
    """Simple word-overlap similarity (Jaccard index on significant words)."""
    words_a = {w for w in re.split(r"\W+", a.lower()) if len(w) > 2 and w not in STOPWORDS}
    words_b = {w for w in re.split(r"\W+", b.lower()) if len(w) > 2 and w not in STOPWORDS}

    if not words_a or not words_b:
        return 0.0

    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union


def find_cross_principles(frames: list[FrameData]) -> list[CrossPrinciple]:
    cross_principles: list[CrossPrinciple] = []
    seen: set[str] = set()

    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            frame_a, frame_b = frames[i], frames[j]
            for principle_a in frame_a.principles:
                for principle_b in frame_b.principles:
                    similarity = compute_similarity(principle_a, principle_b)
                    key = "||".join(sorted([principle_a, principle_b]))
                    if similarity > 0.3 and key not in seen:
                        seen.add(key)
                        cross_principles.append(CrossPrinciple(
                            principle=f"{principle_a} / {principle_b}",
                            domains=[frame_a.domain, frame_b.domain],
                            confidence=min(frame_a.confidence, frame_b.confidence),
                            evidence=f"Shared principle across {frame_a.domain} and {frame_b.domain}",
                        ))

    # Check explicit cross-frame connections
    for frame in frames:
        for conn in frame.cross_connections:
            target_domain = conn.replace(".md", "").replace(":", "")
            existing = any(
                cp for cp in cross_principles
                if frame.domain in cp.domains and target_domain in cp.domains
            )
            if not existing:
                cross_principles.append(CrossPrinciple(
                    principle=f"Explicit connection: {frame.domain} <-> {target_domain}",
                    domains=[frame.domain, target_domain],
                    confidence=frame.confidence,
                    evidence=f"Declared in {frame.domain} frame cross-connections",
                ))

    return sorted(cross_principles, key=lambda cp: cp.confidence, reverse=True)


# ── Frame Health Assessment ──


def assess_health(frame: FrameData) -> FrameHealth:
    if frame.last_crystallized != "unknown":
        try:
            days_since = (datetime.now() - datetime.fromisoformat(frame.last_crystallized)).days
        except ValueError:
            days_since = 999
    else:
        days_since = 999

    if days_since <= 7 and frame.observation_count > 10:
        health = "growing"
    elif days_since <= 30:
        health = "stable"
    else:
        health = "stale"

    return FrameHealth(
        domain=frame.domain,
        confidence=frame.confidence,
        observation_count=frame.observation_count,
        last_crystallized=frame.last_crystallized,
        principle_count=len(frame.principles),
        anti_pattern_count=len(frame.anti_patterns),
        cross_connection_count=len(frame.cross_connections),
        health=health,
    )


# ── Output Generation ──


def generate_principles_report(cross_principles: list[CrossPrinciple], frames: list[FrameData]) -> str:
    date = datetime.now().strftime("%Y-%m-%d")

    principles_section = (
        "*No cross-domain principles found yet. Frames need more observations.*"
        if not cross_principles
        else "\n".join(
            f"""### {i + 1}. {cp.principle}

- **Domains:** {', '.join(cp.domains)}
- **Confidence:** {cp.confidence}%
- **Evidence:** {cp.evidence}
"""
            for i, cp in enumerate(cross_principles)
        )
    )

    coverage_rows = "\n".join(
        f"| {f.domain} | {f.confidence}% | {f.observation_count}+ | {len(f.principles)} | {len(f.anti_patterns)} |"
        for f in frames
    )

    return f"""# Verified Cross-Domain Principles

**Generated:** {date}
**Frames Analyzed:** {len(frames)}
**Cross-Domain Principles Found:** {len(cross_principles)}

---

## Principles Confirmed Across Multiple Domains

{principles_section}

---

## Frame Coverage

| Domain | Confidence | Observations | Principles | Anti-Patterns |
|--------|-----------|-------------|------------|---------------|
{coverage_rows}

---

*Generated by WisdomCrossFrameSynthesizer*
"""


def generate_health_report(health_data: list[FrameHealth]) -> str:
    date = datetime.now().strftime("%Y-%m-%d")

    health_icons = {"growing": "G", "stable": "S", "stale": "!"}
    rows = "\n".join(
        f"| {h.domain} | {health_icons.get(h.health, '?')} {h.health} | {h.confidence}% | "
        f"{h.observation_count}+ | {h.last_crystallized} | {h.principle_count} | {h.anti_pattern_count} |"
        for h in health_data
    )

    stale_recs = "\n".join(
        f"- **{h.domain}:** Stale -- needs new observations or review"
        for h in health_data if h.health == "stale"
    ) or "- All frames are active"

    no_principles = "\n".join(
        f"- **{h.domain}:** No crystallized principles yet -- needs more observations"
        for h in health_data if h.principle_count == 0
    )

    no_anti = "\n".join(
        f"- **{h.domain}:** No anti-patterns captured -- review recent failures"
        for h in health_data if h.anti_pattern_count == 0
    )

    return f"""# Wisdom Frame Health Report

**Generated:** {date}
**Total Frames:** {len(health_data)}

## Frame Status

| Domain | Health | Confidence | Observations | Last Updated | Principles | Anti-Patterns |
|--------|--------|-----------|-------------|-------------|------------|---------------|
{rows}

## Recommendations

{stale_recs}
{no_principles}
{no_anti}

---

*Generated by WisdomCrossFrameSynthesizer*
"""


# ── Main ──


def main() -> None:
    parser = argparse.ArgumentParser(description="WisdomCrossFrameSynthesizer")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--health", action="store_true", help="Show frame health metrics")
    args = parser.parse_args()

    if not FRAMES_DIR.exists():
        print("No frames directory found")
        sys.exit(0)

    frame_files = [f for f in FRAMES_DIR.iterdir() if f.suffix == ".md"]
    if not frame_files:
        print("No frames found")
        sys.exit(0)

    print(f"Loading {len(frame_files)} frames...")
    frames = [parse_frame(f) for f in frame_files]

    if args.health:
        health_data = [assess_health(f) for f in frames]
        report = generate_health_report(health_data)

        if args.dry_run:
            print(report)
        else:
            META_DIR.mkdir(parents=True, exist_ok=True)
            (META_DIR / "frame-health.md").write_text(report)
            print("Health report written to WISDOM/META/frame-health.md")
        sys.exit(0)

    print("Analyzing cross-frame principles...")
    cross_principles = find_cross_principles(frames)
    print(f"   Found {len(cross_principles)} cross-domain principles")

    report = generate_principles_report(cross_principles, frames)

    if args.dry_run:
        print(report)
    else:
        PRINCIPLES_DIR.mkdir(parents=True, exist_ok=True)
        (PRINCIPLES_DIR / "verified.md").write_text(report)
        print("Principles report written to WISDOM/PRINCIPLES/verified.md")

        health_data = [assess_health(f) for f in frames]
        health_report = generate_health_report(health_data)
        META_DIR.mkdir(parents=True, exist_ok=True)
        (META_DIR / "frame-health.md").write_text(health_report)
        print("Health report written to WISDOM/META/frame-health.md")


if __name__ == "__main__":
    main()
