#!/usr/bin/env python3
"""
WisdomFrameUpdater - Update Wisdom Frames with new observations

Takes a domain and observation, then updates the appropriate frame file.
Handles: adding new observations, incrementing counts, updating confidence,
recording evolution log entries.

Usage:
  python WisdomFrameUpdater.py --domain communication --observation "User preferred bullet points over prose"
  python WisdomFrameUpdater.py --domain development --observation "Refactoring without permission caused pushback" --type anti-pattern
  python WisdomFrameUpdater.py --domain deployment --observation "Always verify Cloudflare deployment with screenshot" --type principle

Types: principle, contextual-rule, prediction, anti-pattern, evolution
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(os.environ.get("PAI_DIR", Path(os.environ.get("HOME", "")) / ".claude"))
FRAMES_DIR = BASE_DIR / "MEMORY" / "WISDOM" / "FRAMES"


def get_frame_path(domain: str) -> Path:
    return FRAMES_DIR / f"{domain}.md"


def get_date_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def parse_observation_count(content: str) -> int:
    match = re.search(r"\*\*Observation Count:\*\*\s*(\d+)", content)
    return int(match.group(1)) if match else 0


def increment_observation_count(content: str) -> str:
    current = parse_observation_count(content)
    return re.sub(
        r"(\*\*Observation Count:\*\*\s*)\d+",
        rf"\g<1>{current + 1}",
        content,
    )


def update_crystallized_date(content: str) -> str:
    return re.sub(
        r"(\*\*Last Crystallized:\*\*\s*)\S+",
        rf"\g<1>{get_date_str()}",
        content,
    )


def append_evolution(content: str, entry: str) -> str:
    log_section = "## Evolution Log"
    log_index = content.find(log_section)

    if log_index == -1:
        return content + f"\n\n## Evolution Log\n- {get_date_str()}: {entry}\n"

    after_log = content[log_index + len(log_section):]
    next_section = after_log.find("\n## ")
    insert_point = (
        len(content) if next_section == -1
        else log_index + len(log_section) + next_section
    )

    return (
        content[:insert_point]
        + f"\n- {get_date_str()}: {entry}"
        + content[insert_point:]
    )


def add_anti_pattern(content: str, observation: str) -> str:
    section = "## Anti-Patterns"
    section_index = content.find(section)

    if section_index == -1:
        cross_frame = content.find("## Cross-Frame")
        evolution_log = content.find("## Evolution Log")
        insert_before = (
            cross_frame if cross_frame != -1
            else evolution_log if evolution_log != -1
            else len(content)
        )
        new_section = (
            f"## Anti-Patterns (from observations)\n\n### {observation}\n"
            f"- **Severity:** Medium\n- **Frequency:** Observed\n"
            f"- **Root Cause:** To be determined\n"
            f"- **Counter:** To be determined from further observations\n\n---\n\n"
        )
        return content[:insert_before] + new_section + content[insert_before:]

    after_section = content[section_index + len(section):]
    next_section = after_section.find("\n## ")
    insert_point = (
        len(content) if next_section == -1
        else section_index + len(section) + next_section
    )

    new_entry = (
        f"\n\n### {observation}\n- **Severity:** Medium\n- **Frequency:** Observed\n"
        f"- **Root Cause:** To be determined\n- **Counter:** To be determined from further observations"
    )
    return content[:insert_point] + new_entry + content[insert_point:]


def add_contextual_rule(content: str, observation: str) -> str:
    section = "## Contextual Rules"
    section_index = content.find(section)

    if section_index == -1:
        predictive = content.find("## Predictive")
        insert_before = predictive if predictive != -1 else len(content)
        return (
            content[:insert_before]
            + f"## Contextual Rules\n\n- {observation} (learned {get_date_str()})\n\n"
            + content[insert_before:]
        )

    after_section = content[section_index + len(section):]
    next_section = after_section.find("\n## ")
    insert_point = (
        len(content) if next_section == -1
        else section_index + len(section) + next_section
    )

    return (
        content[:insert_point]
        + f"\n- {observation} (learned {get_date_str()})"
        + content[insert_point:]
    )


def add_prediction(content: str, observation: str) -> str:
    section = "## Predictive Model"
    section_index = content.find(section)

    if section_index == -1:
        anti_patterns = content.find("## Anti-Patterns")
        insert_before = anti_patterns if anti_patterns != -1 else len(content)
        return (
            content[:insert_before]
            + f"## Predictive Model\n\n| Request Pattern | Predicted Want | Confidence |\n"
            f"|----------------|---------------|------------|\n"
            f"| {observation} | To be refined | 60% |\n\n"
            + content[insert_before:]
        )

    after_section = content[section_index + len(section):]
    table_end = after_section.rfind("|")
    if table_end == -1:
        return content

    insert_point = section_index + len(section) + table_end
    line_end = content.find("\n", insert_point)
    return (
        content[:line_end]
        + f"\n| {observation} | To be refined | 60% |"
        + content[line_end:]
    )


# ── Core Update Function ──


def update_frame(domain: str, observation: str, obs_type: str = "evolution") -> dict:
    frame_path = get_frame_path(domain)

    # Create frame if it doesn't exist
    if not frame_path.exists():
        FRAMES_DIR.mkdir(parents=True, exist_ok=True)

        contextual_line = f"- {observation} (learned {get_date_str()})" if obs_type == "contextual-rule" else "*None yet.*"
        prediction_line = f"| {observation} | To be refined | 60% |" if obs_type == "prediction" else ""
        anti_pattern_block = (
            f"### {observation}\n- **Severity:** Medium\n- **Frequency:** Observed\n"
            f"- **Root Cause:** To be determined\n- **Counter:** To be determined"
            if obs_type == "anti-pattern" else "*None yet.*"
        )

        new_frame = f"""# Frame: {domain.capitalize()} Domain

