"""
PAI Installer v4.0 -- API Routes
HTTP + WebSocket API for the web installer.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Dict, List, Optional, Set

from engine.types import (
    ClientMessage,
    EngineEvent,
    InstallState,
    ServerMessage,
    StepId,
)
from engine.detect import detect_system, validate_eleven_labs_key
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
from engine.state import (
    create_fresh_state,
    has_saved_state,
    load_state,
    save_state,
    clear_state,
    complete_step,
    skip_step,
)
from engine.steps import STEPS, get_progress, get_step_statuses


# -- State -------------------------------------------------------------------

install_state: Optional[InstallState] = None
ws_clients: Set[Any] = set()
message_history: List[ServerMessage] = []
pending_requests: Dict[str, Dict[str, Any]] = {}


# -- Broadcasting -------------------------------------------------------------


def broadcast(msg: ServerMessage) -> None:
    """Broadcast a message to all connected WebSocket clients."""
    raw = json.dumps(msg)
    message_history.append(msg)
    disconnected = set()
    for ws in ws_clients:
        try:
            asyncio.ensure_future(ws.send(raw))
        except Exception:
            disconnected.add(ws)
    ws_clients -= disconnected


# -- Engine Event -> WebSocket -------------------------------------------------


def _create_ws_emitter() -> Callable[[EngineEvent], Any]:
    """Create an event handler that broadcasts events over WebSocket."""

    async def emitter(event: EngineEvent) -> None:
        event_type = event.get("event")

        if event_type == "step_start":
            broadcast({"type": "step_update", "step": event["step"], "status": "active"})
        elif event_type == "step_complete":
            broadcast({"type": "step_update", "step": event["step"], "status": "completed"})
        elif event_type == "step_skip":
            broadcast({"type": "step_update", "step": event["step"], "status": "skipped", "detail": event.get("reason", "")})
        elif event_type == "step_error":
            broadcast({"type": "error", "message": event.get("error", ""), "step": event.get("step")})
        elif event_type == "progress":
            broadcast({"type": "progress", "step": event["step"], "percent": event["percent"], "detail": event["detail"]})
        elif event_type == "message":
            broadcast({"type": "message", "role": "assistant", "content": event["content"], "speak": event.get("speak")})
        elif event_type == "error":
            broadcast({"type": "error", "message": event.get("message", "")})

    return emitter


# -- Input Request Bridge ------------------------------------------------------


async def _request_input(
    id: str,
    prompt: str,
    input_type: str,
    placeholder: Optional[str] = None,
) -> str:
    """Request input from a connected client via WebSocket."""
    future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
    pending_requests[id] = {"future": future}
    broadcast({"type": "input_request", "id": id, "prompt": prompt, "inputType": input_type, "placeholder": placeholder})
    return await future


async def _request_choice(
    id: str,
    prompt: str,
    choices: List[Dict[str, str]],
) -> str:
    """Request a choice from a connected client via WebSocket."""
    future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
    pending_requests[id] = {"future": future}
    broadcast({"type": "choice_request", "id": id, "prompt": prompt, "choices": choices})
    return await future


# -- WebSocket Message Handler -------------------------------------------------


def handle_ws_message(ws: Any, raw: str) -> None:
    """Handle incoming WebSocket messages from clients."""
    global install_state

    try:
        msg: ClientMessage = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return

    msg_type = msg.get("type")

    if msg_type == "client_ready":
        # Replay message history
        for m in message_history:
            try:
                asyncio.ensure_future(ws.send(json.dumps({**m, "replayed": True})))
            except Exception:
                pass
        # Send current state
        if install_state:
            steps = get_step_statuses(install_state)
            for s in steps:
                try:
                    asyncio.ensure_future(ws.send(json.dumps({"type": "step_update", "step": s["id"], "status": s["status"]})))
                except Exception:
                    pass

    elif msg_type == "user_input":
        request_id = msg.get("requestId", "")
        pending = pending_requests.get(request_id)
        if pending and "future" in pending:
            pending["future"].set_result(msg.get("value", ""))
            del pending_requests[request_id]
            # Echo user message (masked for keys)
            value = msg.get("value", "")
            display = value[:8] + "..." if value.startswith(("sk-", "xi-")) else value
            if display:
                broadcast({"type": "message", "role": "system", "content": display})

    elif msg_type == "user_choice":
        request_id = msg.get("requestId", "")
        pending = pending_requests.get(request_id)
        if pending and "future" in pending:
            pending["future"].set_result(msg.get("value", ""))
            del pending_requests[request_id]

    elif msg_type == "start_install":
        if not install_state:
            asyncio.ensure_future(_start_installation())


# -- Installation Flow ---------------------------------------------------------


async def _start_installation() -> None:
    """Run the full installation flow."""
    global install_state

    # Always start fresh -- GUI should not silently resume stale state
    if has_saved_state():
        clear_state()
    install_state = create_fresh_state("web")

    emit = _create_ws_emitter()

    try:
        # Step 1: System Detection
        if "system-detect" not in install_state.completed_steps:
            await run_system_detect(install_state, emit)
            broadcast({"type": "detection_result", "data": install_state.detection.__dict__ if install_state.detection else {}})
            complete_step(install_state, "system-detect")
            install_state.current_step = "prerequisites"

        # Step 2: Prerequisites
        if "prerequisites" not in install_state.completed_steps:
            await run_prerequisites(install_state, emit)
            complete_step(install_state, "prerequisites")
            install_state.current_step = "api-keys"

        # Step 3: API Keys
        if "api-keys" not in install_state.completed_steps:
            await run_api_keys(install_state, emit, _request_input, _request_choice)
            complete_step(install_state, "api-keys")
            install_state.current_step = "identity"

        # Step 4: Identity
        if "identity" not in install_state.completed_steps:
            await run_identity(install_state, emit, _request_input)
            complete_step(install_state, "identity")
            install_state.current_step = "repository"

        # Step 5: Repository
        if "repository" not in install_state.completed_steps:
            await run_repository(install_state, emit)
            complete_step(install_state, "repository")
            install_state.current_step = "configuration"

        # Step 6: Configuration
        if "configuration" not in install_state.completed_steps:
            await run_configuration(install_state, emit)
            complete_step(install_state, "configuration")
            install_state.current_step = "voice"

        # Step 7: Voice
        if "voice" not in install_state.completed_steps and "voice" not in install_state.skipped_steps:
            try:
                await run_voice_setup(install_state, emit, _request_choice, _request_input)
                if "voice" not in install_state.skipped_steps:
                    complete_step(install_state, "voice")
            except Exception as voice_err:
                broadcast({"type": "error", "message": f"Voice setup error: {voice_err}"})
                broadcast({"type": "message", "role": "assistant", "content": "Voice setup encountered an error. Continuing with installation..."})
                skip_step(install_state, "voice", str(voice_err))
            install_state.current_step = "validation"

        # Step 8: Validation
        broadcast({"type": "step_update", "step": "validation", "status": "active"})
        checks = await run_validation(install_state)
        broadcast({"type": "validation_result", "checks": [{"name": ch.name, "passed": ch.passed, "detail": ch.detail, "critical": ch.critical} for ch in checks]})
        complete_step(install_state, "validation")
        broadcast({"type": "step_update", "step": "validation", "status": "completed"})

        summary = generate_summary(install_state)
        broadcast({
            "type": "install_complete",
            "success": True,
            "summary": {
                "paiVersion": summary.pai_version,
                "principalName": summary.principal_name,
                "aiName": summary.ai_name,
                "timezone": summary.timezone,
                "voiceEnabled": summary.voice_enabled,
                "voiceMode": summary.voice_mode,
                "catchphrase": summary.catchphrase,
                "installType": summary.install_type,
                "completedSteps": summary.completed_steps,
                "totalSteps": summary.total_steps,
            },
        })

        clear_state()
    except Exception as error:
        broadcast({"type": "error", "message": str(error)})
        if install_state:
            save_state(install_state)


# -- Connection Management ----------------------------------------------------


def add_client(ws: Any) -> None:
    """Add a WebSocket client."""
    ws_clients.add(ws)


def remove_client(ws: Any) -> None:
    """Remove a WebSocket client."""
    ws_clients.discard(ws)


def get_state() -> Optional[InstallState]:
    """Get current install state."""
    return install_state
