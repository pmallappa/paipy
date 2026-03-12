#!/usr/bin/env python3
"""
PAI Installer v4.0 -- Main Entry Point
Routes to CLI, Web server (for Electron), or GUI (Electron app).

Modes:
  --mode cli   -> Interactive terminal wizard
  --mode web   -> Start HTTP/WebSocket server (used internally by Electron)
  --mode gui   -> Launch Electron app (which spawns web mode internally)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def main() -> None:
    """Main entry point for the PAI installer."""
    parser = argparse.ArgumentParser(description="PAI Installer v4.0")
    parser.add_argument("--mode", choices=["cli", "web", "gui"], default="gui", help="Installation mode")
    args = parser.parse_args()

    if args.mode == "cli":
        # Run CLI wizard
        import asyncio
        from cli import run_cli

        asyncio.run(run_cli())

    elif args.mode == "web":
        # Start the HTTP + WebSocket server (Electron loads this)
        from web.server import start_server

        start_server()

    else:
        # Launch Electron GUI app
        electron_dir = ROOT / "electron"
        electron_pkg = electron_dir / "node_modules" / ".package-lock.json"

        # Install electron dependencies if needed
        if not electron_pkg.exists():
            print("Installing GUI dependencies (first run only)...\n")
            install = subprocess.run(
                ["npm", "install"],
                cwd=str(electron_dir),
            )
            if install.returncode != 0:
                print("Failed to install GUI dependencies. Falling back to CLI...\n", file=sys.stderr)
                import asyncio
                from cli import run_cli

                asyncio.run(run_cli())
                return

        # Clear macOS quarantine flags (prevents "app is damaged" error on copied installs)
        if sys.platform == "darwin":
            try:
                subprocess.run(
                    ["xattr", "-cr", str(electron_dir)],
                    capture_output=True,
                    timeout=30,
                )
                print("Cleared macOS quarantine flags.\n")
            except Exception:
                pass  # Non-fatal

        print("Starting PAI Installer GUI...\n")
        child = subprocess.Popen(
            ["npm", "start"],
            cwd=str(electron_dir),
        )

        try:
            exit_code = child.wait()
            sys.exit(exit_code or 0)
        except KeyboardInterrupt:
            child.terminate()
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as err:
        print(f"Fatal error: {err}", file=sys.stderr)
        sys.exit(1)
