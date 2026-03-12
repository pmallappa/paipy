#!/usr/bin/env python3
"""
tab.py -- Unified tab state management for Kitty terminal.

Merged from: tab_constants.py + tab_setter.py
Provides TabState class with all tab title/color management and phase awareness.
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Set

from ._paths import Paths


# ── Type Aliases ──────────────────────────────────────────────────────────

TabStateName = Literal["thinking", "working", "question", "completed", "error", "idle"]

AlgorithmTabPhase = Literal[
    "OBSERVE", "THINK", "PLAN", "BUILD", "EXECUTE",
    "VERIFY", "LEARN", "COMPLETE", "IDLE",
]


class TabState:
    """Unified tab state setter and Kitty terminal integration."""

    # ── Color Constants ───────────────────────────────────────────────────

    TAB_COLORS: Dict[str, Dict[str, str]] = {
        "thinking":  {"inactiveBg": "#1E0A3C", "label": "purple"},
        "working":   {"inactiveBg": "#804000", "label": "orange"},
        "question":  {"inactiveBg": "#0D4F4F", "label": "teal"},
        "completed": {"inactiveBg": "#022800", "label": "green"},
        "error":     {"inactiveBg": "#804000", "label": "orange"},
        "idle":      {"inactiveBg": "none",    "label": "default"},
    }

    ACTIVE_TAB_BG = "#002B80"
    ACTIVE_TAB_FG = "#FFFFFF"
    INACTIVE_TAB_FG = "#A0A0A0"

    PHASE_TAB_CONFIG: Dict[str, Dict[str, str]] = {
        "OBSERVE":  {"symbol": "\U0001F441\uFE0F", "inactiveBg": "#0C2D48", "label": "observe",  "gerund": "Observing the user request."},
        "THINK":    {"symbol": "\U0001F9E0",        "inactiveBg": "#2D1B69", "label": "think",    "gerund": "Analyzing the problem space."},
        "PLAN":     {"symbol": "\U0001F4CB",        "inactiveBg": "#1E1B4B", "label": "plan",     "gerund": "Planning the execution approach."},
        "BUILD":    {"symbol": "\U0001F528",        "inactiveBg": "#78350F", "label": "build",    "gerund": "Building the solution artifacts."},
        "EXECUTE":  {"symbol": "\u26A1",            "inactiveBg": "#713F12", "label": "execute",  "gerund": "Executing the planned work."},
        "VERIFY":   {"symbol": "\u2705",            "inactiveBg": "#14532D", "label": "verify",   "gerund": "Verifying ideal state criteria."},
        "LEARN":    {"symbol": "\U0001F4DA",        "inactiveBg": "#134E4A", "label": "learn",    "gerund": "Recording the session learnings."},
        "COMPLETE": {"symbol": "\u2705",            "inactiveBg": "#022800", "label": "complete", "gerund": "Complete."},
        "IDLE":     {"symbol": "",                  "inactiveBg": "none",    "label": "idle",     "gerund": ""},
    }

    # Noise words to skip when extracting the session label
    SESSION_NOISE: Set[str] = {
        "the", "a", "an", "and", "or", "for", "to", "in", "on", "of", "with",
        "my", "our", "new", "old", "fix", "add", "update", "set", "get",
    }

    # ── Private Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _tab_titles_dir() -> str:
        return Paths.memory_str("STATE", "tab-titles")

    @staticmethod
    def _kitty_sessions_dir() -> str:
        return Paths.memory_str("STATE", "kitty-sessions")

    @staticmethod
    def _get_kitty_env(session_id: Optional[str] = None) -> Dict[str, Optional[str]]:
        """Get Kitty environment from env vars or persisted per-session file."""
        listen_on = os.environ.get("KITTY_LISTEN_ON")
        window_id = os.environ.get("KITTY_WINDOW_ID")
        if listen_on and window_id:
            return {"listenOn": listen_on, "windowId": window_id}

        # Per-session file lookup
        if session_id:
            try:
                session_path = os.path.join(TabState._kitty_sessions_dir(), f"{session_id}.json")
                if os.path.exists(session_path):
                    entry = json.loads(Path(session_path).read_text())
                    listen_on = listen_on or entry.get("listenOn")
                    window_id = window_id or entry.get("windowId")
                    if listen_on and window_id:
                        return {"listenOn": listen_on, "windowId": window_id}
            except Exception:
                pass

        # Fallback: default socket path
        if not listen_on:
            default_socket = f"/tmp/kitty-{os.environ.get('USER', '')}"
            try:
                if os.path.exists(default_socket):
                    listen_on = f"unix:{default_socket}"
            except Exception:
                pass

        if session_id and not listen_on and not window_id:
            print(
                f"[tab] getKittyEnv: no kitty env found for session {(session_id or '')[:8]}",
                file=sys.stderr,
            )

        return {"listenOn": listen_on, "windowId": window_id}

    @staticmethod
    def _cleanup_stale_state_files() -> None:
        """Clean up state files for kitty windows that no longer exist."""
        try:
            tab_dir = TabState._tab_titles_dir()
            if not os.path.isdir(tab_dir):
                return
            files = [f for f in os.listdir(tab_dir) if f.endswith(".json")]
            if not files:
                return

            default_socket = f"/tmp/kitty-{os.environ.get('USER', '')}"
            socket_path = os.environ.get("KITTY_LISTEN_ON") or (
                f"unix:{default_socket}" if os.path.exists(default_socket) else None
            )
            if not socket_path:
                return

            try:
                live_output = subprocess.check_output(
                    f'kitten @ --to="{socket_path}" ls 2>/dev/null | jq -r ".[].tabs[].windows[].id" 2>/dev/null',
                    shell=True,
                    timeout=2,
                    text=True,
                ).strip()
            except Exception:
                return

            if not live_output:
                return

            live_ids = set(live_output.split("\n"))
            for f in files:
                win_id = f.replace(".json", "")
                if win_id not in live_ids:
                    try:
                        os.unlink(os.path.join(tab_dir, f))
                    except Exception:
                        pass
        except Exception:
            pass

    # ── Public Methods ────────────────────────────────────────────────────

    @staticmethod
    def set_state(
        title: str,
        state: str,
        previous_title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """Set Kitty tab title and color."""
        colors = TabState.TAB_COLORS.get(state, TabState.TAB_COLORS["idle"])
        kitty_env = TabState._get_kitty_env(session_id)

        try:
            is_kitty = os.environ.get("TERM") == "xterm-kitty" or kitty_env.get("listenOn")
            if not is_kitty:
                return

            if not kitty_env.get("listenOn"):
                print("[tab] No kitty socket available, skipping tab update", file=sys.stderr)
                return

            to_args = ["--to=" + kitty_env["listenOn"]]
            print(f'[tab] Setting tab: "{title}" with toFlag: {to_args[0]}', file=sys.stderr)

            subprocess.run(
                ["kitten", "@"] + to_args + ["set-tab-title", title],
                capture_output=True, timeout=2,
            )
            subprocess.run(
                ["kitten", "@"] + to_args + ["set-window-title", title],
                capture_output=True, timeout=2,
            )

            if state == "idle":
                subprocess.run(
                    ["kitten", "@"] + to_args + [
                        "set-tab-color", "--self",
                        "active_bg=none", "active_fg=none",
                        "inactive_bg=none", "inactive_fg=none",
                    ],
                    capture_output=True, timeout=2,
                )
            else:
                subprocess.run(
                    ["kitten", "@"] + to_args + [
                        "set-tab-color", "--self",
                        f"active_bg={TabState.ACTIVE_TAB_BG}", f"active_fg={TabState.ACTIVE_TAB_FG}",
                        f"inactive_bg={colors['inactiveBg']}", f"inactive_fg={TabState.INACTIVE_TAB_FG}",
                    ],
                    capture_output=True, timeout=2,
                )
            print("[tab] Tab commands completed successfully", file=sys.stderr)
        except Exception as err:
            print(f"[tab] Error setting tab: {err}", file=sys.stderr)

        # Persist per-window state
        window_id = kitty_env.get("windowId")
        if not window_id:
            return

        try:
            tab_dir = TabState._tab_titles_dir()
            if state == "idle":
                state_path = os.path.join(tab_dir, f"{window_id}.json")
                if os.path.exists(state_path):
                    os.unlink(state_path)
            else:
                os.makedirs(tab_dir, exist_ok=True)
                state_data: Dict[str, Any] = {
                    "title": title,
                    "inactiveBg": colors["inactiveBg"],
                    "state": state,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                if previous_title:
                    state_data["previousTitle"] = previous_title
                Path(os.path.join(tab_dir, f"{window_id}.json")).write_text(json.dumps(state_data))
        except Exception:
            pass

        TabState._cleanup_stale_state_files()

    @staticmethod
    def read_state(session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Read per-window state file. Returns None if not found or invalid."""
        kitty_env = TabState._get_kitty_env(session_id)
        window_id = kitty_env.get("windowId")
        if not window_id:
            return None
        try:
            state_path = os.path.join(TabState._tab_titles_dir(), f"{window_id}.json")
            if not os.path.exists(state_path):
                return None
            raw = json.loads(Path(state_path).read_text())
            return {
                "title": raw.get("title", ""),
                "state": raw.get("state", "idle"),
                "previousTitle": raw.get("previousTitle"),
                "phase": raw.get("phase"),
            }
        except Exception:
            return None

    @staticmethod
    def strip_prefix(title: str) -> str:
        """Strip emoji prefix from a tab title to get raw text."""
        return re.sub(
            r"^(?:\U0001F9E0|\u2699\uFE0F|\u2699|\u2713|\u2753|\U0001F441\uFE0F|\U0001F4CB|\U0001F528|\u26A1|\u2705|\U0001F4DA)\s*",
            "",
            title,
        ).strip()

    @staticmethod
    def get_session_one_word(session_id: str) -> Optional[str]:
        """
        Extract up to 4 representative words from a session name.
        Returns uppercase. Filters noise words but keeps up to 4 meaningful ones.
        """
        try:
            names_path = Paths.memory_str("STATE", "session-names.json")
            if not os.path.exists(names_path):
                return None
            names = json.loads(Path(names_path).read_text())
            full_name = names.get(session_id)
            if not full_name:
                return None

            words = [w for w in full_name.split() if w]
            if not words:
                return None

            meaningful = [w for w in words if w.lower() not in TabState.SESSION_NOISE]
            if len(meaningful) >= 2:
                return " ".join(meaningful[:4]).upper()
            elif len(meaningful) == 1:
                idx = words.index(meaningful[0])
                nearby = [w for w in words[max(0, idx - 1):idx + 3] if w]
                return " ".join(nearby[:4]).upper()

            return " ".join(words[:4]).upper()
        except Exception:
            return None

    @staticmethod
    def set_phase(phase: str, session_id: str, summary: Optional[str] = None) -> None:
        """
        Set tab title and color for an Algorithm phase.
        Active format:    {SYMBOL} {ONE_WORD} | {PHASE}
        Complete format:  {ONE_WORD} | {summary}
        """
        config = TabState.PHASE_TAB_CONFIG.get(phase)
        if not config:
            return

        one_word = TabState.get_session_one_word(session_id) or "WORKING"
        kitty_env = TabState._get_kitty_env(session_id)

        # Build title based on phase
        if phase == "COMPLETE" and summary:
            title = f"\u2705 {summary}"
        elif phase == "COMPLETE":
            title = f"\u2705 {one_word}"
        elif phase == "IDLE":
            title = one_word
        else:
            existing_desc = ""
            current_state = TabState.read_state(session_id)
            if current_state and current_state.get("title"):
                pipe_idx = current_state["title"].find("|")
                if pipe_idx != -1:
                    existing_desc = current_state["title"][pipe_idx + 1:].strip()
            desc = existing_desc or config["gerund"]
            title = f"{config['symbol']} {one_word} | {desc}"

        try:
            is_kitty = os.environ.get("TERM") == "xterm-kitty" or kitty_env.get("listenOn")
            if not is_kitty:
                return

            if not kitty_env.get("listenOn"):
                print("[tab] No kitty socket available, skipping phase tab update", file=sys.stderr)
                return

            to_args = ["--to=" + kitty_env["listenOn"]]

            subprocess.run(
                ["kitten", "@"] + to_args + ["set-tab-title", title],
                capture_output=True, timeout=2,
            )
            subprocess.run(
                ["kitten", "@"] + to_args + ["set-window-title", title],
                capture_output=True, timeout=2,
            )

            if phase == "IDLE":
                subprocess.run(
                    ["kitten", "@"] + to_args + [
                        "set-tab-color", "--self",
                        "active_bg=none", "active_fg=none",
                        "inactive_bg=none", "inactive_fg=none",
                    ],
                    capture_output=True, timeout=2,
                )
            else:
                subprocess.run(
                    ["kitten", "@"] + to_args + [
                        "set-tab-color", "--self",
                        f"active_bg={TabState.ACTIVE_TAB_BG}", f"active_fg={TabState.ACTIVE_TAB_FG}",
                        f"inactive_bg={config['inactiveBg']}", f"inactive_fg={TabState.INACTIVE_TAB_FG}",
                    ],
                    capture_output=True, timeout=2,
                )
            print(f'[tab] Phase tab: "{title}" ({phase}, bg={config["inactiveBg"]})', file=sys.stderr)
        except Exception as err:
            print(f"[tab] Error setting phase tab: {err}", file=sys.stderr)

        # Persist per-window state
        window_id = kitty_env.get("windowId")
        if not window_id:
            return

        try:
            tab_dir = TabState._tab_titles_dir()
            os.makedirs(tab_dir, exist_ok=True)
            Path(os.path.join(tab_dir, f"{window_id}.json")).write_text(
                json.dumps({
                    "title": title,
                    "inactiveBg": config["inactiveBg"],
                    "state": "completed" if phase == "COMPLETE" else "working",
                    "phase": phase,
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                })
            )
        except Exception:
            pass

    @staticmethod
    def persist_session(session_id: str, listen_on: str, window_id: str) -> None:
        """Persist a session's Kitty environment for later hook lookups."""
        try:
            sessions_dir = TabState._kitty_sessions_dir()
            os.makedirs(sessions_dir, exist_ok=True)
            Path(os.path.join(sessions_dir, f"{session_id}.json")).write_text(
                json.dumps({"listenOn": listen_on, "windowId": window_id})
            )
        except Exception:
            pass

    @staticmethod
    def cleanup_session(session_id: str) -> None:
        """Remove a session's persisted Kitty environment file."""
        try:
            session_path = os.path.join(TabState._kitty_sessions_dir(), f"{session_id}.json")
            if os.path.exists(session_path):
                os.unlink(session_path)
        except Exception:
            pass
