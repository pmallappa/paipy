#!/usr/bin/env python3
"""
BuildCLAUDE.py -- Generate CLAUDE.md from template + settings

Reads CLAUDE.md.template, resolves variables from settings.json
and pai/algorithm/LATEST, writes CLAUDE.md.

Called by:
  - PAI installer (first install)
  - SessionStart hook (keeps fresh automatically)
  - Manual: python pai/tools/BuildCLAUDE.py
"""

import json
import os
import sys
from pathlib import Path

HOME = os.environ.get("HOME", str(Path.home()))
PAI_DIR = os.path.join(HOME, ".claude")
TEMPLATE_PATH = os.path.join(PAI_DIR, "CLAUDE.md.template")
OUTPUT_PATH = os.path.join(PAI_DIR, "CLAUDE.md")
SETTINGS_PATH = os.path.join(PAI_DIR, "settings.json")
ALGORITHM_DIR = os.path.join(PAI_DIR, "pai/algorithm")
LATEST_PATH = os.path.join(ALGORITHM_DIR, "LATEST")


def get_algorithm_version() -> str:
    if not os.path.exists(LATEST_PATH):
        print("Warning: pai/algorithm/LATEST not found, defaulting to v3.5.0", file=sys.stderr)
        return "v3.5.0"
    return Path(LATEST_PATH).read_text().strip()


def load_variables() -> dict[str, str]:
    settings: dict = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            settings = json.loads(Path(SETTINGS_PATH).read_text())
        except Exception:
            pass

    algo_version = get_algorithm_version()
    da = settings.get("daidentity", {})
    principal = settings.get("principal", {})
    pai = settings.get("pai", {})

    return {
        "{DAIDENTITY.NAME}": da.get("name", "Assistant"),
        "{DAIDENTITY.FULLNAME}": da.get("fullName", "Assistant"),
        "{DAIDENTITY.DISPLAYNAME}": da.get("displayName", "Assistant"),
        "{PRINCIPAL.NAME}": principal.get("name", "User"),
        "{PRINCIPAL.TIMEZONE}": principal.get("timezone", "UTC"),
        "{{PAI_VERSION}}": pai.get("version", "4.0.0"),
        "{{ALGO_VERSION}}": algo_version,
        "{{ALGO_PATH}}": f"pai/algorithm/{algo_version}.md",
    }


def needs_rebuild() -> bool:
    if not os.path.exists(OUTPUT_PATH):
        return True
    if not os.path.exists(TEMPLATE_PATH):
        return False

    output_content = Path(OUTPUT_PATH).read_text()
    variables = load_variables()

    for key in variables:
        if key in output_content:
            return True

    import re
    algo_version = get_algorithm_version()
    match = re.search(r"pai/algorithm/(.+?)\.md", output_content)
    if match and match.group(1) != algo_version:
        return True

    settings: dict = {}
    if os.path.exists(SETTINGS_PATH):
        try:
            settings = json.loads(Path(SETTINGS_PATH).read_text())
        except Exception:
            pass

    da_name = settings.get("daidentity", {}).get("name", "Assistant")
    if f"\U0001f5e3\ufe0f {da_name}:" not in output_content:
        return True

    return False


def build() -> dict:
    if not os.path.exists(TEMPLATE_PATH):
        return {"rebuilt": False, "reason": "No CLAUDE.md.template found"}

    content = Path(TEMPLATE_PATH).read_text()
    variables = load_variables()

    for key, value in variables.items():
        content = content.replace(key, value)

    if os.path.exists(OUTPUT_PATH):
        existing = Path(OUTPUT_PATH).read_text()
        if existing == content:
            return {"rebuilt": False, "reason": "CLAUDE.md already current"}

    Path(OUTPUT_PATH).write_text(content)
    return {"rebuilt": True}


def main() -> None:
    result = build()
    if result["rebuilt"]:
        variables = load_variables()
        print("Built CLAUDE.md from template")
        print(f"   Algorithm: {variables['{{ALGO_VERSION}}']}")
        print(f"   DA: {variables['{DAIDENTITY.NAME}']}")
        print(f"   Principal: {variables['{PRINCIPAL.NAME}']}")
    else:
        print(f"Info: {result.get('reason', 'unknown')}")


if __name__ == "__main__":
    main()
