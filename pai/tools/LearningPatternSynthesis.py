#!/usr/bin/env python3
"""
LearningPatternSynthesis - Aggregate ratings into actionable patterns

Analyzes LEARNING/SIGNALS/ratings.jsonl to find recurring patterns
and generates synthesis reports for continuous improvement.

Commands:
  --week         Analyze last 7 days (default)
  --month        Analyze last 30 days
  --all          Analyze all ratings
  --dry-run      Show analysis without writing

Examples:
  python LearningPatternSynthesis.py --week
  python LearningPatternSynthesis.py --month --dry-run
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

CLAUDE_DIR = Path(os.environ.get("HOME", "")) / ".claude"
LEARNING_DIR = CLAUDE_DIR / "MEMORY" / "LEARNING"
RATINGS_FILE = LEARNING_DIR / "SIGNALS" / "ratings.jsonl"
SYNTHESIS_DIR = LEARNING_DIR / "SYNTHESIS"

# ============================================================================
# Types
# ============================================================================


@dataclass
class Rating:
    timestamp: str
    rating: int
    session_id: str
    source: str  # "explicit" | "implicit"
    sentiment_summary: str
    confidence: float
    comment: Optional[str] = None


@dataclass
class PatternGroup:
    pattern: str
    count: int
    avg_rating: float
    avg_confidence: float
    examples: list[str] = field(default_factory=list)


@dataclass
class SynthesisResult:
    period: str
    total_ratings: int
    avg_rating: float
    frustrations: list[PatternGroup] = field(default_factory=list)
    successes: list[PatternGroup] = field(default_factory=list)
    top_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


# ============================================================================
# Pattern Detection
# ============================================================================

FRUSTRATION_PATTERNS: dict[str, re.Pattern] = {
    "Time/Performance Issues": re.compile(r"time|slow|delay|hang|wait|long|minutes|hours", re.IGNORECASE),
    "Incomplete Work": re.compile(r"incomplete|missing|partial|didn't finish|not done", re.IGNORECASE),
    "Wrong Approach": re.compile(r"wrong|incorrect|not what|misunderstand|mistake", re.IGNORECASE),
    "Over-engineering": re.compile(r"over-?engineer|too complex|unnecessary|bloat", re.IGNORECASE),
    "Tool/System Failures": re.compile(r"fail|error|broken|crash|bug|issue", re.IGNORECASE),
    "Communication Problems": re.compile(r"unclear|confus|didn't ask|should have asked", re.IGNORECASE),
    "Repetitive Issues": re.compile(r"again|repeat|still|same problem", re.IGNORECASE),
}

SUCCESS_PATTERNS: dict[str, re.Pattern] = {
    "Quick Resolution": re.compile(r"quick|fast|efficient|smooth", re.IGNORECASE),
    "Good Understanding": re.compile(r"understood|clear|exactly|perfect", re.IGNORECASE),
    "Proactive Help": re.compile(r"proactive|anticipat|helpful|above and beyond", re.IGNORECASE),
    "Clean Implementation": re.compile(r"clean|simple|elegant|well done", re.IGNORECASE),
}


def detect_patterns(summaries: list[str], patterns: dict[str, re.Pattern]) -> dict[str, list[str]]:
    results: dict[str, list[str]] = {}
    for summary in summaries:
        for name, pattern in patterns.items():
            if pattern.search(summary):
                results.setdefault(name, []).append(summary)
    return results


def group_to_pattern_groups(
    grouped: dict[str, list[str]],
    ratings: list[Rating],
) -> list[PatternGroup]:
    groups: list[PatternGroup] = []

    for pattern, examples in grouped.items():
        matching_ratings = [
            r for r in ratings if r.sentiment_summary in examples
        ]

        avg_rating = (
            sum(r.rating for r in matching_ratings) / len(matching_ratings)
            if matching_ratings
            else 5.0
        )
        avg_confidence = (
            sum(r.confidence for r in matching_ratings) / len(matching_ratings)
            if matching_ratings
            else 0.5
        )

        groups.append(
            PatternGroup(
                pattern=pattern,
                count=len(examples),
                avg_rating=avg_rating,
                avg_confidence=avg_confidence,
                examples=examples[:3],
            )
        )

    return sorted(groups, key=lambda g: g.count, reverse=True)


# ============================================================================
# Analysis
# ============================================================================


def analyze_ratings(ratings: list[Rating], period: str) -> SynthesisResult:
    if not ratings:
        return SynthesisResult(period=period, total_ratings=0, avg_rating=0.0)

    avg_rating = sum(r.rating for r in ratings) / len(ratings)

    frustration_ratings = [r for r in ratings if r.rating <= 4]
    success_ratings = [r for r in ratings if r.rating >= 7]

    frustration_summaries = [r.sentiment_summary for r in frustration_ratings]
    success_summaries = [r.sentiment_summary for r in success_ratings]

    frustration_groups = detect_patterns(frustration_summaries, FRUSTRATION_PATTERNS)
    success_groups = detect_patterns(success_summaries, SUCCESS_PATTERNS)

    frustrations = group_to_pattern_groups(frustration_groups, frustration_ratings)
    successes = group_to_pattern_groups(success_groups, success_ratings)

    top_issues = [
        f"{f.pattern} ({f.count} occurrences, avg rating {f.avg_rating:.1f})"
        for f in frustrations[:3]
    ]

    recommendations: list[str] = []
    if any(f.pattern == "Time/Performance Issues" for f in frustrations):
        recommendations.append("Consider setting clearer time expectations and progress updates")
    if any(f.pattern == "Wrong Approach" for f in frustrations):
        recommendations.append("Ask clarifying questions before starting complex tasks")
    if any(f.pattern == "Over-engineering" for f in frustrations):
        recommendations.append("Default to simpler solutions; only add complexity when justified")
    if any(f.pattern == "Communication Problems" for f in frustrations):
        recommendations.append("Summarize understanding before implementation")
    if not recommendations:
        recommendations.append("Continue current patterns - no major issues detected")

    return SynthesisResult(
        period=period,
        total_ratings=len(ratings),
        avg_rating=avg_rating,
        frustrations=frustrations,
        successes=successes,
        top_issues=top_issues,
        recommendations=recommendations,
    )


# ============================================================================
# File Generation
# ============================================================================


def format_synthesis_report(result: SynthesisResult) -> str:
    date = datetime.now().strftime("%Y-%m-%d")

    top_issues_str = (
        "\n".join(f"{i + 1}. {issue}" for i, issue in enumerate(result.top_issues))
        if result.top_issues
        else "No significant issues detected"
    )

    content = f"""# Learning Pattern Synthesis

