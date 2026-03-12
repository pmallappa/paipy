"""Settings singleton — centralized access to settings.json.

Consolidates identity loading, principal info, and raw settings access
into a single cached object. Replaces the old identity.py module-level
functions with a proper singleton pattern.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from ._paths import Paths


# ── Defaults ──────────────────────────────────────────────────────────────

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


# ── Dataclasses ───────────────────────────────────────────────────────────

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


# ── Singleton ─────────────────────────────────────────────────────────────

class Settings:
    """Singleton wrapper around settings.json with identity accessors."""

    _instance: Optional["Settings"] = None

    @classmethod
    def get(cls, path: Optional[Path] = None) -> "Settings":
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls(path=path)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear singleton (for testing)."""
        cls._instance = None

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or Paths.settings_file()
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        """Read and cache settings.json. Returns the dict."""
        try:
            if self._path.exists():
                self._data = json.loads(self._path.read_text())
            else:
                self._data = {}
        except Exception:
            self._data = {}
        return self._data

    def reload(self) -> Dict[str, Any]:
        """Force re-read from disk."""
        return self.load()

    def raw(self) -> Dict[str, Any]:
        """Return the full settings dict."""
        return self._data

    def counts(self) -> Dict[str, Any]:
        """Return the counts section of settings."""
        return self._data.get("counts", {})

    # ── Identity accessors ────────────────────────────────────────────────

    def identity(self) -> Identity:
        """Build Identity dataclass from settings."""
        daidentity = self._data.get("daidentity", {})
        env_da = self._data.get("env", {}).get("DA")

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

    def principal(self) -> Principal:
        """Build Principal dataclass from settings."""
        principal = self._data.get("principal", {})
        env_principal = self._data.get("env", {}).get("PRINCIPAL")

        return Principal(
            name=principal.get("name") or env_principal or DEFAULT_PRINCIPAL["name"],
            pronunciation=principal.get("pronunciation") or DEFAULT_PRINCIPAL["pronunciation"],
            timezone=principal.get("timezone") or DEFAULT_PRINCIPAL["timezone"],
        )

    # ── Convenience methods ───────────────────────────────────────────────

    def da_name(self) -> str:
        """Get just the DA name."""
        return self.identity().name

    def principal_name(self) -> str:
        """Get just the Principal name."""
        return self.principal().name

    def voice_id(self) -> str:
        """Get just the voice ID."""
        return self.identity().mainDAVoiceID

    def algorithm_voice(self) -> Optional[Dict[str, Any]]:
        """Get algorithm voice settings from daidentity.voices.algorithm."""
        voices = self._data.get("daidentity", {}).get("voices")
        if not voices or not voices.get("algorithm", {}).get("voiceId"):
            return None
        return voices["algorithm"]

    def voice_prosody(self) -> Optional[VoiceProsody]:
        """Get voice prosody settings."""
        return self.identity().voice

    def voice_personality(self) -> Optional[VoicePersonality]:
        """Get voice personality settings."""
        return self.identity().personality
