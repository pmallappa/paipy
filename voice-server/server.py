#!/usr/bin/env python3
"""
Voice Server - Personal AI Voice notification server using ElevenLabs TTS

Architecture: Pure pass-through. All voice config comes from settings.json.
Converted from Bun.serve to FastAPI + uvicorn.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

# Load .env from home
env_path = Path.home() / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and value:
                os.environ.setdefault(key, value)

PORT = int(os.environ.get("PORT", "8888"))
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")

if not ELEVENLABS_API_KEY:
    print("ELEVENLABS_API_KEY not found in ~/.env")

# ============================================================================
# Pronunciation System
# ============================================================================

compiled_rules: list[dict] = []

def load_pronunciations() -> None:
    pron_path = Path(__file__).parent / "pronunciations.json"
    if not pron_path.exists():
        print("No pronunciations.json found"); return
    try:
        config = json.loads(pron_path.read_text())
        for entry in config.get("replacements", []):
            pattern = re.compile(r"\b" + re.escape(entry["term"]) + r"\b")
            compiled_rules.append({"regex": pattern, "phonetic": entry["phonetic"]})
        print(f"Loaded {len(compiled_rules)} pronunciation rules")
    except Exception as e:
        print(f"Failed to load pronunciations.json: {e}")

def apply_pronunciations(text: str) -> str:
    result = text
    for rule in compiled_rules:
        result = rule["regex"].sub(rule["phonetic"], result)
    return result

load_pronunciations()

# ============================================================================
# Voice Configuration
# ============================================================================

FALLBACK_VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75, "style": 0.0, "speed": 1.0, "use_speaker_boost": True}
FALLBACK_VOLUME = 1.0

EMOTIONAL_PRESETS = {
    "excited": {"stability": 0.7, "similarity_boost": 0.9},
    "celebration": {"stability": 0.65, "similarity_boost": 0.85},
    "success": {"stability": 0.6, "similarity_boost": 0.8},
    "investigating": {"stability": 0.6, "similarity_boost": 0.85},
    "focused": {"stability": 0.7, "similarity_boost": 0.85},
    "urgent": {"stability": 0.3, "similarity_boost": 0.9},
}

voice_config: dict = {"defaultVoiceId": "", "voices": {}, "voicesByVoiceId": {}, "desktopNotifications": True}

def load_voice_config() -> dict:
    settings_path = Path.home() / ".claude" / "settings.json"
    try:
        if not settings_path.exists(): return voice_config
        settings = json.loads(settings_path.read_text())
        daidentity = settings.get("daidentity", {})
        voices_section = daidentity.get("voices", {})
        voices, by_id = {}, {}
        for name, cfg in voices_section.items():
            if cfg.get("voiceId"):
                entry = {"voiceId": cfg["voiceId"], "voiceName": cfg.get("voiceName"),
                         "stability": cfg.get("stability", 0.5), "similarity_boost": cfg.get("similarity_boost", 0.75),
                         "style": cfg.get("style", 0.0), "speed": cfg.get("speed", 1.0),
                         "use_speaker_boost": cfg.get("use_speaker_boost", True), "volume": cfg.get("volume", 1.0)}
                voices[name] = entry
                by_id[cfg["voiceId"]] = entry
        default_id = voices.get("main", {}).get("voiceId") or daidentity.get("mainDAVoiceID", "")
        print(f"Loaded {len(voices)} voice config(s)")
        return {"defaultVoiceId": default_id, "voices": voices, "voicesByVoiceId": by_id,
                "desktopNotifications": settings.get("notifications", {}).get("desktop", {}).get("enabled", True) is not False}
    except Exception as e:
        print(f"Failed to load voice config: {e}")
        return voice_config

voice_config = load_voice_config()
DEFAULT_VOICE_ID = voice_config["defaultVoiceId"] or os.environ.get("ELEVENLABS_VOICE_ID", "s3TPKV1kjDlVtZbl4Ksh")

# ============================================================================
# Sanitization and helpers
# ============================================================================

def sanitize_for_speech(text: str) -> str:
    cleaned = re.sub(r"<script", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"\.\.\//", "", cleaned)
    cleaned = re.sub(r"[;&|><`$\\]", "", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"#{1,6}\s+", "", cleaned)
    return cleaned.strip()[:500]

def extract_emotion(message: str) -> tuple[str, Optional[str]]:
    # Simple extraction - strip known emotion markers
    for emotion in EMOTIONAL_PRESETS:
        marker = f"[{emotion}]"
        if marker.lower() in message.lower():
            return message.replace(marker, "").strip(), emotion
    return message, None

# ============================================================================
# TTS + Audio
# ============================================================================

async def generate_speech(text: str, voice_id: str, settings: dict) -> bytes:
    if not ELEVENLABS_API_KEY:
        raise RuntimeError("ElevenLabs API key not configured")
    pronounced = apply_pronunciations(text)
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers={"Accept": "audio/mpeg", "Content-Type": "application/json", "xi-api-key": ELEVENLABS_API_KEY},
            json={"text": pronounced, "model_id": "eleven_turbo_v2_5", "voice_settings": settings})
        if resp.status_code != 200: raise RuntimeError(f"ElevenLabs API error: {resp.status_code}")
        return resp.content

async def play_audio(audio_data: bytes, volume: float = 1.0) -> None:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(audio_data)
        tmp = f.name
    try:
        proc = await asyncio.create_subprocess_exec("/usr/bin/afplay", "-v", str(volume), tmp)
        await proc.wait()
    finally:
        Path(tmp).unlink(missing_ok=True)

# ============================================================================
# Rate limiting
# ============================================================================

rate_counts: dict[str, dict] = {}
RATE_LIMIT, RATE_WINDOW = 10, 60

def check_rate_limit(ip: str) -> bool:
    now = time.time()
    rec = rate_counts.get(ip)
    if not rec or now > rec["reset"]:
        rate_counts[ip] = {"count": 1, "reset": now + RATE_WINDOW}; return True
    if rec["count"] >= RATE_LIMIT: return False
    rec["count"] += 1; return True

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(title="Voice Server")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost"], allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"])

async def send_notification(title: str, message: str, voice_enabled: bool = True, voice_id: str = None,
                            caller_settings: dict = None, caller_volume: float = None) -> dict:
    safe_message = sanitize_for_speech(message)
    cleaned, emotion = extract_emotion(safe_message)
    voice_played, voice_error = False, None

    if voice_enabled and ELEVENLABS_API_KEY:
        try:
            vid = voice_id or DEFAULT_VOICE_ID
            if caller_settings:
                settings = {**FALLBACK_VOICE_SETTINGS, **caller_settings}
                vol = caller_volume or FALLBACK_VOLUME
            else:
                entry = voice_config["voicesByVoiceId"].get(vid) or voice_config["voices"].get("main")
                if entry:
                    settings = {k: entry[k] for k in ["stability", "similarity_boost", "style", "speed", "use_speaker_boost"]}
                    vol = caller_volume or entry.get("volume", FALLBACK_VOLUME)
                else:
                    settings = dict(FALLBACK_VOICE_SETTINGS)
                    vol = caller_volume or FALLBACK_VOLUME
            if emotion and emotion in EMOTIONAL_PRESETS:
                settings.update(EMOTIONAL_PRESETS[emotion])
            audio = await generate_speech(cleaned, vid, settings)
            await play_audio(audio, vol)
            voice_played = True
        except Exception as e:
            voice_error = str(e)
    return {"voicePlayed": voice_played, "voiceError": voice_error}

@app.post("/notify")
async def notify(request: Request):
    ip = request.headers.get("x-forwarded-for", "localhost")
    if not check_rate_limit(ip): return JSONResponse({"status": "error", "message": "Rate limit exceeded"}, 429)
    data = await request.json()
    result = await send_notification(data.get("title", "PAI Notification"), data.get("message", "Task completed"),
        data.get("voice_enabled", True), data.get("voice_id"), data.get("voice_settings"), data.get("volume"))
    if data.get("voice_enabled", True) and not result["voicePlayed"] and result["voiceError"]:
        return JSONResponse({"status": "error", "message": f"TTS failed: {result['voiceError']}"}, 502)
    return JSONResponse({"status": "success", "message": "Notification sent"})

@app.post("/notify/personality")
async def notify_personality(request: Request):
    data = await request.json()
    await send_notification("PAI Notification", data.get("message", "Notification"), True)
    return JSONResponse({"status": "success", "message": "Personality notification sent"})

@app.post("/pai")
async def pai_notify(request: Request):
    data = await request.json()
    await send_notification(data.get("title", "PAI Assistant"), data.get("message", "Task completed"), True)
    return JSONResponse({"status": "success", "message": "PAI notification sent"})

@app.get("/health")
async def health():
    return JSONResponse({"status": "healthy", "port": PORT, "voice_system": "ElevenLabs",
        "default_voice_id": DEFAULT_VOICE_ID, "api_key_configured": bool(ELEVENLABS_API_KEY),
        "pronunciation_rules": len(compiled_rules), "configured_voices": list(voice_config["voices"].keys())})

@app.get("/")
async def root():
    return PlainTextResponse("Voice Server - POST to /notify, /notify/personality, or /pai")

def main():
    import uvicorn
    print(f"Voice Server running on port {PORT}")
    print(f"Using ElevenLabs TTS (default voice: {DEFAULT_VOICE_ID})")
    print(f"POST to http://localhost:{PORT}/notify")
    print(f"API Key: {'Configured' if ELEVENLABS_API_KEY else 'Missing'}")
    print(f"Pronunciations: {len(compiled_rules)} rules loaded")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
