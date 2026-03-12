#!/usr/bin/env python3

"""
generate - Image Generation CLI

Generate branded images using Flux 1.1 Pro, Nano Banana, Nano Banana Pro,
or GPT-image-1.
Follows llcli pattern for deterministic, composable CLI design.

Usage:
  python Generate.py --model nano-banana-pro --prompt "..." --size 16:9 --output /tmp/image.png

@see ~/.claude/skills/art/README.md
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import struct
import subprocess
import sys
from os.path import splitext
from pathlib import Path
from typing import Any, Literal, Optional

import httpx

# Optional SDK imports -- guarded so the module can still be imported for
# inspection even when the SDKs are not installed.
try:
    import replicate as _replicate_mod
except ImportError:
    _replicate_mod = None  # type: ignore[assignment]

try:
    import openai as _openai_mod
except ImportError:
    _openai_mod = None  # type: ignore[assignment]

try:
    from google import genai as _google_genai_mod
except ImportError:
    _google_genai_mod = None  # type: ignore[assignment]


# ============================================================================
# Types
# ============================================================================

Model = Literal["flux", "nano-banana", "nano-banana-pro", "gpt-image-1"]
ReplicateSize = Literal[
    "1:1", "16:9", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "21:9"
]
OpenAISize = Literal["1024x1024", "1536x1024", "1024x1536"]
GeminiSize = Literal["1K", "2K", "4K"]
Size = str  # Union of ReplicateSize | OpenAISize | GeminiSize


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
        # Remove surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        # Only set if not already defined
        if key not in os.environ:
            os.environ[key] = value


# ============================================================================
# Configuration
# ============================================================================

DEFAULTS_MODEL: Model = "flux"
DEFAULTS_SIZE: Size = "16:9"
DEFAULTS_OUTPUT = f"{os.environ.get('HOME', str(Path.home()))}/Downloads/generated-image.png"

REPLICATE_SIZES = ["1:1", "16:9", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "21:9"]
OPENAI_SIZES = ["1024x1024", "1536x1024", "1024x1536"]
GEMINI_SIZES = ["1K", "2K", "4K"]
GEMINI_ASPECT_RATIOS = [
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
]


# ============================================================================
# Error Handling
# ============================================================================


class CLIError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def handle_error(error: Exception) -> None:
    if isinstance(error, CLIError):
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(error.exit_code)
    print(f"Unexpected error: {error}", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Image Format Detection
# ============================================================================


def detect_image_format(
    data: bytes,
) -> Optional[dict[str, str]]:
    """Detect actual image format from magic bytes."""
    if len(data) < 12:
        return None
    if data[:4] == b"\x89PNG":
        return {"format": "png", "ext": ".png", "mime": "image/png"}
    if data[:3] == b"\xff\xd8\xff":
        return {"format": "jpeg", "ext": ".jpg", "mime": "image/jpeg"}
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return {"format": "webp", "ext": ".webp", "mime": "image/webp"}
    if data[:3] == b"GIF":
        return {"format": "gif", "ext": ".gif", "mime": "image/gif"}
    return None


def save_image(data: bytes, requested_path: str) -> str:
    """Save image data with correct file extension."""
    detected = detect_image_format(data)
    if detected:
        requested_ext = splitext(requested_path)[1].lower()
        if requested_ext and requested_ext != detected["ext"]:
            corrected_path = re.sub(r"\.[^.]+$", detected["ext"], requested_path)
            print(
                f"WARNING: API returned {detected['format'].upper()} data "
                f"(requested {requested_ext[1:].upper()}). "
                f"Saving as {corrected_path}"
            )
            Path(corrected_path).write_bytes(data)
            return corrected_path
    Path(requested_path).write_bytes(data)
    return requested_path


def detect_mime_type(file_path: str) -> str:
    """Detect MIME type from image file content (magic bytes), falling back to extension."""
    try:
        data = Path(file_path).read_bytes()
        detected = detect_image_format(data)
        if detected:
            return detected["mime"]
    except Exception:
        pass
    ext = splitext(file_path)[1].lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    if ext in mime_map:
        return mime_map[ext]
    raise CLIError(f"Unsupported image format: {ext}. Supported: .png, .jpg, .jpeg, .webp")


# ============================================================================
# Help Text
# ============================================================================

PAI_DIR = os.environ.get("PAI_DIR") or f"{os.environ.get('HOME', str(Path.home()))}/.claude"


def show_help() -> None:
    print(f"""
generate - Image Generation CLI

USAGE:
  python Generate.py --model <model> --prompt "<prompt>" [OPTIONS]

REQUIRED:
  --model <model>      Model to use: flux, nano-banana, nano-banana-pro, gpt-image-1
  --prompt <text>      Image generation prompt (quote if contains spaces)

