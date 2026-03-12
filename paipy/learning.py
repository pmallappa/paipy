#!/usr/bin/env python3
"""
learning.py -- Learning utilities: categorization, capture detection, and readback.

Merged from: learning_utils.py + learning_readback.py
Wraps all functions in the Learning class.
"""

import os
import re
from pathlib import Path
from typing import List, Literal, Optional

from ._paths import Paths


class Learning:
    """Learning categorization, capture detection, and context readback."""

    # ── Category Detection ────────────────────────────────────────────

    @staticmethod
    def get_learning_category(content: str, comment: Optional[str] = None) -> Literal["SYSTEM", "ALGORITHM"]:
        """
        Categorize learning as SYSTEM (tooling/infrastructure) or ALGORITHM (task execution).

        SYSTEM = hook failures, tooling issues, infrastructure problems, system errors
        ALGORITHM = task execution issues, approach errors, method improvements

        Check ALGORITHM first because user feedback about task execution is more valuable.
        Default to ALGORITHM since most learnings are about task quality, not infrastructure.
        """
        text = f"{content} {comment or ''}".lower()

        algorithm_indicators = [
            re.compile(r"over.?engineer"),
            re.compile(r"wrong approach"),
            re.compile(r"should have asked"),
            re.compile(r"didn't follow"),
            re.compile(r"missed the point"),
            re.compile(r"too complex"),
            re.compile(r"didn't understand"),
            re.compile(r"wrong direction"),
            re.compile(r"not what i wanted"),
            re.compile(r"approach|method|strategy|reasoning"),
        ]

        system_indicators = [
            re.compile(r"hook|crash|broken"),
            re.compile(r"tool|config|deploy|path"),
            re.compile(r"import|module|file.*not.*found"),
            re.compile(r"typescript|javascript|npm|bun"),
        ]

        for pattern in algorithm_indicators:
            if pattern.search(text):
                return "ALGORITHM"

        for pattern in system_indicators:
            if pattern.search(text):
                return "SYSTEM"

        return "ALGORITHM"

    @staticmethod
    def is_learning_capture(text: str, summary: Optional[str] = None, analysis: Optional[str] = None) -> bool:
        """Determine if a response represents a learning moment."""
        learning_indicators = [
            re.compile(r"problem|issue|bug|error|failed|broken", re.IGNORECASE),
            re.compile(r"fixed|solved|resolved|discovered|realized|learned", re.IGNORECASE),
            re.compile(r"troubleshoot|debug|investigate|root cause", re.IGNORECASE),
            re.compile(r"lesson|takeaway|now we know|next time", re.IGNORECASE),
        ]

        check_text = f"{summary or ''} {analysis or ''} {text}"

        indicator_count = 0
        for pattern in learning_indicators:
            if pattern.search(check_text):
                indicator_count += 1

        return indicator_count >= 2

    # ── Readback: Private Helpers ─────────────────────────────────────

    @staticmethod
    def _get_recent_learnings(subdir: str, count: int) -> List[str]:
        """
        Read the N most recent learning files from a LEARNING subdirectory.
        Files are named YYYY-MM-DD-HHMMSS_LEARNING_*.md with YAML frontmatter.
        Extracts the **Feedback:** line and rating for compact display.
        """
        insights: List[str] = []
        learning_dir = Paths.memory_str("LEARNING", subdir)
        if not os.path.isdir(learning_dir):
            return insights

        try:
            months = sorted(
                [
                    d.name
                    for d in Path(learning_dir).iterdir()
                    if d.is_dir() and re.match(r"^\d{4}-\d{2}$", d.name)
                ],
                reverse=True,
            )

            for month in months:
                if len(insights) >= count:
                    break
                month_path = os.path.join(learning_dir, month)

                try:
                    files = sorted(
                        [f for f in os.listdir(month_path) if f.endswith(".md")],
                        reverse=True,
                    )

                    for file in files:
                        if len(insights) >= count:
                            break
                        try:
                            content = Path(os.path.join(month_path, file)).read_text()
                            feedback_match = re.search(r"\*\*Feedback:\*\*\s*(.+)", content)
                            rating_match = re.search(r"rating:\s*(\d+)", content)
                            if feedback_match:
                                rating = rating_match.group(1) if rating_match else "?"
                                feedback = feedback_match.group(1)[:80]
                                insights.append(f"[{rating}/10] {feedback}")
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        return insights

    # ── Readback: Public Methods ──────────────────────────────────────

    @staticmethod
    def load_learning_digest() -> Optional[str]:
        """
        Load recent learning signals from ALGORITHM and SYSTEM directories.
        Returns the 3 most recent from each, formatted as a compact bullet list.
        """
        algorithm_insights = Learning._get_recent_learnings("ALGORITHM", 3)
        system_insights = Learning._get_recent_learnings("SYSTEM", 3)

        if not algorithm_insights and not system_insights:
            return None

        parts = ["**Recent Learning Signals:**"]

        if algorithm_insights:
            parts.append("*Algorithm:*")
            for i in algorithm_insights:
                parts.append(f"  {i}")
        if system_insights:
            parts.append("*System:*")
            for i in system_insights:
                parts.append(f"  {i}")

        return "\n".join(parts)

    @staticmethod
    def load_wisdom_frames() -> Optional[str]:
        """
        Load Wisdom Frame core principles for context injection.
        Reads all WISDOM/FRAMES/*.md files and extracts principle headers
        (lines matching "### Name [CRYSTAL: N%]").
        """
        frames_dir = Paths.memory_str("WISDOM", "FRAMES")
        if not os.path.isdir(frames_dir):
            return None

        principles: List[str] = []

        try:
            files = [f for f in os.listdir(frames_dir) if f.endswith(".md")]

            for file in files:
                try:
                    content = Path(os.path.join(frames_dir, file)).read_text()
                    domain = file.replace(".md", "")

                    for match in re.finditer(r"^### (.+?) \[CRYSTAL: (\d+)%\]", content, re.MULTILINE):
                        confidence = int(match.group(2))
                        if confidence >= 85:
                            principles.append(f"[{domain}] {match.group(1)} ({confidence}%)")
                except Exception:
                    pass
        except Exception:
            pass

        if not principles:
            return None

        lines = "\n".join(f"  {p}" for p in principles)
        return f"**Wisdom Frames (high confidence):**\n{lines}"

    @staticmethod
    def load_failure_patterns() -> Optional[str]:
        """
        Load recent failure pattern insights.
        Reads the 5 most recent FAILURES directories and extracts slug/date info.
        """
        failures_dir = Paths.memory_str("LEARNING", "FAILURES")
        if not os.path.isdir(failures_dir):
            return None

        patterns: List[str] = []

        try:
            months = sorted(
                [
                    d.name
                    for d in Path(failures_dir).iterdir()
                    if d.is_dir() and re.match(r"^\d{4}-\d{2}$", d.name)
                ],
                reverse=True,
            )

            for month in months:
                if len(patterns) >= 5:
                    break
                month_path = os.path.join(failures_dir, month)

                try:
                    dirs = sorted(
                        [
                            d.name
                            for d in Path(month_path).iterdir()
                            if d.is_dir()
                        ],
                        reverse=True,
                    )

                    for dir_name in dirs:
                        if len(patterns) >= 5:
                            break
                        context_path = os.path.join(month_path, dir_name, "CONTEXT.md")
                        if not os.path.exists(context_path):
                            continue

                        try:
                            slug = re.sub(r"^\d{4}-\d{2}-\d{2}-\d{6}_", "", dir_name).replace("-", " ")
                            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})", dir_name)
                            date = date_match.group(1) if date_match else ""
                            patterns.append(f"[{date}] {slug[:70]}")
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

        if not patterns:
            return None

        lines = "\n".join(f"  {p}" for p in patterns)
        return f"**Recent Failure Patterns (avoid these):**\n{lines}"

    @staticmethod
    def load_signal_trends() -> Optional[str]:
        """
        Load performance signal trends from the pre-computed learning-cache.sh.
        Extracts numeric averages and trend direction for a compact status line.
        """
        cache_path = Paths.memory_str("STATE", "learning-cache.sh")
        if not os.path.exists(cache_path):
            return None

        try:
            content = Path(cache_path).read_text()

            variables: dict = {}
            for line in content.split("\n"):
                match = re.match(r"^(\w+)='?([^']*)'?$", line)
                if match:
                    variables[match.group(1)] = match.group(2)

            today_avg = variables.get("today_avg", "?")
            week_avg = variables.get("week_avg", "?")
            month_avg = variables.get("month_avg", "?")
            trend = variables.get("trend", "stable")
            total_count = variables.get("total_count", "?")

            trend_label = {"up": "trending up", "down": "trending down"}.get(trend, "stable")

            return (
                f"**Performance Signals:** Today: {today_avg}/10 | "
                f"Week: {week_avg}/10 | Month: {month_avg}/10 | "
                f"Trend: {trend_label} | Total signals: {total_count}"
            )
        except Exception:
            return None
