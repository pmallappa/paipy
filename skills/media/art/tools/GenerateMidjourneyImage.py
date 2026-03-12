#!/usr/bin/env python3

"""
generate-midjourney-image - Midjourney Image Generation CLI

Generate images using Midjourney via Discord bot integration.
Follows llcli pattern for deterministic, composable CLI design.

Usage:
  python GenerateMidjourneyImage.py --prompt "..." --aspect-ratio 16:9 --output /tmp/image.png

@see ~/.claude/skills/art/SKILL.md
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from ..Lib.discord_bot import DiscordBotClient
from ..Lib.midjourney_client import MidjourneyClient, MidjourneyError

# ============================================================================
# Environment Loading
# ============================================================================


def load_env() -> None:
    """Load environment variables from $PAI_DIR/.env."""
    pai_dir = os.environ.get("PAI_DIR") or str(
        Path(os.environ.get("HOME", str(Path.home()))) / ".claude"
    )
    env_path = Path(pai_dir) / ".env"
    try:
        env_content = env_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return

    for line in env_content.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        eq_index = trimmed.find("=")
        if eq_index == -1:
            continue
        key = trimmed[:eq_index].strip()
        value = trimmed[eq_index + 1 :].strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value


# ============================================================================
# Types
# ============================================================================


class CLIArgs:
    def __init__(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
        version: str = "",
        stylize: int = 100,
        quality: float = 1,
        chaos: Optional[int] = None,
        weird: Optional[int] = None,
        tile: bool = False,
        output: str = "/tmp/midjourney-image.png",
        timeout: int = 120,
    ) -> None:
        self.prompt = prompt
        self.aspect_ratio = aspect_ratio
        self.version = version or os.environ.get("MIDJOURNEY_DEFAULT_VERSION", "6.1")
        self.stylize = stylize
        self.quality = quality
        self.chaos = chaos
        self.weird = weird
        self.tile = tile
        self.output = output
        self.timeout = timeout


# ============================================================================
# Configuration
# ============================================================================


DEFAULTS = {
    "aspect_ratio": "16:9",
    "version": os.environ.get("MIDJOURNEY_DEFAULT_VERSION", "6.1"),
    "stylize": int(os.environ.get("MIDJOURNEY_DEFAULT_STYLIZE", "100")),
    "quality": int(os.environ.get("MIDJOURNEY_DEFAULT_QUALITY", "1")),
    "tile": False,
    "output": "/tmp/midjourney-image.png",
    "timeout": 120,
}


# ============================================================================
# Error Handling
# ============================================================================


class CLIError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def handle_error(error: Exception) -> None:
    if isinstance(error, MidjourneyError):
        print(f"\nMidjourney Error: {error}", file=sys.stderr)
        print(f"   Type: {error.error_type}", file=sys.stderr)
        if error.original_prompt:
            print(f"   Prompt: {error.original_prompt}", file=sys.stderr)
        if error.suggestion:
            print(f"   Suggestion: {error.suggestion}", file=sys.stderr)
        sys.exit(1)

    if isinstance(error, CLIError):
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(error.exit_code)

    print(f"Unexpected error: {error}", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Help Text
# ============================================================================


def show_help() -> None:
    print(f"""
generate-midjourney-image - Midjourney Image Generation CLI

USAGE:
  python GenerateMidjourneyImage.py --prompt "<prompt>" [OPTIONS]

REQUIRED:
  --prompt <text>         Image generation prompt

OPTIONS:
  --aspect-ratio <ratio>  Aspect ratio (default: {DEFAULTS['aspect_ratio']})
  --version <version>     Midjourney version (default: {DEFAULTS['version']})
  --stylize <value>       Stylization 0-1000 (default: {DEFAULTS['stylize']})
  --quality <value>       Quality: 0.25, 0.5, 1, 2 (default: {DEFAULTS['quality']})
  --chaos <value>         Chaos 0-100 (optional)
  --weird <value>         Weird 0-3000 (optional)
  --tile                  Enable tiling mode
  --output <path>         Output file path (default: {DEFAULTS['output']})
  --timeout <seconds>     Max wait time (default: {DEFAULTS['timeout']})

ENVIRONMENT VARIABLES:
  DISCORD_BOT_TOKEN           Discord bot token (required)
  MIDJOURNEY_CHANNEL_ID       Channel ID for Midjourney (required)
  MIDJOURNEY_DEFAULT_VERSION  Default Midjourney version
  MIDJOURNEY_DEFAULT_QUALITY  Default quality setting
  MIDJOURNEY_DEFAULT_STYLIZE  Default stylize setting
