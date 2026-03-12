"""
PAI Installer v4.0 -- Step Definitions
Defines the 8 installation steps, their dependencies, and conditions.
"""

from __future__ import annotations

from typing import List, Optional

from engine.types import InstallState, StepDefinition, StepId

STEPS: List[StepDefinition] = [
    StepDefinition(
        id="system-detect",
        name="System Detection",
        description="Detect operating system, installed tools, and existing PAI installation",
        number=1,
        required=True,
        depends_on=[],
    ),
    StepDefinition(
        id="prerequisites",
        name="Prerequisites",
        description="Install required tools: Git, Bun, Claude Code",
        number=2,
        required=True,
        depends_on=["system-detect"],
    ),
    StepDefinition(
        id="api-keys",
        name="API Keys",
        description="Find or collect ElevenLabs API key for voice features",
        number=3,
        required=True,
        depends_on=["prerequisites"],
    ),
    StepDefinition(
        id="identity",
        name="Identity",
        description="Configure your name, AI assistant name, timezone, and catchphrase",
        number=4,
        required=True,
        depends_on=["api-keys"],
    ),
    StepDefinition(
        id="repository",
        name="PAI Repository",
        description="Clone or update the PAI repository into ~/.claude",
        number=5,
        required=True,
        depends_on=["identity"],
    ),
    StepDefinition(
        id="configuration",
        name="Configuration",
        description="Generate settings.json, environment files, and directory structure",
        number=6,
        required=True,
        depends_on=["repository"],
    ),
    StepDefinition(
        id="voice",
        name="Digital Assistant Voice",
        description="Configure ElevenLabs key, select voice, start voice server, and test",
        number=7,
        required=True,
        depends_on=["configuration"],
    ),
    StepDefinition(
        id="validation",
        name="Validation",
        description="Verify installation completeness and show summary",
        number=8,
        required=True,
        depends_on=["voice"],
    ),
]


def get_step(step_id: StepId) -> StepDefinition:
    """Get a step definition by ID."""
    for step in STEPS:
        if step.id == step_id:
            return step
    raise ValueError(f"Unknown step: {step_id}")


def get_next_step(state: InstallState) -> Optional[StepDefinition]:
    """Get the next step to execute based on current state."""
    for step in STEPS:
        # Skip completed and skipped steps
        if step.id in state.completed_steps:
            continue
        if step.id in state.skipped_steps:
            continue

        # Check if condition allows this step
        if step.condition and not step.condition(state):
            continue

        # Check dependencies are met
        deps_ready = all(
            dep in state.completed_steps or dep in state.skipped_steps
            for dep in step.depends_on
        )
        if not deps_ready:
            continue

        return step

    return None  # All steps done


def get_step_statuses(state: InstallState) -> List[dict]:
    """Get all steps with their current status."""
    result = []
    for step in STEPS:
        if step.id in state.completed_steps:
            status = "completed"
        elif step.id in state.skipped_steps:
            status = "skipped"
        elif state.current_step == step.id:
            status = "active"
        elif step.condition and not step.condition(state):
            status = "skipped"
        else:
            status = "pending"

        result.append({
            "id": step.id,
            "name": step.name,
            "description": step.description,
            "number": step.number,
            "required": step.required,
            "depends_on": step.depends_on,
            "status": status,
        })
    return result


def get_progress(state: InstallState) -> int:
    """Calculate overall progress percentage."""
    applicable_steps = [
        s for s in STEPS if not s.condition or s.condition(state)
    ]
    done = [
        s
        for s in applicable_steps
        if s.id in state.completed_steps or s.id in state.skipped_steps
    ]
    if not applicable_steps:
        return 0
    return round((len(done) / len(applicable_steps)) * 100)
