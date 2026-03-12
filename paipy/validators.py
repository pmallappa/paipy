#!/usr/bin/env python3
"""
validators.py -- Validation for voice and tab title outputs.

Renamed from: output_validators.py
Wraps all validation functions in the Validators class.
"""

import re
from typing import Callable, List, Optional, Set


class Validators:
    """Validation utilities for voice completion and tab title outputs."""

    # ── Conversational filler -- always invalid for voice output ───────

    GARBAGE_PATTERNS = [
        re.compile(r"appreciate", re.IGNORECASE),
        re.compile(r"thank", re.IGNORECASE),
        re.compile(r"welcome", re.IGNORECASE),
        re.compile(r"help(ing)? you", re.IGNORECASE),
        re.compile(r"assist(ing)? you", re.IGNORECASE),
        re.compile(r"reaching out", re.IGNORECASE),
        re.compile(r"happy to", re.IGNORECASE),
        re.compile(r"let me know", re.IGNORECASE),
        re.compile(r"feel free", re.IGNORECASE),
    ]

    CONVERSATIONAL_STARTERS = [
        re.compile(r"^I'm ", re.IGNORECASE),
        re.compile(r"^I am ", re.IGNORECASE),
        re.compile(r"^Sure[,.]?", re.IGNORECASE),
        re.compile(r"^OK[,.]?", re.IGNORECASE),
        re.compile(r"^Got it[,.]?", re.IGNORECASE),
        re.compile(r"^Done\.?$", re.IGNORECASE),
        re.compile(r"^Yes[,.]?", re.IGNORECASE),
        re.compile(r"^No[,.]?", re.IGNORECASE),
        re.compile(r"^Okay[,.]?", re.IGNORECASE),
        re.compile(r"^Alright[,.]?", re.IGNORECASE),
    ]

    SINGLE_WORD_BLOCKLIST: Set[str] = {
        "ready", "done", "ok", "okay", "yes", "no", "sure",
        "hello", "hi", "hey", "thanks", "working", "processing",
    }

    # ── Incomplete endings for tab titles ─────────────────────────────

    INCOMPLETE_ENDINGS: Set[str] = {
        "the", "a", "an", "to", "for", "with", "of",
        "in", "on", "at", "by", "from", "into", "about",
        "and", "or", "but", "that", "which",
        "now", "then", "still", "also", "just", "only", "even",
        "very", "quite", "rather", "really", "here", "there",
    }

    # ── Irregular past tense map ──────────────────────────────────────

    IRREGULAR_PAST = {
        "building": "Built", "running": "Ran", "writing": "Wrote", "reading": "Read",
        "making": "Made", "finding": "Found", "getting": "Got", "setting": "Set",
        "doing": "Did", "sending": "Sent", "keeping": "Kept", "putting": "Put",
        "losing": "Lost", "telling": "Told", "understanding": "Understood",
    }

    # ── Voice Validation ──────────────────────────────────────────────

    @staticmethod
    def is_valid_voice_completion(text: str) -> bool:
        """Check if a voice completion is valid for TTS."""
        if not text or len(text) < 10:
            return False
        word_count = len(text.strip().split())
        if word_count == 1:
            lower = re.sub(r"[^a-z]", "", text.lower())
            if lower in Validators.SINGLE_WORD_BLOCKLIST or len(lower) < 10:
                return False
        for p in Validators.GARBAGE_PATTERNS:
            if p.search(text):
                return False
        if len(text) < 40:
            if re.search(r"\bready\b", text, re.IGNORECASE) or re.search(r"\bhello\b", text, re.IGNORECASE):
                return False
        for p in Validators.CONVERSATIONAL_STARTERS:
            if p.search(text):
                return False
        return True

    @staticmethod
    def get_voice_fallback() -> str:
        """Intentionally empty -- invalid voice completions should be skipped, not spoken."""
        return ""

    # ── Tab Title Validation ──────────────────────────────────────────

    @staticmethod
    def _is_valid_title_base(text: str) -> tuple:
        """Shared base validation: 2-4 words, period, no garbage, no incomplete endings."""
        if not text or len(text) < 5:
            return (False, "")
        if not text.endswith("."):
            return (False, "")

        content = text[:-1].strip()
        words = content.split()
        if len(words) < 2 or len(words) > 4:
            return (False, "")

        first_word = words[0].lower()

        # Reject generic garbage
        if re.match(
            r"^(completed?|proces{1,2}e?d|processing|handled|handling|finished|finishing|worked|working|done|analyzed?) (the |on )?(task|request|work|it|input)$",
            content,
            re.IGNORECASE,
        ):
            return (False, first_word)

        # Reject first-person pronouns
        lower = content.lower()
        if re.search(r"\bi\b", lower) or re.search(r"\bme\b", lower) or re.search(r"\bmy\b", lower):
            return (False, first_word)

        # Reject dangling/incomplete endings
        last_word = re.sub(r"[^a-z]", "", words[-1].lower())
        if last_word in Validators.INCOMPLETE_ENDINGS:
            return (False, first_word)

        # Reject single-character last words
        if len(last_word) <= 1:
            return (False, first_word)

        # Reject long adverbs ending in "-ly"
        if last_word.endswith("ly") and len(last_word) > 5:
            return (False, first_word)

        return (True, first_word)

    @staticmethod
    def is_valid_working_title(text: str) -> bool:
        """Working-phase title: MUST start with gerund (-ing verb)."""
        valid, first_word = Validators._is_valid_title_base(text)
        if not valid:
            return False
        return first_word.endswith("ing")

    @staticmethod
    def is_valid_completion_title(text: str) -> bool:
        """Completion-phase title: must NOT start with gerund."""
        valid, first_word = Validators._is_valid_title_base(text)
        if not valid:
            return False
        if first_word.endswith("ing"):
            return False
        return True

    @staticmethod
    def is_valid_question_title(text: str) -> bool:
        """Question-phase title: noun phrase, no period, 1-4 words, max 30 chars."""
        if not text or not text.strip():
            return False
        if text.endswith("."):
            return False
        if len(text) > 30:
            return False
        words = text.strip().split()
        if len(words) < 1 or len(words) > 4:
            return False
        if re.search(r"<[^>]*>", text):
            return False
        return True

    # ── Progressive Title Trimming ────────────────────────────────────

    @staticmethod
    def trim_to_valid_title(
        words: List[str],
        validator: Callable[[str], bool],
        max_words: int = 4,
    ) -> Optional[str]:
        """
        Try progressively shorter word counts (from max_words down to 2) until valid.
        Returns the first valid title, or None if none work.
        """
        limit = min(len(words), max_words)
        for n in range(limit, 1, -1):
            candidate = " ".join(words[:n])
            candidate = re.sub(r"[,;:!?\-\u2014]+$", "", candidate).strip()
            if not candidate.endswith("."):
                candidate += "."
            if validator(candidate):
                return candidate
        return None

    # ── Fallbacks ─────────────────────────────────────────────────────

    @staticmethod
    def get_working_fallback() -> str:
        return "Analyzing input."

    @staticmethod
    def get_completion_fallback() -> str:
        return "Task complete."

    @staticmethod
    def get_question_fallback() -> str:
        return "Awaiting input"

    # ── Past Tense Conversion ─────────────────────────────────────────

    @staticmethod
    def gerund_to_past_tense(gerund: str) -> str:
        """Convert a gerund to past tense: 'Fixing' -> 'Fixed', 'Building' -> 'Built'."""
        lower = gerund.lower()

        if lower in Validators.IRREGULAR_PAST:
            return Validators.IRREGULAR_PAST[lower]

        if not lower.endswith("ing") or len(lower) < 5:
            return gerund

        stem = lower[:-3]
        result = stem + "ed"
        return result[0].upper() + result[1:]