**Period:** {result.period}
**Generated:** {date}
**Total Ratings:** {result.total_ratings}
**Average Rating:** {result.avg_rating:.1f}/10

---

## Top Issues

{top_issues_str}

## Frustration Patterns

"""

    if not result.frustrations:
        content += "*No frustration patterns detected*\n\n"
    else:
        for f in result.frustrations:
            examples_str = "\n".join(f'  - "{e}"' for e in f.examples)
            content += f"""### {f.pattern}

- **Occurrences:** {f.count}
- **Avg Rating:** {f.avg_rating:.1f}
- **Confidence:** {f.avg_confidence * 100:.0f}%
- **Examples:**
{examples_str}

"""

    content += "## Success Patterns\n\n"

    if not result.successes:
        content += "*No success patterns detected*\n\n"
    else:
        for s in result.successes:
            examples_str = "\n".join(f'  - "{e}"' for e in s.examples)
            content += f"""### {s.pattern}

- **Occurrences:** {s.count}
- **Avg Rating:** {s.avg_rating:.1f}
- **Examples:**
{examples_str}

"""

    recs_str = "\n".join(f"{i + 1}. {r}" for i, r in enumerate(result.recommendations))
    content += f"""## Recommendations

{recs_str}

---

*Generated by LearningPatternSynthesis tool*
"""

    return content


def write_synthesis(result: SynthesisResult, period: str) -> str:
    now = datetime.now()
    month_dir = SYNTHESIS_DIR / f"{now.year}-{now.month:02d}"
    month_dir.mkdir(parents=True, exist_ok=True)

    date_str = now.strftime("%Y-%m-%d")
    filename = f"{date_str}_{period.lower().replace(' ', '-')}-patterns.md"
    filepath = month_dir / filename

    content = format_synthesis_report(result)
    filepath.write_text(content)

    return str(filepath)


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="LearningPatternSynthesis - Aggregate ratings into actionable patterns")
    parser.add_argument("--week", action="store_true", help="Analyze last 7 days (default)")
    parser.add_argument("--month", action="store_true", help="Analyze last 30 days")
    parser.add_argument("--all", action="store_true", help="Analyze all ratings")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if not RATINGS_FILE.exists():
        print(f"No ratings file found at: {RATINGS_FILE}")
        sys.exit(0)

    content = RATINGS_FILE.read_text()
    all_ratings: list[Rating] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            all_ratings.append(Rating(
                timestamp=data.get("timestamp", ""),
                rating=data.get("rating", 0),
                session_id=data.get("session_id", ""),
                source=data.get("source", "implicit"),
                sentiment_summary=data.get("sentiment_summary", ""),
                confidence=data.get("confidence", 0.5),
                comment=data.get("comment"),
            ))
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"Loaded {len(all_ratings)} total ratings")

    period = "Weekly"
    cutoff_date = datetime.now()

    if args.month:
        period = "Monthly"
        cutoff_date -= timedelta(days=30)
    elif args.all:
        period = "All Time"
        cutoff_date = datetime.min
    else:
        cutoff_date -= timedelta(days=7)

    filtered_ratings = [
        r for r in all_ratings
        if datetime.fromisoformat(r.timestamp.replace("Z", "+00:00")).replace(tzinfo=None) >= cutoff_date
    ] if period != "All Time" else all_ratings

    print(f"Analyzing {len(filtered_ratings)} ratings for {period.lower()} period")

    if not filtered_ratings:
        print("No ratings in this period")
        sys.exit(0)

    result = analyze_ratings(filtered_ratings, period)

    print(f"\nAnalysis Results:")
    print(f"   Average Rating: {result.avg_rating:.1f}/10")
    print(f"   Frustration Patterns: {len(result.frustrations)}")
    print(f"   Success Patterns: {len(result.successes)}")

    if result.top_issues:
        print(f"\n   Top Issues:")
        for issue in result.top_issues:
            print(f"   - {issue}")

    if args.dry_run:
        print("\nDRY RUN - Would write synthesis report")
        print("\nRecommendations:")
        for rec in result.recommendations:
            print(f"   - {rec}")
    else:
        filepath = write_synthesis(result, period)
        print(f"\nCreated synthesis report: {Path(filepath).name}")


if __name__ == "__main__":
    main()
