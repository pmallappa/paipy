#!/usr/bin/env python3
"""
identity.py -- Central Identity Loader.

Single source of truth for DA (Digital Assistant) and Principal identity.
Reads from settings.json. All hooks and tools should import from here.
"""

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


HOME = os.environ.get("HOME", str(Path.home()))
_PAI_DIR = os.environ.get("PAI_DIR", os.path.join(HOME, ".claude"))
SETTINGS_PATH = os.path.join(_PAI_DIR, "settings.json")

# Default identity (fallback if settings.json doesn't have identity section)
DEFAULT_IDENTITY = {
    "name": "PAI",
    "fullName": "Personal AI",
    "displayName": "PAI",
    "mainDAVoiceID": "",
    "color": "#3B82F6",
}

DEFAULT_PRINCIPAL = {
    "name": "User",
    "pronunciation": "",
    "timezone": "UTC",
}


@dataclass
class VoiceProsody:
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    use_speaker_boost: bool = True


@dataclass
class VoicePersonality:
    baseVoice: str = ""
    enthusiasm: float = 0.0
    energy: float = 0.0
    expressiveness: float = 0.0
    resilience: float = 0.0
    composure: float = 0.0
    optimism: float = 0.0
    warmth: float = 0.0
    formality: float = 0.0
    directness: float = 0.0
    precision: float = 0.0
    curiosity: float = 0.0
    playfulness: float = 0.0


@dataclass
class Identity:
    name: str = "PAI"
    fullName: str = "Personal AI"
    displayName: str = "PAI"
    mainDAVoiceID: str = ""
    color: str = "#3B82F6"
    voice: Optional[VoiceProsody] = None
    personality: Optional[VoicePersonality] = None


@dataclass
class Principal:
    name: str = "User"
    pronunciation: str = ""
    timezone: str = "UTC"


_cached_settings: Optional[Dict[str, Any]] = None


def load_settings() -> Dict[str, Any]:
    """Load settings.json (cached)."""
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings

    try:
        if not os.path.exists(SETTINGS_PATH):
            _cached_settings = {}
            return _cached_settings
        content = Path(SETTINGS_PATH).read_text()
        _cached_settings = json.loads(content)
        return _cached_settings  # type: ignore
    except Exception:
        _cached_settings = {}
        return _cached_settings


def get_identity() -> Identity:
    """Get DA (Digital Assistant) identity from settings.json."""
    settings = load_settings()
    daidentity = settings.get("daidentity", {})
    env_da = settings.get("env", {}).get("DA")

    # Support both old and new voice structures
    voices = daidentity.get("voices", {})
    voice_config = voices.get("main") or daidentity.get("voice")

    voice = None
    if voice_config:
        voice = VoiceProsody(
            stability=voice_config.get("stability", 0.5),
            similarity_boost=voice_config.get("similarity_boost", 0.75),
            style=voice_config.get("style", 0.0),
            speed=voice_config.get("speed", 1.0),
            use_speaker_boost=voice_config.get("use_speaker_boost", True),
        )

    personality = None
    if daidentity.get("personality"):
        p = daidentity["personality"]
        personality = VoicePersonality(
            baseVoice=p.get("baseVoice", ""),
            enthusiasm=p.get("enthusiasm", 0.0),
            energy=p.get("energy", 0.0),
            expressiveness=p.get("expressiveness", 0.0),
            resilience=p.get("resilience", 0.0),
            composure=p.get("composure", 0.0),
            optimism=p.get("optimism", 0.0),
            warmth=p.get("warmth", 0.0),
            formality=p.get("formality", 0.0),
            directness=p.get("directness", 0.0),
            precision=p.get("precision", 0.0),
            curiosity=p.get("curiosity", 0.0),
            playfulness=p.get("playfulness", 0.0),
        )

    return Identity(
        name=daidentity.get("name") or env_da or DEFAULT_IDENTITY["name"],
        fullName=daidentity.get("fullName") or daidentity.get("name") or env_da or DEFAULT_IDENTITY["fullName"],
        displayName=daidentity.get("displayName") or daidentity.get("name") or env_da or DEFAULT_IDENTITY["displayName"],
        mainDAVoiceID=(
            (voice_config or {}).get("voiceId")
            or daidentity.get("voiceId")
            or daidentity.get("mainDAVoiceID")
            or DEFAULT_IDENTITY["mainDAVoiceID"]
        ),
        color=daidentity.get("color") or DEFAULT_IDENTITY["color"],
        voice=voice,
        personality=personality,
    )


def get_principal() -> Principal:
    """Get Principal (human owner) identity from settings.json."""
    settings = load_settings()
    principal = settings.get("principal", {})
    env_principal = settings.get("env", {}).get("PRINCIPAL")

    return Principal(
        name=principal.get("name") or env_principal or DEFAULT_PRINCIPAL["name"],
        pronunciation=principal.get("pronunciation") or DEFAULT_PRINCIPAL["pronunciation"],
        timezone=principal.get("timezone") or DEFAULT_PRINCIPAL["timezone"],
    )


def clear_cache() -> None:
    """Clear cache (useful for testing or when settings.json changes)."""
    global _cached_settings
    _cached_settings = None


def get_da_name() -> str:
    """Get just the DA name (convenience function)."""
    return get_identity().name


def get_principal_name() -> str:
    """Get just the Principal name (convenience function)."""
    return get_principal().name


def get_voice_id() -> str:
    """Get just the voice ID (convenience function)."""
    return get_identity().mainDAVoiceID


def get_settings() -> Dict[str, Any]:
    """Get the full settings object (for advanced use)."""
    return load_settings()


def get_default_identity() -> Identity:
    """Get the default identity (for documentation/testing)."""
    return Identity(**DEFAULT_IDENTITY)


def get_default_principal() -> Principal:
    """Get the default principal (for documentation/testing)."""
    return Principal(**DEFAULT_PRINCIPAL)


def get_algorithm_voice() -> Optional[Dict[str, Any]]:
    """
    Get algorithm voice settings from settings.json -> daidentity.voices.algorithm.
    Returns dict with voiceId, voiceName, stability, etc. or None if not configured.
    """
    settings = load_settings()
    voices = settings.get("daidentity", {}).get("voices")
    if not voices or not voices.get("algorithm", {}).get("voiceId"):
        return None
    return voices["algorithm"]


def get_voice_prosody() -> Optional[VoiceProsody]:
    """Get voice prosody settings (convenience function) - legacy ElevenLabs."""
    return get_identity().voice


def get_voice_personality() -> Optional[VoicePersonality]:
    """Get voice personality settings (convenience function) - Qwen3-TTS."""
    return get_identity().personality
