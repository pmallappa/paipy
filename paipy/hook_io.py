"""HookIO — stdin reader and output helpers for Claude Code hooks.

Provides class-based interface for reading hook JSON payloads from stdin
and emitting structured decisions (allow/block/ask/inject).
"""

import json
import os
import sys
from dataclasses import dataclass
from typing import Optional


@dataclass
class HookInput:
    session_id: str = ""
    transcript_path: str = ""
    hook_event_name: str = ""
    last_assistant_message: Optional[str] = None


class HookIO:
    """Static methods for hook stdin reading and output emission."""

    @staticmethod
    def read() -> dict:
        """Read and parse JSON from stdin. Returns {} on failure."""
        try:
            raw = sys.stdin.read()
            return json.loads(raw) if raw.strip() else {}
        except Exception:
            return {}

    @staticmethod
    def read_structured() -> Optional[HookInput]:
        """Read stdin and parse into a HookInput dataclass. Returns None on failure."""
        try:
            raw = sys.stdin.read()
            if raw.strip():
                data = json.loads(raw)
                return HookInput(
                    session_id=data.get("session_id", ""),
                    transcript_path=data.get("transcript_path", ""),
                    hook_event_name=data.get("hook_event_name", ""),
                    last_assistant_message=data.get("last_assistant_message"),
                )
        except Exception as e:
            print(f"[hook-io] Error reading stdin: {e}", file=sys.stderr)
        return None

    @staticmethod
    def allow() -> None:
        """Emit non-blocking continue decision."""
        print(json.dumps({"continue": True}))

    @staticmethod
    def block(reason: str) -> None:
        """Emit hard-block decision and exit 0."""
        print(json.dumps({"decision": "block", "reason": reason}))
        sys.exit(0)

    @staticmethod
    def ask(reason: str) -> None:
        """Emit soft-block (ask user for confirmation) decision."""
        print(json.dumps({"decision": "ask", "reason": reason}))

    @staticmethod
    def inject(content: str) -> None:
        """Inject a <system-reminder> into context."""
        print(json.dumps({"type": "inject", "content": content}))

    @staticmethod
    def is_subagent() -> bool:
        """True when running inside an agent task, not the main session."""
        return bool(os.environ.get("CLAUDE_CODE_AGENT_TASK_ID"))


# ── Legacy aliases (backward compat for existing hooks) ───────────────────

def read_hook_input() -> Optional[HookInput]:
    """Legacy wrapper — prefer HookIO.read_structured()."""
    return HookIO.read_structured()
