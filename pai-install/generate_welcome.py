#!/usr/bin/env python3
"""
PAI Installer v4.0 -- Welcome MP3 Generator
Uses ElevenLabs API to generate the welcome audio with a voice clone.

Usage: python generate_welcome.py

Requires: ELEVENLABS_API_KEY environment variable
Uses voice clone ID from settings.json principal.voiceClone
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "public" / "assets" / "welcome.mp3"


def _get_voice_id() -> str:
    """
    Determine the voice ID to use.
    Priority: env var -> settings.json voiceClone -> settings.json DA voice -> default.
    """
    # Environment variable takes priority
    env_voice = os.environ.get("ELEVENLABS_VOICE_ID")
    if env_voice:
        return env_voice

    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)

            # Use principal's voice clone (the installer speaks in the user's voice)
            clone = settings.get("principal", {}).get("voiceClone")
            if isinstance(clone, str):
                return clone
            if isinstance(clone, dict) and isinstance(clone.get("voiceId"), str):
                return clone["voiceId"]

            # Fallback to DA main voice
            main_voice = (
                settings.get("daidentity", {})
                .get("voices", {})
                .get("main", {})
                .get("voiceId")
            )
            if isinstance(main_voice, str):
                return main_voice
        except Exception:
            pass

    # Fallback to a default ElevenLabs voice (Adam)
    return "pNInz6obpgDQGcFmaJgB"


def generate_welcome() -> None:
    """Generate the welcome audio file using ElevenLabs TTS."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")

    if not api_key:
        # Try to read from config
        env_path = Path.home() / ".config" / "PAI" / ".env"
        if env_path.exists():
            try:
                env_content = env_path.read_text()
                for line in env_content.splitlines():
                    if line.startswith("ELEVENLABS_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
            except Exception:
                pass

    if not api_key:
        print("Error: ELEVENLABS_API_KEY not found in environment or ~/.config/pai/.env", file=sys.stderr)
        print("Set it with: export ELEVENLABS_API_KEY=your-key-here", file=sys.stderr)
        sys.exit(1)

    voice_id = _get_voice_id()
    text = 'Welcome to Personal AI Infrastructure. <break time="1.0s" /> Magnifying human capabilities.'

    print("Generating welcome audio...")
    print(f"  Voice ID: {voice_id}")
    print(f'  Text: "{text}"')
    print(f"  Output: {OUTPUT_PATH}")

    request_body = json.dumps({
        "text": text,
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.85,
            "similarity_boost": 0.9,
            "style": 0.1,
            "use_speaker_boost": True,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=request_body,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status != 200:
                error_text = response.read().decode("utf-8", errors="replace")
                print(f"ElevenLabs API error ({response.status}): {error_text}", file=sys.stderr)
                sys.exit(1)

            audio_data = response.read()
    except urllib.error.HTTPError as e:
        error_text = e.read().decode("utf-8", errors="replace") if e.fp else str(e)
        print(f"ElevenLabs API error ({e.code}): {error_text}", file=sys.stderr)
        sys.exit(1)

    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "wb") as f:
        f.write(audio_data)

    size_kb = round(len(audio_data) / 1024)
    print(f"\nWelcome audio generated: {OUTPUT_PATH} ({size_kb}KB)")


if __name__ == "__main__":
    try:
        generate_welcome()
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)