## Meta
- **Domain:** {domain}
- **Confidence:** 50%
- **Observation Count:** 1
- **Last Crystallized:** {get_date_str()}
- **Source:** Auto-created from observation

---

## Core Principles

*No crystallized principles yet. Observations accumulating.*

---

## Contextual Rules

{contextual_line}

---

## Predictive Model

| Request Pattern | Predicted Want | Confidence |
|----------------|---------------|------------|
{prediction_line}

---

## Anti-Patterns (from observations)

{anti_pattern_block}

---

## Cross-Frame Connections

*To be discovered through cross-frame synthesis.*

---

## Evolution Log
- {get_date_str()}: Frame created with initial observation: {observation}
"""
        frame_path.write_text(new_frame)
        return {
            "success": True,
            "domain": domain,
            "type": obs_type,
            "message": f'Created new frame for domain "{domain}" with initial observation',
            "framePath": str(frame_path),
        }

    # Update existing frame
    content = frame_path.read_text()
    content = increment_observation_count(content)
    content = update_crystallized_date(content)

    if obs_type == "anti-pattern":
        content = add_anti_pattern(content, observation)
        content = append_evolution(content, f"New anti-pattern observed: {observation}")
    elif obs_type == "contextual-rule":
        content = add_contextual_rule(content, observation)
        content = append_evolution(content, f"New contextual rule: {observation}")
    elif obs_type == "prediction":
        content = add_prediction(content, observation)
        content = append_evolution(content, f"New prediction added: {observation}")
    elif obs_type == "principle":
        content = append_evolution(content, f"Principle candidate observed: {observation}")
    else:  # evolution
        content = append_evolution(content, observation)

    frame_path.write_text(content)

    return {
        "success": True,
        "domain": domain,
        "type": obs_type,
        "message": f'Updated "{domain}" frame with {obs_type}: {observation}',
        "framePath": str(frame_path),
    }


# ── CLI ──


def main() -> None:
    parser = argparse.ArgumentParser(description="WisdomFrameUpdater")
    parser.add_argument("--domain", "-d", type=str, help="Domain name")
    parser.add_argument("--observation", "-o", type=str, help="Observation text")
    parser.add_argument(
        "--type", "-t", type=str, default="evolution",
        choices=["principle", "contextual-rule", "prediction", "anti-pattern", "evolution"],
        help="Observation type",
    )
    args = parser.parse_args()

    if not args.domain or not args.observation:
        print("Required: --domain and --observation", file=sys.stderr)
        sys.exit(1)

    result = update_frame(args.domain, args.observation, args.type)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