""")


# ============================================================================
# Argument Parsing
# ============================================================================


def parse_args(argv: list[str]) -> CLIArgs:
    result: dict = {
        "aspect_ratio": DEFAULTS["aspect_ratio"],
        "version": DEFAULTS["version"],
        "stylize": DEFAULTS["stylize"],
        "quality": DEFAULTS["quality"],
        "tile": DEFAULTS["tile"],
        "output": DEFAULTS["output"],
        "timeout": DEFAULTS["timeout"],
    }

    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg in ("--help", "-h"):
            show_help()
            sys.exit(0)
        elif arg == "--prompt":
            result["prompt"] = argv[i + 1]
            i += 2
        elif arg in ("--aspect-ratio", "--ar"):
            result["aspect_ratio"] = argv[i + 1]
            i += 2
        elif arg in ("--version", "-v"):
            result["version"] = argv[i + 1]
            i += 2
        elif arg in ("--stylize", "-s"):
            result["stylize"] = int(argv[i + 1])
            i += 2
        elif arg in ("--quality", "-q"):
            result["quality"] = float(argv[i + 1])
            i += 2
        elif arg == "--chaos":
            result["chaos"] = int(argv[i + 1])
            i += 2
        elif arg == "--weird":
            result["weird"] = int(argv[i + 1])
            i += 2
        elif arg == "--tile":
            result["tile"] = True
            i += 1
        elif arg in ("--output", "-o"):
            result["output"] = argv[i + 1]
            i += 2
        elif arg == "--timeout":
            result["timeout"] = int(argv[i + 1])
            i += 2
        else:
            raise CLIError(f"Unknown argument: {arg}")

    if "prompt" not in result:
        raise CLIError("Missing required argument: --prompt")

    return CLIArgs(
        prompt=result["prompt"],
        aspect_ratio=result["aspect_ratio"],
        version=result["version"],
        stylize=result["stylize"],
        quality=result["quality"],
        chaos=result.get("chaos"),
        weird=result.get("weird"),
        tile=result["tile"],
        output=result["output"],
        timeout=result["timeout"],
    )


# ============================================================================
# Main
# ============================================================================


async def async_main() -> None:
    try:
        load_env()
        args = parse_args(sys.argv[1:])

        bot_token = os.environ.get("DISCORD_BOT_TOKEN")
        channel_id = os.environ.get("MIDJOURNEY_CHANNEL_ID")

        if not bot_token:
            raise CLIError(
                "Missing DISCORD_BOT_TOKEN environment variable. Add it to $PAI_DIR/.env"
            )
        if not channel_id:
            raise CLIError(
                "Missing MIDJOURNEY_CHANNEL_ID environment variable. Add it to $PAI_DIR/.env"
            )

        # Validate options
        MidjourneyClient.validate_options(
            prompt=args.prompt,
            aspect_ratio=args.aspect_ratio,
            version=args.version,
            stylize=args.stylize,
            quality=args.quality,
            chaos=args.chaos,
            weird=args.weird,
            timeout=args.timeout,
        )

        print("Midjourney Image Generation")
        print("=" * 55)
        print(f"Prompt: {args.prompt}")
        print(f"Aspect Ratio: {args.aspect_ratio}")
        print(f"Version: {args.version}")
        print(f"Stylize: {args.stylize}")
        print(f"Quality: {args.quality}")
        if args.chaos is not None:
            print(f"Chaos: {args.chaos}")
        if args.weird is not None:
            print(f"Weird: {args.weird}")
        if args.tile:
            print("Tile: enabled")
        print(f"Output: {args.output}")
        print(f"Timeout: {args.timeout}s")
        print("=" * 55 + "\n")

        discord_bot = DiscordBotClient(token=bot_token, channel_id=channel_id)
        midjourney_client = MidjourneyClient(discord_bot)

        try:
            await discord_bot.connect()

            result = await midjourney_client.generate_image(
                prompt=args.prompt,
                aspect_ratio=args.aspect_ratio,
                version=args.version,
                stylize=args.stylize,
                quality=args.quality,
                chaos=args.chaos,
                weird=args.weird,
                tile=args.tile,
                timeout=args.timeout,
            )

            await discord_bot.download_image(result["image_url"], args.output)

            print("\n" + "=" * 55)
            print("Success!")
            print(f"   Image URL: {result['image_url']}")
            print(f"   Saved to: {args.output}")
            print(f"   Message ID: {result['message_id']}")
            print("=" * 55 + "\n")

            await discord_bot.disconnect()
            sys.exit(0)

        except Exception:
            await discord_bot.disconnect()
            raise

    except Exception as error:
        handle_error(error)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
