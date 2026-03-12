#!/usr/bin/env python3

"""
ComposeThumbnail - YouTube Thumbnail Composition CLI

Composites background, headshot, and text into a YouTube thumbnail.
Uses ImageMagick for all composition operations.

Features:
- Dynamic headshot positioning (left, center, right)
- Solid black backdrop boxes behind text for readability
- Full-height headshot that dominates the frame
- Colored border (Tokyo Night purple default)
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

# ============================================================================
# Types
# ============================================================================

HeadshotPosition = Literal["left", "center", "right"]


@dataclass
class CLIArgs:
    background: str
    headshot: str
    title: str
    subtitle: str
    output: str
    title_color: str = "#7dcfff"
    subtitle_color: str = "#FFFFFF"
    border_color: str = "#bb9af7"
    font: str = "Helvetica-Bold"
    headshot_position: HeadshotPosition = "left"


# ============================================================================
# Configuration
# ============================================================================

DEFAULTS = {
    "title_color": "#7dcfff",        # Tokyo Night cyan
    "subtitle_color": "#FFFFFF",
    "border_color": "#bb9af7",       # Tokyo Night Vivid Purple
    "font": "Helvetica-Bold",
    "headshot_position": "left",
    "output": f"{os.environ.get('HOME', str(Path.home()))}/Downloads/yt-thumbnail-{os.getpid()}.png",
}

LAYOUT = {
    "width": 1280,
    "height": 720,
    "border_width": 16,
    "title_size": 100,
    "subtitle_size": 50,
    "title_stroke": 4,
    "subtitle_stroke": 3,
    "text_padding": 6,
    "text_box_padding": 20,
    "headshot_max_width": 0.40,
    "text_zone_width": 0.55,
    "text_zone_gap": 0.05,
}

COLOR_PRESETS: dict[str, str] = {
    "white": "#FFFFFF",
    "cyan": "#7dcfff",
    "purple": "#bb9af7",
    "blue": "#7aa2f7",
    "magenta": "#ff007c",
    "yellow": "#e0af68",
    "green": "#9ece6a",
    "orange": "#ff9e64",
    "red": "#f7768e",
}


def resolve_color(color: str) -> str:
    preset = COLOR_PRESETS.get(color.lower())
    return preset if preset else color


# ============================================================================
# Error Handling
# ============================================================================


class CLIError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


# ============================================================================
# Helpers
# ============================================================================


def print_help() -> None:
    print("""
ComposeThumbnail - YouTube Thumbnail Composition CLI

USAGE:
  python ComposeThumbnail.py [OPTIONS]

REQUIRED:
  --background <path>     Background image (dramatic tech art)
  --headshot <path>       Headshot image (transparent background)
  --title <text>          Title text (max 6 words, auto-capitalized)
  --subtitle <text>       Subtitle text (max 12 words, auto-capitalized)

