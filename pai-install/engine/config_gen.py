"""
PAI Installer v4.0 -- Configuration Generator
Generates a FALLBACK settings.json from collected user data.
Only used when no existing settings.json exists.
Produces minimal output -- just fields the installer collects.
Hooks, permissions, and other config come from the release template.
"""

from __future__ import annotations

from typing import Any, Dict

from engine.types import DEFAULT_VOICES, PAIConfig


def generate_settings_json(config: PAIConfig) -> Dict[str, Any]:
    """
    Generate a minimal fallback settings.json from installer-collected data.
    This is merged into (not replacing) the release template.
    """
    voice_id = config.voice_id or DEFAULT_VOICES.get(config.voice_type or "", DEFAULT_VOICES["female"])

    settings: Dict[str, Any] = {
        "env": {
            "PAI_DIR": config.pai_dir,
            "PAI_CONFIG_DIR": config.config_dir,
        },
        "contextFiles": [
            "skills/pai/SKILL.md",
            "skills/pai/AISTEERINGRULES.md",
            "skills/pai/user/AISTEERINGRULES.md",
            "skills/pai/user/DAIDENTITY.md",
        ],
        "daidentity": {
            "name": config.ai_name,
            "fullName": f"{config.ai_name} -- Personal AI",
            "displayName": config.ai_name.upper(),
            "color": "#3B82F6",
            "voices": {
                "main": {
                    "voiceId": voice_id,
                    "stability": 0.35,
                    "similarityBoost": 0.80,
                    "style": 0.90,
                    "speed": 1.1,
                },
            },
            "startupCatchphrase": config.catchphrase,
        },
        "principal": {
            "name": config.principal_name,
            "timezone": config.timezone,
        },
        "preferences": {
            "temperatureUnit": config.temperature_unit or "fahrenheit",
        },
        "pai": {
            "repoUrl": "https://github.com/danielmiessler/PAI",
            "version": "4.0.0",
        },
    }

    if config.projects_dir:
        settings["env"]["PROJECTS_DIR"] = config.projects_dir

    return settings
