"""
PAI Installer v4.0 -- CLI Wizard
Interactive command-line installation experience.
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List

from engine.types import EngineEvent, InstallState, StepId
from engine.steps import STEPS, get_progress
from engine.state import (
    create_fresh_state,
    has_saved_state,
    load_state,
    save_state,
    clear_state,
    complete_step,
)
from engine.actions import (
    run_system_detect,
    run_prerequisites,
    run_api_keys,
    run_identity,
    run_repository,
    run_configuration,
    run_voice_setup,
)
from engine.validate import run_validation, generate_summary
from cli.display import (
    print_banner,
    print_step,
    print_detection,
    print_validation,
    print_summary,
    print_text,
    print_success,
    print_error,
    print_warning,
    print_info,
    progress_bar,
    c,
)
from cli.prompts import prompt_text, prompt_secret, prompt_choice, prompt_confirm


def _create_event_handler():
    """Handle engine events in CLI mode."""

    async def handler(event: EngineEvent) -> None:
        event_type = event.get("event")

        if event_type == "step_start":
            pass  # Handled by the main loop with print_step
        elif event_type == "step_complete":
            print_success("Step complete")
        elif event_type == "step_skip":
            print_info(f"Skipped: {event.get('reason', '')}")
        elif event_type == "step_error":
            print_error(f"Error: {event.get('error', '')}")
        elif event_type == "progress":
            print_text(f"  {progress_bar(event.get('percent', 0))} {c['gray']}{event.get('detail', '')}{c['reset']}")
        elif event_type == "message":
            print_text(f"\n  {event.get('content', '')}\n")
        elif event_type == "error":
            print_error(event.get("message", ""))

    return handler


async def _get_input(
    id: str,
    prompt: str,
    input_type: str,
    placeholder: str = "",
) -> str:
    """CLI input adapter -- bridges engine's input requests to readline prompts."""
    if input_type in ("key", "password"):
        return await prompt_secret(prompt, placeholder)
    return await prompt_text(prompt, placeholder)


async def _get_choice(
    id: str,
    prompt: str,
    choices: List[Dict[str, str]],
) -> str:
    """CLI choice adapter."""
    return await prompt_choice(prompt, choices)


async def run_cli() -> None:
    """Run the full CLI installation wizard."""
    print_banner()

    emit = _create_event_handler()

    # Check for resume
    state: InstallState

    if has_saved_state():
        saved = load_state()
        if saved:
            print_text(f"  {c['yellow']}Found previous installation in progress.{c['reset']}")
            print_text(f"  {c['gray']}Started: {saved.started_at}{c['reset']}")
            print_text(f"  {c['gray']}Progress: {get_progress(saved)}% ({len(saved.completed_steps)} steps completed){c['reset']}")
            print_text("")

            resume = await prompt_confirm("Resume previous installation?")
            if resume:
                state = saved
                state.mode = "cli"
                print_text(f"\n  {c['green']}Resuming from step: {state.current_step}{c['reset']}\n")
            else:
                state = create_fresh_state("cli")
        else:
            state = create_fresh_state("cli")
    else:
        state = create_fresh_state("cli")

    try:
        # -- Step 1: System Detection --
        if "system-detect" not in state.completed_steps:
            step = STEPS[0]
            print_step(step.number, 8, step.name)
            detection = await run_system_detect(state, emit)
            print_detection(detection)
            complete_step(state, "system-detect")
            state.current_step = "prerequisites"

        # -- Step 2: Prerequisites --
        if "prerequisites" not in state.completed_steps:
            step = STEPS[1]
            print_step(step.number, 8, step.name)
            await run_prerequisites(state, emit)
            complete_step(state, "prerequisites")
            state.current_step = "api-keys"

        # -- Step 3: API Keys --
        if "api-keys" not in state.completed_steps:
            step = STEPS[2]
            print_step(step.number, 8, step.name)
            await run_api_keys(state, emit, _get_input, _get_choice)
            complete_step(state, "api-keys")
            state.current_step = "identity"

        # -- Step 4: Identity --
        if "identity" not in state.completed_steps:
            step = STEPS[3]
            print_step(step.number, 8, step.name)
            await run_identity(state, emit, _get_input)
            complete_step(state, "identity")
            state.current_step = "repository"

        # -- Step 5: Repository --
        if "repository" not in state.completed_steps:
            step = STEPS[4]
            print_step(step.number, 8, step.name)
            await run_repository(state, emit)
            complete_step(state, "repository")
            state.current_step = "configuration"

        # -- Step 6: Configuration --
        if "configuration" not in state.completed_steps:
            step = STEPS[5]
            print_step(step.number, 8, step.name)
            await run_configuration(state, emit)
            complete_step(state, "configuration")
            state.current_step = "voice"

        # -- Step 7: Voice --
        if "voice" not in state.completed_steps and "voice" not in state.skipped_steps:
            step = STEPS[6]
            print_step(step.number, 8, step.name)
            await run_voice_setup(state, emit, _get_choice, _get_input)
            complete_step(state, "voice")
            state.current_step = "validation"

        # -- Step 8: Validation --
        if "validation" not in state.completed_steps:
            step = STEPS[7]
            print_step(step.number, 8, step.name)

            checks = await run_validation(state)
            print_validation(checks)

            all_critical = all(ch.passed for ch in checks if ch.critical)
            if all_critical:
                complete_step(state, "validation")
            else:
                print_error("\nSome critical checks failed. Please review and fix the issues above.")

        # -- Summary --
        summary = generate_summary(state)
        print_summary(summary)

        # Clean up state file on success
        clear_state()

        print_text(f"  {c['green']}{c['bold']}Installation complete!{c['reset']}")
        print_text(f"  {c['gray']}Run {c['bold']}source ~/.zshrc && pai{c['reset']}{c['gray']} to launch PAI.{c['reset']}")
        print_text("")

        sys.exit(0)
    except Exception as error:
        print_error(f"\nInstallation failed: {error}")
        print_info("Your progress has been saved. Run the installer again to resume.")
        save_state(state)
        sys.exit(1)
