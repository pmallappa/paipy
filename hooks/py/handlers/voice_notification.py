#!/usr/bin/env python3
"""
voice_notification.py -- Voice Notification Handler.

PURPOSE:
Sends completion messages to the voice server for TTS playback.
Extracts the voice line from responses and sends to ElevenLabs via voice server.

Pure handler: receives pre-parsed transcript data, sends to voice server.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from paipy import get_identity, get_iso_timestamp, is_valid_voice_completion, get_voice_fallback, memory


_pai_dir: Optional[str] = None


def _get_pai_dir() -> str:
    global _pai_dir
    if _pai_dir is None:
        raw = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))
        _pai_dir = os.path.expandvars(raw).replace("~", str(Path.home()))
    return _pai_dir


def _pai_path(*segments: str) -> str:
    return os.path.join(_get_pai_dir(), *segments)


DA_IDENTITY = None  # Lazy-loaded


def _get_da_identity():
    global DA_IDENTITY
    if DA_IDENTITY is None:
        DA_IDENTITY = get_identity()
    return DA_IDENTITY


def _get_active_work_dir() -> Optional[str]:
    try:
        current_work_path = memory("STATE") / "current-work.json"
        if not current_work_path.exists():
            return None
        content = current_work_path.read_text()
        state = json.loads(content)
        if state.get("work_dir"):
            work_path = memory("WORK") / state["work_dir"]
            if work_path.exists():
                return str(work_path)
    except Exception:
        pass
    return None


def _log_voice_event(event: Dict[str, Any]) -> None:
    line = json.dumps(event) + "\n"

    try:
        voice_dir = memory("VOICE")
        voice_log = str(voice_dir / "voice-events.jsonl")
        with open(voice_log, "a") as f:
            f.write(line)
    except Exception:
        pass

    try:
        work_dir = _get_active_work_dir()
        if work_dir:
            with open(os.path.join(work_dir, "voice.jsonl"), "a") as f:
                f.write(line)
    except Exception:
        pass


def _send_notification(payload: Dict[str, Any], session_id: str) -> None:
    identity = _get_da_identity()
    voice_id = payload.get("voice_id") or identity.mainDAVoiceID

    base_event = {
        "timestamp": get_iso_timestamp(),
        "session_id": session_id,
        "message": payload["message"],
        "character_count": len(payload["message"]),
        "voice_engine": "elevenlabs",
        "voice_id": voice_id,
    }

    try:
        req = urllib.request.Request(
            "http://localhost:8888/notify",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status >= 400:
                print(f"[Voice] Server error: {resp.status}", file=sys.stderr)
                _log_voice_event({
                    **base_event,
                    "event_type": "failed",
                    "status_code": resp.status,
                    "error": str(resp.status),
                })
            else:
                _log_voice_event({
                    **base_event,
                    "event_type": "sent",
                    "status_code": resp.status,
                })
    except Exception as e:
        print(f"[Voice] Failed to send: {e}", file=sys.stderr)
        _log_voice_event({
            **base_event,
            "event_type": "failed",
            "error": str(e),
        })


def handle_voice(voice_completion: str, session_id: str) -> None:
    """Handle voice notification with pre-parsed transcript data."""
    identity = _get_da_identity()

    # Validate voice completion
    if not is_valid_voice_completion(voice_completion):
        print(f'[Voice] Invalid completion: "{voice_completion[:50]}..."', file=sys.stderr)
        voice_completion = get_voice_fallback()

    # Skip empty or too-short messages
    if not voice_completion or len(voice_completion) < 5:
        print("[Voice] Skipping - message too short or empty", file=sys.stderr)
        return

    voice_id = identity.mainDAVoiceID
    voice_settings = identity.voice

    payload: Dict[str, Any] = {
        "message": voice_completion,
        "title": f"{identity.name} says",
        "voice_enabled": True,
        "voice_id": voice_id,
    }

    if voice_settings:
        payload["voice_settings"] = {
            "stability": voice_settings.stability,
            "similarity_boost": voice_settings.similarity_boost,
            "style": voice_settings.style,
            "speed": voice_settings.speed,
            "use_speaker_boost": voice_settings.use_speaker_boost,
        }

    _send_notification(payload, session_id)