OPTIONS:
  --size <size>              Image size/aspect ratio (default: 16:9)
                             Replicate (flux, nano-banana): {', '.join(REPLICATE_SIZES)}
                             OpenAI (gpt-image-1): {', '.join(OPENAI_SIZES)}
                             Gemini (nano-banana-pro): {', '.join(GEMINI_SIZES)}
  --aspect-ratio <ratio>     Aspect ratio for Gemini nano-banana-pro
  --output <path>            Output file path (default: ~/Downloads/generated-image.png)
  --reference-image <path>   Reference image (Nano Banana Pro only, repeatable)
  --transparent              Enable transparent background
  --remove-bg                Remove background after generation (remove.bg API)
  --add-bg <hex>             Add background color to transparent image
  --thumbnail                Generate transparent + thumbnail versions
  --creative-variations <n>  Generate N variations (1-10)
  --help, -h                 Show this help message

ENVIRONMENT VARIABLES:
  REPLICATE_API_TOKEN  Required for flux and nano-banana models
  OPENAI_API_KEY       Required for gpt-image-1 model
  GOOGLE_API_KEY       Required for nano-banana-pro model
  REMOVEBG_API_KEY     Required for --remove-bg flag

Documentation: {PAI_DIR}/skills/media/art/README.md
""")
    sys.exit(0)


# ============================================================================
# Argument Parsing
# ============================================================================


def parse_args(argv: list[str]) -> dict[str, Any]:
    args = argv[1:]  # skip script name

    if "--help" in args or "-h" in args or len(args) == 0:
        show_help()

    parsed: dict[str, Any] = {
        "model": DEFAULTS_MODEL,
        "output": DEFAULTS_OUTPUT,
        "transparent": False,
        "remove_bg": False,
        "thumbnail": False,
        "reference_images": [],
    }

    i = 0
    while i < len(args):
        flag = args[i]
        if not flag.startswith("--"):
            raise CLIError(f"Invalid flag: {flag}. Flags must start with --")

        key = flag[2:]

        # Boolean flags
        if key == "transparent":
            parsed["transparent"] = True
            i += 1
            continue
        if key == "remove-bg":
            parsed["remove_bg"] = True
            i += 1
            continue
        if key == "thumbnail":
            parsed["thumbnail"] = True
            parsed["remove_bg"] = True
            i += 1
            continue

        # Flags with values
        if i + 1 >= len(args) or args[i + 1].startswith("--"):
            raise CLIError(f"Missing value for flag: {flag}")
        value = args[i + 1]

        if key == "model":
            valid_models = ["flux", "nano-banana", "nano-banana-pro", "gpt-image-1"]
            if value not in valid_models:
                raise CLIError(
                    f"Invalid model: {value}. Must be: {', '.join(valid_models)}"
                )
            parsed["model"] = value
            i += 2
        elif key == "prompt":
            parsed["prompt"] = value
            i += 2
        elif key == "size":
            parsed["size"] = value
            i += 2
        elif key == "aspect-ratio":
            parsed["aspect_ratio"] = value
            i += 2
        elif key == "output":
            parsed["output"] = value
            i += 2
        elif key == "reference-image":
            parsed["reference_images"].append(value)
            i += 2
        elif key == "creative-variations":
            variations = int(value)
            if variations < 1 or variations > 10:
                raise CLIError(
                    f"Invalid creative-variations: {value}. Must be 1-10"
                )
            parsed["creative_variations"] = variations
            i += 2
        elif key == "add-bg":
            if not re.match(r"^#[0-9A-Fa-f]{6}$", value):
                raise CLIError(
                    f"Invalid hex color: {value}. Must be in format #RRGGBB"
                )
            parsed["add_bg"] = value
            i += 2
        else:
            raise CLIError(f"Unknown flag: {flag}")

    # Validate required
    if "prompt" not in parsed:
        raise CLIError("Missing required argument: --prompt")

    model = parsed["model"]

    # Validate reference images
    ref_images = parsed.get("reference_images", [])
    if ref_images and model != "nano-banana-pro":
        raise CLIError("--reference-image is only supported with --model nano-banana-pro")
    if len(ref_images) > 14:
        raise CLIError(
            f"Too many reference images: {len(ref_images)}. Maximum is 14 total"
        )

    # Set default size if not provided
    if "size" not in parsed:
        if model == "gpt-image-1":
            parsed["size"] = "1024x1024"
        elif model == "nano-banana-pro":
            parsed["size"] = "2K"
        else:
            parsed["size"] = "16:9"

    # Validate size
    size = parsed["size"]
    if model == "gpt-image-1":
        if size not in OPENAI_SIZES:
            raise CLIError(
                f"Invalid size for gpt-image-1: {size}. Must be: {', '.join(OPENAI_SIZES)}"
            )
    elif model == "nano-banana-pro":
        if size not in GEMINI_SIZES:
            raise CLIError(
                f"Invalid size for nano-banana-pro: {size}. Must be: {', '.join(GEMINI_SIZES)}"
            )
        ar = parsed.get("aspect_ratio")
        if ar and ar not in GEMINI_ASPECT_RATIOS:
            raise CLIError(
                f"Invalid aspect-ratio: {ar}. Must be: {', '.join(GEMINI_ASPECT_RATIOS)}"
            )
        if not ar:
            parsed["aspect_ratio"] = "16:9"
    else:
        if size not in REPLICATE_SIZES:
            raise CLIError(
                f"Invalid size for {model}: {size}. Must be: {', '.join(REPLICATE_SIZES)}"
            )

    return parsed


# ============================================================================
# Prompt Enhancement
# ============================================================================


def enhance_prompt_for_transparency(prompt: str) -> str:
    prefix = (
        "CRITICAL: Transparent background (PNG with alpha channel) - "
        "NO background color, pure transparency. Object floating in "
        "transparent space. "
    )
    return prefix + prompt


# ============================================================================
# Background Operations
# ============================================================================


async def add_background_color(
    input_path: str, output_path: str, hex_color: str
) -> None:
    """Add a solid background color to a transparent PNG using ImageMagick."""
    print(f"Adding background color {hex_color} to image...")
    cmd = ["magick", input_path, "-background", hex_color, "-flatten", output_path]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise CLIError(
            f"Failed to add background color: {stderr.decode()}"
        )
    print(f"Thumbnail saved to {output_path}")


async def remove_background(image_path: str) -> None:
    """Remove background using remove.bg API."""
    api_key = os.environ.get("REMOVEBG_API_KEY")
    if not api_key:
        raise CLIError("Missing environment variable: REMOVEBG_API_KEY")

    print("Removing background with remove.bg API...")

    image_data = Path(image_path).read_bytes()

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.remove.bg/v1.0/removebg",
            headers={"X-Api-Key": api_key},
            files={"image_file": ("image.png", image_data, "image/png")},
            data={"size": "auto"},
        )

    if resp.status_code != 200:
        raise CLIError(
            f"remove.bg API error: {resp.status_code} - {resp.text}"
        )

    Path(image_path).write_bytes(resp.content)
    print("Background removed successfully")


# ============================================================================
# Image Generation
# ============================================================================


async def generate_with_flux(
    prompt: str, size: str, output: str
) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise CLIError("Missing environment variable: REPLICATE_API_TOKEN")
    if _replicate_mod is None:
        raise CLIError("replicate package not installed (pip install replicate)")

    client = _replicate_mod.Client(api_token=token)
    print("Generating with Flux 1.1 Pro...")

    result = client.run(
        "black-forest-labs/flux-1.1-pro",
        input={
            "prompt": prompt,
            "aspect_ratio": size,
            "output_format": "png",
            "output_quality": 95,
            "prompt_upsampling": False,
        },
    )

    # result may be a URL string or file-like object
    if isinstance(result, str):
        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.get(result)
            resp.raise_for_status()
            data = resp.content
    elif hasattr(result, "read"):
        data = result.read()
    else:
        data = bytes(result)

    final_path = save_image(data, output)
    print(f"Image saved to {final_path}")
    return final_path


async def generate_with_nano_banana(
    prompt: str, size: str, output: str
) -> str:
    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise CLIError("Missing environment variable: REPLICATE_API_TOKEN")
    if _replicate_mod is None:
        raise CLIError("replicate package not installed (pip install replicate)")

    client = _replicate_mod.Client(api_token=token)
    print("Generating with Nano Banana...")

    result = client.run(
        "google/nano-banana",
        input={
            "prompt": prompt,
            "aspect_ratio": size,
            "output_format": "png",
        },
    )

    if isinstance(result, str):
        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.get(result)
            resp.raise_for_status()
            data = resp.content
    elif hasattr(result, "read"):
        data = result.read()
    else:
        data = bytes(result)

    final_path = save_image(data, output)
    print(f"Image saved to {final_path}")
    return final_path


async def generate_with_gpt_image(
    prompt: str, size: str, output: str
) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise CLIError("Missing environment variable: OPENAI_API_KEY")
    if _openai_mod is None:
        raise CLIError("openai package not installed (pip install openai)")

    client = _openai_mod.OpenAI(api_key=api_key)
    print("Generating with GPT-image-1...")

    response = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size=size,
        n=1,
    )

    image_data = response.data[0].b64_json
    if not image_data:
        raise CLIError("No image data returned from OpenAI API")

    image_buffer = base64.b64decode(image_data)
    final_path = save_image(image_buffer, output)
    print(f"Image saved to {final_path}")
    return final_path


async def generate_with_nano_banana_pro(
    prompt: str,
    size: str,
    aspect_ratio: str,
    output: str,
    reference_images: Optional[list[str]] = None,
) -> str:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise CLIError("Missing environment variable: GOOGLE_API_KEY")
    if _google_genai_mod is None:
        raise CLIError("google-genai package not installed (pip install google-genai)")

    ai = _google_genai_mod.Client(api_key=api_key)

    ref_count = len(reference_images) if reference_images else 0
    if ref_count > 0:
        print(
            f"Generating with Nano Banana Pro (Gemini 3 Pro) at {size} "
            f"{aspect_ratio} with {ref_count} reference image(s)..."
        )
    else:
        print(f"Generating with Nano Banana Pro (Gemini 3 Pro) at {size} {aspect_ratio}...")

    # Build content parts
    parts: list[dict[str, Any]] = []

    if reference_images:
        for ref_img in reference_images:
            img_bytes = Path(ref_img).read_bytes()
            img_b64 = base64.b64encode(img_bytes).decode("ascii")
            mime_type = detect_mime_type(ref_img)
            parts.append({
                "inline_data": {"mime_type": mime_type, "data": img_b64}
            })

    parts.append({"text": prompt})

    response = ai.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[{"parts": parts}],
        config={
            "response_modalities": ["TEXT", "IMAGE"],
            "image_config": {
                "aspect_ratio": aspect_ratio,
                "image_size": size,
            },
        },
    )

    image_data: Optional[str] = None
    if response.candidates:
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                image_data = part.inline_data.data
                break

    if not image_data:
        raise CLIError("No image data returned from Gemini API")

    image_buffer = base64.b64decode(image_data)
    final_path = save_image(image_buffer, output)
    print(f"Image saved to {final_path}")
    return final_path


# ============================================================================
# Main
# ============================================================================


async def async_main() -> None:
    try:
        load_env()
        args = parse_args(sys.argv)

        prompt = args["prompt"]
        if args.get("transparent"):
            prompt = enhance_prompt_for_transparency(prompt)
            print("Transparent background mode enabled")
            print("Note: Not all models support transparency natively\n")

        model = args["model"]
        output = args["output"]
        size = args["size"]

        # Creative variations mode
        creative_n = args.get("creative_variations")
        if creative_n and creative_n > 1:
            print(f"Creative Mode: Generating {creative_n} variations...")
            print("Note: CLI mode uses same prompt for all variations\n")

            base_path = re.sub(r"\.[^.]+$", "", output)
            tasks = []
            for i in range(1, creative_n + 1):
                var_output = f"{base_path}-v{i}.png"
                print(f"Variation {i}/{creative_n}: {var_output}")
                if model == "flux":
                    tasks.append(generate_with_flux(prompt, size, var_output))
                elif model == "nano-banana":
                    tasks.append(generate_with_nano_banana(prompt, size, var_output))
                elif model == "nano-banana-pro":
                    tasks.append(
                        generate_with_nano_banana_pro(
                            prompt, size, args.get("aspect_ratio", "16:9"),
                            var_output, args.get("reference_images"),
                        )
                    )
                elif model == "gpt-image-1":
                    tasks.append(generate_with_gpt_image(prompt, size, var_output))

            actual_paths = await asyncio.gather(*tasks)
            print(f"\nGenerated {creative_n} variations")
            print(f"   Files: {', '.join(actual_paths)}")
            return

        # Standard single image generation
        actual_output = output
        if model == "flux":
            actual_output = await generate_with_flux(prompt, size, output)
        elif model == "nano-banana":
            actual_output = await generate_with_nano_banana(prompt, size, output)
        elif model == "nano-banana-pro":
            actual_output = await generate_with_nano_banana_pro(
                prompt, size, args.get("aspect_ratio", "16:9"),
                output, args.get("reference_images"),
            )
        elif model == "gpt-image-1":
            actual_output = await generate_with_gpt_image(prompt, size, output)

        # Remove background if requested
        if args.get("remove_bg"):
            await remove_background(actual_output)

        # Add background color (standalone mode)
        if args.get("add_bg") and not args.get("thumbnail"):
            temp_path = re.sub(r"\.[^.]+$", "-temp.png", actual_output)
            await add_background_color(actual_output, temp_path, args["add_bg"])
            Path(temp_path).rename(actual_output)

        # Generate thumbnail
        if args.get("thumbnail"):
            thumb_path = re.sub(r"\.[^.]+$", "-thumb.png", actual_output)
            THUMBNAIL_BG_COLOR = "#EAE9DF"
            await add_background_color(actual_output, thumb_path, THUMBNAIL_BG_COLOR)
            print(f"\nBlog header mode: Created both versions")
            print(f"   Transparent: {actual_output}")
            print(f"   Thumbnail:   {thumb_path}")

    except CLIError as e:
        handle_error(e)
    except Exception as e:
        handle_error(e)


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
