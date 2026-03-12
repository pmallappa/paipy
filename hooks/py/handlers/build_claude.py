#!/usr/bin/env python3
"""
build_claude.py -- SessionStart hook handler.

Checks if CLAUDE.md needs rebuilding (algorithm version changed,
DA name changed, unresolved variables). If so, regenerates from template.

Current session uses the existing CLAUDE.md (already loaded).
Rebuild ensures the NEXT session gets the fresh version.

NOTE: This is a stub that logs a message. The actual BuildCLAUDE tool
(pai/tools/BuildCLAUDE.ts) has not been ported to Python yet.
"""

import sys


def handle_build_claude() -> None:
    """Check if CLAUDE.md needs rebuilding and rebuild if necessary."""
    # The actual build logic depends on pai/tools/BuildCLAUDE.ts
    # which is outside the hooks subsystem. This is a stub placeholder.
    try:
        # Import would come from pai/tools equivalent when ported
        print("[BuildCLAUDE] Python stub -- actual build logic not yet ported", file=sys.stderr)
    except Exception as e:
        print(f"[BuildCLAUDE] Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    handle_build_claude()
