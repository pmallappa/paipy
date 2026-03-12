#!/usr/bin/env python3
"""
remove-bg - Background Removal CLI

Remove backgrounds from images using the remove.bg API.
Part of the Images skill for PAI system.

Usage:
  remove-bg input.png                    # Overwrites original
  remove-bg input.png output.png         # Saves to new file
  remove-bg file1.png file2.png file3.png # Batch process

Environment:
  REMOVEBG_API_KEY    Required - Get from https://www.remove.bg/api
"""

import os
import sys
from pathlib import Path

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


# ============================================================================
# Environment Loading
# ============================================================================


def load_env() -> None:
    """Load .env file into environment."""
    env_path = (
        Path(os.environ["PAI_CONFIG_DIR"]) / ".env"
        if os.environ.get("PAI_CONFIG_DIR")
        else Path.home() / ".config" / "PAI" / ".env"
    )
    try:
        for line in env_path.read_text().splitlines():
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("#"):
                continue
            eq_index = trimmed.find("=")
            if eq_index == -1:
                continue
            key = trimmed[:eq_index].strip()
            value = trimmed[eq_index + 1:].strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
    except FileNotFoundError:
        pass


# ============================================================================
# Help
# ============================================================================


def show_help() -> None:
    print("""
remove-bg - Background Removal CLI

Remove backgrounds from images using the remove.bg API.

USAGE:
  remove-bg <input> [output]           Single file
  remove-bg <file1> <file2> ...        Batch process (overwrites originals)

ARGUMENTS:
  input     Path to image file (PNG, JPG, JPEG, WebP)
  output    Optional output path (defaults to overwriting input)

EXAMPLES:
  # Remove background, overwrite original
  remove-bg header.png

  # Remove background, save to new file
  remove-bg header.png header-transparent.png

  # Batch process multiple files
  remove-bg diagram1.png diagram2.png diagram3.png

ENVIRONMENT:
  REMOVEBG_API_KEY    Required - Get from https://www.remove.bg/api

ERROR CODES:
  0  Success
  1  Error (missing API key, file not found, API error)
""")
    sys.exit(0)


# ============================================================================
# Background Removal
# ============================================================================


def remove_background(input_path: str, output_path: str | None = None) -> None:
    if httpx is None:
        print("Error: httpx is required. Install with: pip install httpx", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("REMOVEBG_API_KEY")
    if not api_key:
        print("Error: Missing environment variable: REMOVEBG_API_KEY", file=sys.stderr)
        print("   Add it to your .env or export it in your shell", file=sys.stderr)
        sys.exit(1)

    if not Path(input_path).exists():
        print(f"Error: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output = output_path or input_path
    print(f"Removing background: {input_path}")

    try:
        image_data = Path(input_path).read_bytes()

        response = httpx.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": api_key},
            files={"image_file": ("image.png", image_data)},
            data={"size": "auto"},
            timeout=60,
        )

        if response.status_code != 200:
            print(f"Error: remove.bg API error: {response.status_code}", file=sys.stderr)
            print(f"   {response.text}", file=sys.stderr)
            sys.exit(1)

        Path(output).write_bytes(response.content)
        print(f"Saved: {output}")
    except Exception as e:
        print(f"Error processing {input_path}: {e}", file=sys.stderr)
        sys.exit(1)


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    load_env()

    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        show_help()

    # Single file with optional output
    if len(args) == 1:
        remove_background(args[0])
        return

    # Check if second arg is an output path or batch mode
    if len(args) == 2:
        if Path(args[1]).exists():
            # Both files exist - batch mode
            for file in args:
                remove_background(file)
        else:
            # Second arg is output path
            remove_background(args[0], args[1])
        return

    # Batch mode - multiple files
    print(f"Batch processing {len(args)} files...\n")
    success = 0
    failed = 0

    for file in args:
        try:
            remove_background(file)
            success += 1
        except SystemExit:
            failed += 1

    print(f"\nComplete: {success} succeeded, {failed} failed")


if __name__ == "__main__":
    main()
