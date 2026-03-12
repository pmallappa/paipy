#!/usr/bin/env python3
"""
doc_integrity.py -- Check cross-refs if system docs/hooks were modified.

PURPOSE:
Runs deterministic doc integrity checks when system files (hooks, PAI docs,
skills, components) were modified during the session.
Self-gating: returns instantly when no system files changed.

TRIGGER: Stop

HANDLER: handlers/doc_cross_ref_integrity.py
"""

import json
import sys

from paipy import read_hook_input
from handlers.doc_cross_ref_integrity import handle_doc_cross_ref_integrity


def main() -> None:
    hook_input = read_hook_input()
    if not hook_input:
        sys.exit(0)

    try:
        handle_doc_cross_ref_integrity(
            transcript_path=hook_input.transcript_path,
            session_id=hook_input.session_id,
        )
    except Exception as e:
        print(f"[DocIntegrity] Handler failed: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[DocIntegrity] Fatal: {e}", file=sys.stderr)
        sys.exit(0)
