#!/usr/bin/env python3
"""
integrity_check.py -- PAI Integrity Check (SessionEnd).

Runs system integrity check -- detects PAI system file changes,
spawns background maintenance.

TRIGGER: SessionEnd
PERFORMANCE: ~50ms (single transcript parse, one handler call). Non-blocking.
"""

import json
import sys

from paipy import read_hook_input
from handlers.system_integrity import handle_system_integrity


def main() -> None:
    hook_input = read_hook_input()
    if not hook_input or not hook_input.transcript_path:
        sys.exit(0)

    handle_system_integrity(
        session_id=hook_input.session_id,
        transcript_path=hook_input.transcript_path,
    )

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)
