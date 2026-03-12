#!/usr/bin/env python3
"""
LoadSkillConfig - Shared utility for loading skill configurations with user customizations

Skills call this to load their JSON/YAML configs, which automatically merges
base config with user customizations from SKILLCUSTOMIZATIONS directory.

Usage (as module):
    from LoadSkillConfig import load_skill_config
    config = load_skill_config(skill_dir, 'config.json')

Or CLI:
    python LoadSkillConfig.py <skill-dir> <filename>
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

# Types

HOME = Path.home()
CUSTOMIZATION_DIR = HOME / ".claude" / "PAI" / "USER" / "SKILLCUSTOMIZATIONS"


# ============================================================================
# Deep merge
# ============================================================================


def deep_merge(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dicts recursively."""
    result = dict(base)
    for key, custom_value in custom.items():
        if custom_value is None:
            continue
        base_value = base.get(key)
        if (
            isinstance(custom_value, dict)
            and isinstance(base_value, dict)
        ):
            result[key] = deep_merge(base_value, custom_value)
        elif isinstance(custom_value, list) and isinstance(base_value, list):
            result[key] = base_value + custom_value
        else:
            result[key] = custom_value
    return result


# ============================================================================
# Merge configs
# ============================================================================


def merge_configs(
    base: dict[str, Any],
    custom: dict[str, Any],
    strategy: str,
) -> dict[str, Any]:
    """Merge configs based on strategy."""
    customization_meta = custom.pop("_customization", None)
    effective_strategy = (
        customization_meta.get("merge_strategy", strategy)
        if isinstance(customization_meta, dict)
        else strategy
    )

    if effective_strategy == "override":
        return dict(custom)

    if effective_strategy == "deep_merge":
        return deep_merge(base, custom)

    # append (default)
    result = dict(base)
    for key, value in custom.items():
        if isinstance(result.get(key), list) and isinstance(value, list):
            result[key] = result[key] + value
        elif value is not None:
            result[key] = value
    return result


# ============================================================================
# EXTEND manifest
# ============================================================================


def load_extend_manifest(skill_name: str) -> Optional[dict[str, Any]]:
    """Load EXTEND.yaml manifest for a skill customization."""
    manifest_path = CUSTOMIZATION_DIR / skill_name / "EXTEND.yaml"
    if not manifest_path.exists():
        return None

    if yaml is None:
        print(f"Warning: PyYAML not installed, cannot parse EXTEND.yaml for {skill_name}", file=sys.stderr)
        return None

    try:
        content = manifest_path.read_text()
        manifest = yaml.safe_load(content)
        if not manifest or not manifest.get("skill") or not manifest.get("extends"):
            print(f"Warning: Invalid EXTEND.yaml for {skill_name}: missing required fields", file=sys.stderr)
            return None
        if "enabled" not in manifest:
            manifest["enabled"] = True
        return manifest
    except Exception as e:
        print(f"Warning: Failed to parse EXTEND.yaml for {skill_name}: {e}", file=sys.stderr)
        return None


# ============================================================================
# Public API
# ============================================================================


def load_skill_config(skill_dir: str, filename: str) -> dict[str, Any]:
    """
    Load a skill configuration file with user customizations merged in.

    Args:
        skill_dir: The skill's directory path
        filename: The config file to load (e.g., 'sources.json')

    Returns:
        The merged configuration
    """
    skill_name = Path(skill_dir).name
    base_config_path = Path(skill_dir) / filename

    # 1. Load base config
    try:
        base_config = json.loads(base_config_path.read_text())
    except FileNotFoundError:
        base_config = {}
    except Exception as e:
        print(f"Failed to load base config {base_config_path}: {e}", file=sys.stderr)
        raise

    # 2. Check for customization manifest
    manifest = load_extend_manifest(skill_name)
    if not manifest or not manifest.get("enabled", True):
        return base_config

    # 3. Check if this file is in the extends list
    if filename not in manifest.get("extends", []):
        return base_config

    # 4. Load customization file
    custom_config_path = CUSTOMIZATION_DIR / skill_name / filename
    if not custom_config_path.exists():
        return base_config

    try:
        custom_config = json.loads(custom_config_path.read_text())
        return merge_configs(base_config, custom_config, manifest.get("merge_strategy", "append"))
    except Exception as e:
        print(f"Warning: Failed to load customization {custom_config_path}, using base config: {e}", file=sys.stderr)
        return base_config


def get_customization_path(skill_name: str) -> str:
    """Get the customization directory path for a skill."""
    return str(CUSTOMIZATION_DIR / skill_name)


def has_customizations(skill_name: str) -> bool:
    """Check if a skill has customizations enabled."""
    manifest = load_extend_manifest(skill_name)
    return manifest is not None and manifest.get("enabled", True)


def list_customized_skills() -> list[str]:
    """List all skills with customizations."""
    if not CUSTOMIZATION_DIR.exists():
        return []
    return [
        d.name
        for d in CUSTOMIZATION_DIR.iterdir()
        if d.is_dir() and has_customizations(d.name)
    ]


# ============================================================================
# CLI
# ============================================================================


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("--help", "-h"):
        print("""
LoadSkillConfig - Load skill configs with user customizations

Usage:
  python LoadSkillConfig.py <skill-dir> <filename>    Load and merge config
  python LoadSkillConfig.py --list                    List customized skills
  python LoadSkillConfig.py --check <skill-name>      Check if skill has customizations

Examples:
  python LoadSkillConfig.py ~/.claude/skills/pai-upgrade sources.json
  python LoadSkillConfig.py --list
  python LoadSkillConfig.py --check pai-upgrade
""")
        sys.exit(0)

    if args[0] == "--list":
        skills = list_customized_skills()
        if not skills:
            print("No skills with customizations found.")
        else:
            print("Skills with customizations:")
            for s in skills:
                print(f"  - {s}")
        sys.exit(0)

    if args[0] == "--check":
        if len(args) < 2:
            print("Error: Skill name required", file=sys.stderr)
            sys.exit(1)
        skill_name = args[1]
        has = has_customizations(skill_name)
        print(f"{skill_name}: {'Has customizations enabled' if has else 'No customizations'}")
        sys.exit(0)

    # Load config mode
    if len(args) < 2:
        print("Error: Both skill-dir and filename required", file=sys.stderr)
        sys.exit(1)

    skill_dir, filename = args[0], args[1]
    try:
        config = load_skill_config(skill_dir, filename)
        print(json.dumps(config, indent=2))
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
