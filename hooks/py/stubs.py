#!/usr/bin/env python3
"""
No-op stubs for hooks that depend on external systems not present:
  - Kitty terminal (tab titles/colors)
  - ElevenLabs TTS server (voice)
  - Doc integrity / cross-reference checks

Each stub reads stdin and exits 0 without error.
Symlinked or called by name via settings.json hooks.

Usage: python3 stubs.py
"""
import sys

# Read and discard stdin so Claude Code doesn't get a broken pipe
try:
    sys.stdin.read()
except Exception:
    pass

sys.exit(0)
