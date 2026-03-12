#!/usr/bin/env python3
"""
RebuildPAI - Assembles SKILL.md from Components/

Usage: python ~/.claude/pai/tools/RebuildPAI.py

Reads all .md files from Components/, sorts by numeric prefix,
concatenates them, and writes to SKILL.md with build timestamp
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

HOME = os.environ.get("HOME", "")
PAI_DIR = Path(HOME) / ".claude" / "PAI"
COMPONENTS_DIR = PAI_DIR / "Components"
ALGORITHM_DIR = COMPONENTS_DIR / "Algorithm"
OUTPUT_FILE = PAI_DIR / "SKILL.md"
SETTINGS_PATH = Path(HOME) / ".claude" / "settings.json"


def load_variables() -> dict[str, str]:
    """Load identity variables from settings.json for template resolution."""
    try:
        settings = json.loads(SETTINGS_PATH.read_text())
        return {
            "{DAIDENTITY.NAME}": settings.get("daidentity", {}).get("name", "PAI"),
            "{DAIDENTITY.FULLNAME}": settings.get("daidentity", {}).get("fullName", "Personal AI"),
            "{DAIDENTITY.DISPLAYNAME}": settings.get("daidentity", {}).get("displayName", "PAI"),
            "{PRINCIPAL.NAME}": settings.get("principal", {}).get("name", "User"),
            "{PRINCIPAL.TIMEZONE}": settings.get("principal", {}).get("timezone", "UTC"),
            "{DAIDENTITY.ALGORITHMVOICEID}": (
                settings.get("daidentity", {}).get("voices", {}).get("algorithm", {}).get("voiceId", "")
            ),
        }
    except Exception:
        print("Warning: Could not read settings.json, using defaults", file=sys.stderr)
        return {
            "{DAIDENTITY.NAME}": "PAI",
            "{DAIDENTITY.FULLNAME}": "Personal AI",
            "{DAIDENTITY.DISPLAYNAME}": "PAI",
            "{PRINCIPAL.NAME}": "User",
            "{PRINCIPAL.TIMEZONE}": "UTC",
            "{DAIDENTITY.ALGORITHMVOICEID}": "",
        }


def resolve_variables(content: str, variables: dict[str, str]) -> str:
    """Resolve template variables in content."""
    result = content
    for key, value in variables.items():
        result = result.replace(key, value)
    return result


def get_timestamp() -> str:
    """Generate timestamp in format: DAY MONTH YEAR HOUR MINUTE SECOND."""
    now = datetime.now()
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    return f"{now.day} {months[now.month - 1]} {now.year} {now.hour:02d}:{now.minute:02d}:{now.second:02d}"


def load_algorithm() -> str:
    """Load versioned algorithm."""
    latest_file = ALGORITHM_DIR / "LATEST"
    version = latest_file.read_text().strip()
    algorithm_file = ALGORITHM_DIR / f"{version}.md"
    return algorithm_file.read_text()


def main() -> None:
    # Get all .md files, sorted by numeric prefix
    components = sorted(
        [f for f in COMPONENTS_DIR.iterdir() if f.suffix == ".md" and f.is_file()],
        key=lambda f: int(f.name.split("-")[0]) if f.name.split("-")[0].isdigit() else 0,
    )

    if not components:
        print("Error: No component files found in Components/", file=sys.stderr)
        sys.exit(1)

    # Assemble content
    output = ""
    timestamp = get_timestamp()
    algorithm_content = load_algorithm()

    for comp_file in components:
        content = comp_file.read_text()

        # Inject timestamp into frontmatter component
        if comp_file.name == "00-frontmatter.md":
            content = content.replace(
                "  Build:  bun ~/.claude/pai/tools/RebuildPAI.ts",
                f"  Build:  bun ~/.claude/pai/tools/RebuildPAI.ts\n  Built:  {timestamp}",
            )

        # Inject versioned algorithm
        if "{{ALGORITHM_VERSION}}" in content:
            content = content.replace("{{ALGORITHM_VERSION}}", algorithm_content)

        output += content

    # Resolve template variables from settings.json
    variables = load_variables()
    output = resolve_variables(output, variables)

    # Write output
    OUTPUT_FILE.write_text(output)

    component_names = [c.name for c in components]
    print(f"Built SKILL.md from {len(components)} components:")
    for i, c in enumerate(component_names):
        print(f"   {i + 1:2d}. {c}")

    print(f"\nResolved {len(variables)} template variables:")
    for key, value in variables.items():
        print(f"   {key} -> {value}")

    print(f"\nOutput: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
