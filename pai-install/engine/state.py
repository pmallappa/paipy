"""
PAI Installer v4.0 -- State Persistence
Manages install state to support resume from interruption.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.types import CollectedData, InstallState, StepId

STATE_FILE = os.path.join(
    os.environ.get("PAI_CONFIG_DIR", os.path.join(str(Path.home()), ".config", "PAI")),
    "install-state.json",
)


def create_fresh_state(mode: str) -> InstallState:
    """Create a fresh install state."""
    now = datetime.now(timezone.utc).isoformat()
    return InstallState(
        version="4.0.0",
        started_at=now,
        updated_at=now,
        current_step="system-detect",
        completed_steps=[],
        skipped_steps=[],
        mode=mode,
        detection=None,
        collected=CollectedData(),
        install_type=None,
        errors=[],
    )


def has_saved_state() -> bool:
    """Check if a saved state exists."""
    return os.path.exists(STATE_FILE)


def load_state() -> Optional[InstallState]:
    """
    Load saved install state from disk.
    Returns None if no state exists or it's corrupted.
    """
    if not os.path.exists(STATE_FILE):
        return None

    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)

        # Validate basic structure
        if not data.get("version") or not data.get("started_at") or not data.get("current_step"):
            return None

        # Reconstruct state from JSON
        collected = CollectedData(
            eleven_labs_key=data.get("collected", {}).get("elevenLabsKey"),
            principal_name=data.get("collected", {}).get("principalName"),
            timezone=data.get("collected", {}).get("timezone"),
            ai_name=data.get("collected", {}).get("aiName"),
            catchphrase=data.get("collected", {}).get("catchphrase"),
            projects_dir=data.get("collected", {}).get("projectsDir"),
            temperature_unit=data.get("collected", {}).get("temperatureUnit"),
            voice_type=data.get("collected", {}).get("voiceType"),
            custom_voice_id=data.get("collected", {}).get("customVoiceId"),
        )

        state = InstallState(
            version=data["version"],
            started_at=data["startedAt"],
            updated_at=data.get("updatedAt", ""),
            current_step=data["currentStep"],
            completed_steps=data.get("completedSteps", []),
            skipped_steps=data.get("skippedSteps", []),
            mode=data.get("mode", "cli"),
            detection=None,  # Detection is not persisted in full
            collected=collected,
            install_type=data.get("installType"),
            errors=[],
        )

        return state
    except Exception:
        return None


def _state_to_dict(state: InstallState) -> dict:
    """Convert state to a JSON-serializable dict."""
    return {
        "version": state.version,
        "startedAt": state.started_at,
        "updatedAt": state.updated_at,
        "currentStep": state.current_step,
        "completedSteps": state.completed_steps,
        "skippedSteps": state.skipped_steps,
        "mode": state.mode,
        "collected": {
            "elevenLabsKey": state.collected.eleven_labs_key,
            "principalName": state.collected.principal_name,
            "timezone": state.collected.timezone,
            "aiName": state.collected.ai_name,
            "catchphrase": state.collected.catchphrase,
            "projectsDir": state.collected.projects_dir,
            "temperatureUnit": state.collected.temperature_unit,
            "voiceType": state.collected.voice_type,
            "customVoiceId": state.collected.custom_voice_id,
        },
        "installType": state.install_type,
        "errors": [
            {
                "step": e.step,
                "message": e.message,
                "timestamp": e.timestamp,
                "recoverable": e.recoverable,
            }
            for e in state.errors
        ],
    }


def save_state(state: InstallState) -> None:
    """Save install state to disk."""
    state.updated_at = datetime.now(timezone.utc).isoformat()

    state_dir = os.path.dirname(STATE_FILE)
    os.makedirs(state_dir, exist_ok=True)

    data = _state_to_dict(state)

    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=2)

    # Set restrictive permissions
    os.chmod(STATE_FILE, 0o600)


def clear_state() -> None:
    """Remove saved state (after successful install)."""
    if os.path.exists(STATE_FILE):
        os.unlink(STATE_FILE)


def complete_step(state: InstallState, step: StepId) -> None:
    """Mark a step as completed and advance to the next."""
    if step not in state.completed_steps:
        state.completed_steps.append(step)
    save_state(state)


def skip_step(state: InstallState, step: StepId, reason: Optional[str] = None) -> None:
    """Mark a step as skipped."""
    if step not in state.skipped_steps:
        state.skipped_steps.append(step)
    save_state(state)


def record_error(
    state: InstallState,
    step: StepId,
    message: str,
    recoverable: bool = True,
) -> None:
    """Record an error for a step."""
    from engine.types import StepError

    state.errors.append(
        StepError(
            step=step,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            recoverable=recoverable,
        )
    )
    save_state(state)


def mask_key(key: str) -> str:
    """
    Mask API keys for safe logging/display.
    Shows first 8 chars and masks the rest.
    """
    if not key or len(key) <= 12:
        return "***"
    return key[:8] + "..." + key[-4:]
