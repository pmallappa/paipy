#!/usr/bin/env python3
"""
voice_completion.py -- Send completion voice line to TTS server.

PURPOSE:
Extracts the voice line from Claude's response and sends it to
the ElevenLabs voice server for spoken playback.

TRIGGER: Stop

VOICE GATE: Only fires for main terminal sessions (not subagents).

HANDLER: handlers/voice_notification.py
"""

import os
import sys

from paipy import read_hook_input
from handlers.voice_notification import handle_voice


def _is_main_session() -> bool:
    """Voice gate: only main terminal sessions get voice."""
    return not os.environ.get("CLAUDE_CODE_AGENT_TASK_ID")


def main() -> None:
    hook_input = read_hook_input()
    if not hook_input:
        sys.exit(0)

    if not _is_main_session():
        print("[VoiceCompletion] Voice OFF (not main session)", file=sys.stderr)
        sys.exit(0)

    try:
        voice_completion = hook_input.last_assistant_message or ""
        handle_voice(voice_completion, hook_input.session_id)
    except Exception as e:
        print(f"[VoiceCompletion] Handler failed: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[VoiceCompletion] Fatal: {e}", file=sys.stderr)
        sys.exit(0)