OPTIONAL:
  --output <path>         Output path (default: ~/Downloads/yt-thumbnail-{pid}.png)
  --position <pos>        Headshot position: left, center, right (default: left)
  --font <name>           Font name (default: Helvetica-Bold)
  --title-color <hex>     Title color (default: #7dcfff)
  --subtitle-color <hex>  Subtitle color (default: #FFFFFF)
  --border-color <hex>    Border color (default: #bb9af7)
  --help, -h              Show this help message

LAYOUT:
  Canvas:     1280x720 px
  Border:     16px colored border
  Headshot:   Full height inside border
  Text:       White text with stroke outlines
""")


def parse_args(argv: list[str]) -> CLIArgs:
    result: dict[str, str] = {}
    i = 0
    while i < len(argv):
        arg = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else None

        if arg in ("--help", "-h"):
            print_help()
            sys.exit(0)
        elif arg == "--background":
            result["background"] = nxt or ""
            i += 2
        elif arg == "--headshot":
            result["headshot"] = nxt or ""
            i += 2
        elif arg == "--title":
            result["title"] = nxt or ""
            i += 2
        elif arg == "--subtitle":
            result["subtitle"] = nxt or ""
            i += 2
        elif arg == "--output":
            result["output"] = nxt or ""
            i += 2
        elif arg == "--position":
            if nxt in ("left", "center", "right"):
                result["headshot_position"] = nxt
            i += 2
        elif arg == "--title-color":
            result["title_color"] = nxt or ""
            i += 2
        elif arg == "--subtitle-color":
            result["subtitle_color"] = nxt or ""
            i += 2
        elif arg == "--border-color":
            result["border_color"] = nxt or ""
            i += 2
        elif arg == "--font":
            result["font"] = nxt or ""
            i += 2
        else:
            i += 1

    # Validate required
    if "background" not in result:
        raise CLIError("--background is required")
    if "headshot" not in result:
        raise CLIError("--headshot is required")
    if "title" not in result:
        raise CLIError("--title is required")
    if "subtitle" not in result:
        raise CLIError("--subtitle is required")

    bg_path = str(Path(result["background"]).resolve())
    hs_path = str(Path(result["headshot"]).resolve())

    if not Path(bg_path).exists():
        raise CLIError(f"Background file not found: {bg_path}")
    if not Path(hs_path).exists():
        raise CLIError(f"Headshot file not found: {hs_path}")

    output = (
        str(Path(result["output"]).resolve()) if "output" in result else DEFAULTS["output"]
    )

    return CLIArgs(
        background=bg_path,
        headshot=hs_path,
        title=result["title"].upper(),
        subtitle=result["subtitle"].upper(),
        output=output,
        title_color=result.get("title_color", DEFAULTS["title_color"]),
        subtitle_color=result.get("subtitle_color", DEFAULTS["subtitle_color"]),
        border_color=result.get("border_color", DEFAULTS["border_color"]),
        font=result.get("font", DEFAULTS["font"]),
        headshot_position=result.get("headshot_position", DEFAULTS["headshot_position"]),  # type: ignore[arg-type]
    )


async def run_command(cmd: str, args: list[str]) -> str:
    proc = await asyncio.create_subprocess_exec(
        cmd, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise CLIError(
            f"Command failed: {cmd} {' '.join(args)}\n{stderr.decode()}",
            proc.returncode or 1,
        )
    return stdout.decode()


# ============================================================================
# Headshot Processing
# ============================================================================


async def crop_to_face_only(headshot_path: str, output_path: str) -> None:
    """Crop headshot to face only - removes shoulders/body and zooms into face."""
    dimensions = await run_command("magick", [
        "identify", "-format", "%wx%h", headshot_path
    ])
    w_str, h_str = dimensions.strip().split("x")
    width, height = int(w_str), int(h_str)

    await run_command("magick", [
        headshot_path,
        "-gravity", "north",
        "-crop", "100%x75%+0+0",
        "+repage",
        "-resize", "135%",
        "-gravity", "center",
        "-extent", f"{width}x{height}",
        output_path,
    ])


# ============================================================================
# Main Composition
# ============================================================================


async def compose_thumbnail(args: CLIArgs) -> None:
    output_dir = str(Path(args.output).parent)
    ts = os.getpid()

    resized_bg = f"{output_dir}/.yt-bg-{ts}.png"
    cropped_headshot = f"{output_dir}/.yt-cropped-{ts}.png"
    with_headshot = f"{output_dir}/.yt-headshot-{ts}.png"
    with_text = f"{output_dir}/.yt-text-{ts}.png"

    intermediates = [resized_bg, cropped_headshot, with_headshot, with_text]

    W = LAYOUT["width"]
    H = LAYOUT["height"]
    BW = LAYOUT["border_width"]

    try:
        print("Composing YouTube thumbnail...")

        # Step 1: Resize background
        print("   Resizing background to 1280x720...")
        await run_command("magick", [
            args.background,
            "-resize", f"{W}x{H}^",
            "-gravity", "center",
            "-extent", f"{W}x{H}",
            resized_bg,
        ])

        # Step 2: Crop headshot to face only
        print("   Cropping headshot to face only...")
        await crop_to_face_only(args.headshot, cropped_headshot)

        # Step 3: Composite headshot
        print(f"   Adding headshot ({args.headshot_position})...")
        headshot_height = H - (BW * 2)

        gravity_map: dict[str, tuple[str, str]] = {
            "left": ("west", "+20+0"),
            "center": ("center", "+0+0"),
            "right": ("east", "+20+0"),
        }
        gravity, geometry_offset = gravity_map.get(
            args.headshot_position, ("west", "+20+0")
        )

        await run_command("magick", [
            resized_bg,
            "(", cropped_headshot, "-resize", f"x{headshot_height}", ")",
            "-gravity", gravity,
            "-geometry", geometry_offset,
            "-composite",
            with_headshot,
        ])

        # Step 4: Add text with stroke outline
        print("   Adding text with stroke outlines...")

        title_color_resolved = resolve_color(args.title_color)
        subtitle_color_resolved = resolve_color(args.subtitle_color)

        if args.headshot_position == "center":
            title_img = f"{output_dir}/.yt-title-{ts}.png"
            subtitle_img = f"{output_dir}/.yt-subtitle-{ts}.png"
            intermediates.extend([title_img, subtitle_img])

            # Create title
            await run_command("magick", [
                "-size", "1400x200", "xc:transparent",
                "-font", args.font,
                "-pointsize", str(LAYOUT["title_size"]),
                "-gravity", "center",
                "-stroke", "#000000", "-strokewidth", str(LAYOUT["title_stroke"]),
                "-fill", "none", "-annotate", "+0+0", args.title,
                "-stroke", "none", "-fill", title_color_resolved,
                "-annotate", "+0+0", args.title,
                "-trim", "+repage", title_img,
            ])

            # Create subtitle
            await run_command("magick", [
                "-size", "1400x120", "xc:transparent",
                "-font", args.font,
                "-pointsize", str(LAYOUT["subtitle_size"]),
                "-gravity", "center",
                "-stroke", "#000000", "-strokewidth", str(LAYOUT["subtitle_stroke"]),
                "-fill", "none", "-annotate", "+0+0", args.subtitle,
                "-stroke", "none", "-fill", subtitle_color_resolved,
                "-annotate", "+0+0", args.subtitle,
                "-trim", "+repage", subtitle_img,
            ])

            with_title = f"{output_dir}/.yt-with-title-{ts}.png"
            intermediates.append(with_title)

            await run_command("magick", [
                with_headshot, title_img,
                "-gravity", "north", "-geometry", "+0+25",
                "-composite", with_title,
            ])

            await run_command("magick", [
                with_title, subtitle_img,
                "-gravity", "south", "-geometry", "+0+25",
                "-composite", with_text,
            ])

        else:
            # LEFT or RIGHT positioning
            text_zone_center = (
                round(W * 0.62) if args.headshot_position == "left"
                else round(W * 0.38)
            )

            title_img = f"{output_dir}/.yt-title-{ts}.png"
            subtitle_img = f"{output_dir}/.yt-subtitle-{ts}.png"
            intermediates.extend([title_img, subtitle_img])

            await run_command("magick", [
                "-size", "1400x200", "xc:transparent",
                "-font", args.font, "-gravity", "center",
                "-pointsize", str(LAYOUT["title_size"]),
                "-stroke", "#000000", "-strokewidth", str(LAYOUT["title_stroke"]),
                "-fill", "none", "-annotate", "+0+0", args.title,
                "-stroke", "none", "-fill", title_color_resolved,
                "-annotate", "+0+0", args.title,
                "-trim", "+repage", title_img,
            ])

            await run_command("magick", [
                "-size", "1400x120", "xc:transparent",
                "-font", args.font, "-gravity", "center",
                "-pointsize", str(LAYOUT["subtitle_size"]),
                "-stroke", "#000000", "-strokewidth", str(LAYOUT["subtitle_stroke"]),
                "-fill", "none", "-annotate", "+0+0", args.subtitle,
                "-stroke", "none", "-fill", subtitle_color_resolved,
                "-annotate", "+0+0", args.subtitle,
                "-trim", "+repage", subtitle_img,
            ])

            title_y = round(H / 2) - 80
            subtitle_y = round(H / 2) + 50

            with_title = f"{output_dir}/.yt-with-title-{ts}.png"
            intermediates.append(with_title)

            x_offset = text_zone_center - W // 2

            await run_command("magick", [
                with_headshot, title_img,
                "-gravity", "north",
                "-geometry", f"+{x_offset}+{title_y}",
                "-composite", with_title,
            ])

            await run_command("magick", [
                with_title, subtitle_img,
                "-gravity", "north",
                "-geometry", f"+{x_offset}+{subtitle_y}",
                "-composite", with_text,
            ])

        # Step 5: Add colored border
        print("   Adding border...")
        await run_command("magick", [
            with_text,
            "-bordercolor", args.border_color,
            "-border", str(BW),
            "-resize", f"{W}x{H}!",
            args.output,
        ])

        print(f"Thumbnail saved to {args.output}")

        identify = await run_command("magick", [
            "identify", "-format", "%wx%h", args.output
        ])
        print(f"   Dimensions: {identify.strip()}")

    finally:
        for f in intermediates:
            try:
                p = Path(f)
                if p.exists():
                    p.unlink()
            except Exception:
                pass


# ============================================================================
# Main
# ============================================================================


async def async_main() -> None:
    try:
        cli_args = parse_args(sys.argv[1:])
        await compose_thumbnail(cli_args)
    except CLIError as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(error.exit_code)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
