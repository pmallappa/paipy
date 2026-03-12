"""
PAI Installer v4.0 -- Validation
Verifies installation completeness after all steps run.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import List

from engine.types import InstallState, InstallSummary, ValidationCheck


async def _check_voice_server_health() -> bool:
    """Check if voice server is running via HTTP health check."""
    try:
        req = urllib.request.Request("http://localhost:8888/health")
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


async def run_validation(state: InstallState) -> List[ValidationCheck]:
    """Run all validation checks against the current state."""
    home = str(Path.home())
    pai_dir = state.detection.pai_dir if state.detection else os.path.join(home, ".claude")
    config_dir = state.detection.config_dir if state.detection else os.path.join(home, ".config", "PAI")
    checks: List[ValidationCheck] = []

    # 1. settings.json exists and is valid JSON
    settings_path = os.path.join(pai_dir, "settings.json")
    settings_exists = os.path.exists(settings_path)
    settings_valid = False
    settings = None

    if settings_exists:
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
            settings_valid = True
        except Exception:
            settings_valid = False

    checks.append(ValidationCheck(
        name="settings.json",
        passed=settings_exists and settings_valid,
        detail=(
            "Valid configuration file"
            if settings_valid
            else "File exists but invalid JSON"
            if settings_exists
            else "File not found"
        ),
        critical=True,
    ))

    # 2. Required settings fields
    if settings:
        checks.append(ValidationCheck(
            name="Principal name",
            passed=bool(settings.get("principal", {}).get("name")),
            detail=(
                f"Set to: {settings['principal']['name']}"
                if settings.get("principal", {}).get("name")
                else "Not configured"
            ),
            critical=True,
        ))

        checks.append(ValidationCheck(
            name="AI identity",
            passed=bool(settings.get("daidentity", {}).get("name")),
            detail=(
                f"Set to: {settings['daidentity']['name']}"
                if settings.get("daidentity", {}).get("name")
                else "Not configured"
            ),
            critical=True,
        ))

        checks.append(ValidationCheck(
            name="PAI version",
            passed=bool(settings.get("pai", {}).get("version")),
            detail=(
                f"v{settings['pai']['version']}"
                if settings.get("pai", {}).get("version")
                else "Not set"
            ),
            critical=False,
        ))

        checks.append(ValidationCheck(
            name="Timezone",
            passed=bool(settings.get("principal", {}).get("timezone")),
            detail=settings.get("principal", {}).get("timezone", "Not configured"),
            critical=False,
        ))

    # 3. Directory structure
    required_dirs = [
        {"path": "skills", "name": "Skills directory"},
        {"path": "MEMORY", "name": "Memory directory"},
        {"path": os.path.join("MEMORY", "STATE"), "name": "State directory"},
        {"path": os.path.join("MEMORY", "WORK"), "name": "Work directory"},
        {"path": "hooks", "name": "Hooks directory"},
        {"path": "Plans", "name": "Plans directory"},
    ]

    for d in required_dirs:
        full_path = os.path.join(pai_dir, d["path"])
        exists = os.path.exists(full_path)
        checks.append(ValidationCheck(
            name=d["name"],
            passed=exists,
            detail="Present" if exists else "Missing",
            critical=d["path"] in ("skills", "MEMORY"),
        ))

    # 4. PAI skill present
    skill_path = os.path.join(pai_dir, "skills", "PAI", "SKILL.md")
    skill_exists = os.path.exists(skill_path)
    checks.append(ValidationCheck(
        name="PAI core skill",
        passed=skill_exists,
        detail="Present" if skill_exists else "Not found -- clone PAI repo to enable",
        critical=False,
    ))

    # 5. ElevenLabs key stored -- check all three possible locations
    env_paths = [
        os.path.join(config_dir, ".env"),
        os.path.join(pai_dir, ".env"),
        os.path.join(home, ".env"),
    ]
    eleven_labs_key_stored = False
    eleven_labs_key_location = ""
    for ep in env_paths:
        if os.path.exists(ep):
            try:
                with open(ep, "r") as f:
                    env_content = f.read()
                if "ELEVENLABS_API_KEY=" in env_content and "ELEVENLABS_API_KEY=\n" not in env_content:
                    eleven_labs_key_stored = True
                    eleven_labs_key_location = ep
                    break
            except Exception:
                pass

    checks.append(ValidationCheck(
        name="ElevenLabs API key",
        passed=eleven_labs_key_stored,
        detail=(
            f"Stored in {eleven_labs_key_location}"
            if eleven_labs_key_stored
            else "Collected but not saved"
            if state.collected.eleven_labs_key
            else "Not configured"
        ),
        critical=False,
    ))

    # 6. DA voice configured in settings (nested under voices.main.voiceId)
    voice_id = None
    if settings:
        voice_id = (
            settings.get("daidentity", {}).get("voices", {}).get("main", {}).get("voiceId")
        )
    voice_id_configured = bool(voice_id)

    checks.append(ValidationCheck(
        name="DA voice ID",
        passed=voice_id_configured,
        detail=(
            f"Voice ID: {voice_id[:8]}..."
            if voice_id_configured and voice_id
            else "Not configured"
        ),
        critical=False,
    ))

    # 7. Voice server reachable (live HTTP health check)
    voice_server_healthy = await _check_voice_server_health()

    checks.append(ValidationCheck(
        name="Voice server",
        passed=voice_server_healthy,
        detail=(
            "Running (localhost:8888)"
            if voice_server_healthy
            else "Not reachable -- start voice server"
        ),
        critical=False,
    ))

    # 8. Zsh alias configured
    zshrc_path = os.path.join(home, ".zshrc")
    alias_configured = False
    if os.path.exists(zshrc_path):
        try:
            with open(zshrc_path, "r") as f:
                zsh_content = f.read()
            alias_configured = "# PAI alias" in zsh_content and "alias pai=" in zsh_content
        except Exception:
            pass

    checks.append(ValidationCheck(
        name="Shell alias (pai)",
        passed=alias_configured,
        detail="Configured in .zshrc" if alias_configured else "Not found -- run: source ~/.zshrc",
        critical=True,
    ))

    return checks


def generate_summary(state: InstallState) -> InstallSummary:
    """Generate install summary from state."""
    voice_mode = "none"
    if state.collected.eleven_labs_key:
        voice_mode = "elevenlabs"
    elif "voice" in state.completed_steps:
        voice_mode = "macos-say"

    return InstallSummary(
        pai_version="4.0.0",
        principal_name=state.collected.principal_name or "User",
        ai_name=state.collected.ai_name or "PAI",
        timezone=state.collected.timezone or "UTC",
        voice_enabled="voice" in state.completed_steps,
        voice_mode=voice_mode,
        catchphrase=state.collected.catchphrase or "",
        install_type=state.install_type or "fresh",
        completed_steps=len(state.completed_steps),
        total_steps=8,
    )
