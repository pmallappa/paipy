#!/usr/bin/env python3
"""
add-bg - Add Background Color CLI

Add a solid background color to transparent PNG images.
Part of the Images skill for PAI system.

Usage:
  python AddBg.py input.png "#EAE9DF" output.png
  python AddBg.py input.png --brand output.png

@see ~/.claude/skills/images/SKILL.md
"""

import re
import subprocess
import sys
from pathlib import Path

# Brand background color for thumbnails/social previews
BRAND_COLOR = "#EAE9DF"


def show_help() -> None:
    print("""
add-bg - Add Background Color CLI

Add a solid background color to transparent PNG images using ImageMagick.

USAGE:
  python AddBg.py <input> <color> <output>
  python AddBg.py <input> --brand <output>

ARGUMENTS:
  input       Path to transparent PNG image
  color       Hex color code (e.g., "#EAE9DF") OR --brand
  output      Path to save result

OPTIONS:
  --brand     Use brand color (#EAE9DF) for thumbnails

EXAMPLES:
  # Add brand background for thumbnail
  python AddBg.py header.png --brand header-thumb.png

  # Add custom background color
  python AddBg.py header.png "#FFFFFF" header-white.png

  # Add dark background
  python AddBg.py logo.png "#1a1a1a" logo-dark.png

REQUIREMENTS:
  ImageMagick must be installed (magick command)

BRAND COLOR:
  #EAE9DF - Sepia/cream background for social previews

ERROR CODES:
  0  Success
  1  Error (file not found, invalid color, ImageMagick error)
""")
    sys.exit(0)


def validate_hex_color(color: str) -> bool:
    return bool(re.match(r"^#[0-9A-Fa-f]{6}$", color))


def add_background(input_path: str, hex_color: str, output_path: str) -> None:
    if not Path(input_path).exists():
        print(f"File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if not validate_hex_color(hex_color):
        print(f"Invalid hex color: {hex_color}", file=sys.stderr)
        print('   Must be in format #RRGGBB (e.g., "#EAE9DF")', file=sys.stderr)
        sys.exit(1)

    print(f"Adding background {hex_color} to {input_path}")

    command = ["magick", input_path, "-background", hex_color, "-flatten", output_path]

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        print(f"Saved: {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"ImageMagick error: {e.stderr or e}", file=sys.stderr)
        print("   Make sure ImageMagick is installed: brew install imagemagick", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("ImageMagick not found. Install it: brew install imagemagick", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]

    if not args or "--help" in args or "-h" in args:
        show_help()

    if len(args) < 3:
        print("Missing arguments", file=sys.stderr)
        print("   Usage: python AddBg.py <input> <color|--brand> <output>", file=sys.stderr)
        sys.exit(1)

    input_path = args[0]
    color_arg = args[1]
    output_path = args[2]

    hex_color = BRAND_COLOR if color_arg == "--brand" else color_arg

    add_background(input_path, hex_color, output_path)


if __name__ == "__main__":
    main()
