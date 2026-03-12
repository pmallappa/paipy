#!/usr/bin/env python3

"""
Abstract Illustration Prompt Generator

WARNING: DEPRECATED - THIS TOOL USES OLD CHARACTER-BASED SYSTEM
WARNING: NEEDS COMPLETE REWRITE FOR ABSTRACT SHAPES/IMPRESSIONS ONLY
WARNING: DO NOT USE UNTIL UPDATED

This tool needs to be rewritten to generate prompts using:
- Abstract shapes and forms (NO characters)
- Visual motifs (networks, flows, structures, horizons)
- Composition approaches (centered, horizon, flow, opposition, layered)

Usage (when updated):
  python GeneratePrompt.py --input essay.md --type essay-illustration
  python GeneratePrompt.py --input essay.md --type blog-header --format json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Literal, Optional

# ============================================================================
# Types
# ============================================================================

CompositionType = Literal["observation", "horizon", "dialogue", "workshop", "aura"]
CharacterFocus = Literal["maya", "kai", "both"]
TokyoNightColor = Literal[
    "Electric Blue",
    "Vivid Purple",
    "Bright Cyan",
    "Neon Green",
    "Warm Yellow",
    "Soft Magenta",
]
Human3Motif = Literal[
    "agents", "networks", "aura", "substrates", "horizons", "ts_stacks"
]
BackgroundType = Literal["sepia", "dark_tokyo_night"]
OutputFormat = Literal["text", "json"]
ImageType = Literal["essay-illustration", "blog-header"]


# ============================================================================
# Constants
# ============================================================================

ART_AESTHETIC_PATH = Path.home() / ".claude" / "PAI" / "Aesthetic.md"

COLOR_HEX_MAP: dict[str, str] = {
    "Electric Blue": "#7aa2f7",
    "Vivid Purple": "#bb9af7",
    "Bright Cyan": "#7dcfff",
    "Neon Green": "#9ece6a",
    "Warm Yellow": "#e0af68",
    "Soft Magenta": "#ff007c",
}

CHARACTER_DESCRIPTIONS: dict[str, str] = {
    "maya": (
        "Maya is a young, highly curious girl with a round head, simple short "
        "hair, and big round glasses (her signature feature). She has a "
        "stick-figure body with thin limbs and a slightly oversized head, "
        "with minimal facial features (dots for eyes, simple line for mouth "
        "when needed)."
    ),
    "kai": (
        "{DAIDENTITY.NAME} is a young boy with a slightly oval head, a soft "
        "messy hair tuft on top (his signature feature), and NO glasses. He "
        "wears a simple t-shirt and shorts or pants. He has a stick-figure "
        "body with thin limbs and a slightly oversized head, with minimal "
        "facial features."
    ),
    "both": (
        "Two recurring child characters: Maya and Kai. Maya is a young, "
        "highly curious girl with a round head, simple short hair, and big "
        "round glasses. Kai is a young boy with a slightly oval head, a soft "
        "messy hair tuft, and a simple t-shirt and shorts or pants. Both have "
        "stick-figure bodies with thin limbs and slightly oversized heads, "
        "with minimal facial features."
    ),
}


# ============================================================================
# Helpers
# ============================================================================


def parse_cli_args() -> dict[str, Any]:
    """Parse command-line arguments into a dict."""
    args = sys.argv[1:]
    parsed: dict[str, Any] = {
        "type": "essay-illustration",
        "format": "text",
    }
    i = 0
    while i < len(args) - 1:
        key = args[i].lstrip("-")
        value = args[i + 1]
        parsed[key] = value
        i += 2
    return parsed


def read_essay_content(path: str) -> str:
    """Read essay content from file."""
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        print(f"Error reading essay file: {path}", file=sys.stderr)
        raise


def analyze_content(
    essay_content: str,
) -> dict[str, Any]:
    """Simple content analysis."""
    lines = essay_content.split("\n")

    # Extract title (first # line)
    title_line = next((l for l in lines if l.startswith("# ")), None)
    theme = title_line[2:] if title_line else "essay topic"

    content_lower = essay_content.lower()
    tone = "analytical curiosity"

    if "future" in content_lower or "possibility" in content_lower:
        tone = "cautious wonder about future possibilities"
    elif "build" in content_lower or "create" in content_lower:
        tone = "collaborative optimism"
    elif "problem" in content_lower or "challenge" in content_lower:
        tone = "analytical focus on challenges and opportunities"

    return {
        "theme": theme,
        "tone": tone,
        "metaphors": [],
        "concepts": [],
    }


def select_composition(
    essay_content: str, override: Optional[str] = None
) -> CompositionType:
    if override:
        return override  # type: ignore[return-value]

    content_lower = essay_content.lower()
    if "future" in content_lower or "horizon" in content_lower:
        return "horizon"
    if "together" in content_lower or "collaborate" in content_lower:
        return "dialogue"
    if "build" in content_lower or "create" in content_lower:
        return "workshop"
    if "personal" in content_lower or "context" in content_lower:
        return "aura"
    return "observation"


def select_character(
    composition_type: CompositionType, override: Optional[str] = None
) -> CharacterFocus:
    if override:
        return override  # type: ignore[return-value]

    mapping: dict[CompositionType, CharacterFocus] = {
        "dialogue": "both",
        "workshop": "kai",
        "observation": "maya",
    }
    return mapping.get(composition_type, "both")


def select_colors(
    essay_content: str, override: Optional[str] = None
) -> list[str]:
    if override:
        return [c.strip() for c in override.split(",")]

    content_lower = essay_content.lower()
    if "security" in content_lower or "privacy" in content_lower:
        return ["Vivid Purple"]
    if "tool" in content_lower or "productivity" in content_lower:
        return ["Bright Cyan"]
    if "human" in content_lower or "growth" in content_lower:
        return ["Neon Green"]
    return ["Electric Blue"]


def select_motifs(
    essay_content: str, override: Optional[str] = None
) -> list[str]:
    if override:
        return [m.strip() for m in override.split(",")]

    motifs: list[str] = []
    content_lower = essay_content.lower()

    if "agent" in content_lower or "ai" in content_lower:
        motifs.append("agents")
    if "network" in content_lower or "connect" in content_lower:
        motifs.append("networks")
    if "future" in content_lower or "horizon" in content_lower:
        motifs.append("horizons")
    if "personal" in content_lower or "context" in content_lower:
        motifs.append("aura")

    return motifs[:2]


def build_visual_metaphor(
    essay_content: str,
    composition_type: CompositionType,
    character_focus: CharacterFocus,
) -> str:
    analysis = analyze_content(essay_content)
    theme = analysis["theme"]
    tone = analysis["tone"]

    char_name_map: dict[str, str] = {
        "maya": "Maya",
        "kai": "Kai",
        "both": "Maya and Kai",
    }
    char_display = char_name_map.get(character_focus, character_focus)

    metaphors: dict[CompositionType, str] = {
        "observation": (
            f"{char_display if character_focus != 'both' else 'Maya'} positioned in the left "
            f"quarter of the frame, small and observing with {tone}, looking at a "
            f"large visual element on the right that represents the core concept of {theme}"
        ),
        "horizon": (
            f"{char_display} in the foreground, facing a wide distant horizon "
            f"filled with tiny elements representing future possibilities related to {theme}"
        ),
        "dialogue": (
            f"Maya and {{DAIDENTITY.NAME}} positioned with space between them, "
            f"interacting with a shared element or concept in the center, "
            f"representing different perspectives on {theme}"
        ),
        "workshop": (
            f"{char_display if character_focus != 'both' else 'Both Maya and Kai'} actively "
            f"building or creating, with elements spreading horizontally showing "
            f"the process of making something related to {theme}"
        ),
        "aura": (
            f"{char_display if character_focus != 'both' else 'The character'} surrounded by a "
            f"soft, translucent aura bubble containing tiny symbolic icons "
            f"representing aspects of {theme}"
        ),
    }

    return metaphors.get(composition_type, "")


def build_motifs_description(motifs: list[str]) -> str:
    if not motifs:
        return ""

    descriptions: list[str] = []
    motif_map = {
        "agents": "tiny cute pill-shaped agent robots",
        "networks": "thin network lines connecting small nodes",
        "aura": (
            "soft aura bubbles around people or robots with tiny symbolic "
            "icons like hearts, book-shapes, leaves, or stars (icons must be "
            "purely visual and contain no letters or numbers)"
        ),
        "substrates": "horizontal platform layers suggesting infrastructure",
        "horizons": "distant horizon line filled with tiny silhouettes",
        "ts_stacks": "stacks of thin blank rectangular sheets",
    }

    for motif in motifs:
        desc = motif_map.get(motif)
        if desc:
            descriptions.append(desc)

    return (
        "Optionally include Human 3.0 motifs that fit the essay: "
        + ", ".join(descriptions)
        + "."
    )


# ============================================================================
# Prompt Generation
# ============================================================================


def generate_prompt(
    essay_theme: str,
    character_focus: CharacterFocus,
    composition_type: CompositionType,
    emotional_tone_description: str,
    core_object_description: str,
    overall_mood: str,
    accent_colors: list[str],
    human3_motifs: list[str],
    background_type: BackgroundType,
    image_type: ImageType,
) -> str:
    # Build color description
    color_descriptions = " and ".join(
        f"{c} {COLOR_HEX_MAP.get(c, '')}" for c in accent_colors
    )

    character_desc = CHARACTER_DESCRIPTIONS.get(character_focus, "")
    motifs_desc = build_motifs_description(human3_motifs)

    background_desc = (
        "Soft sepia-toned paper background with lots of empty space."
        if background_type == "sepia"
        else "Dark gradient background transitioning from #1a1b26 to #24283b."
    )

    color_label = "s" if len(accent_colors) > 1 else ""
    image_label = (
        "a blog post" if image_type == "blog-header" else "an essay"
    )
    char_display = (
        "Maya and Kai" if character_focus == "both" else character_focus
    )
    comp_extra = (
        " optimized for horizontal 16:9 composition"
        if image_type == "blog-header"
        else ""
    )

    prompt = (
        f"Minimal Tokyo Night-inspired illustration for {image_label} about {essay_theme}.\n\n"
        f"{background_desc} Thin, slightly imperfect deep navy linework and flat color "
        f"fills only, no shading. Tokyo Night-inspired accent color{color_label} "
        f"{color_descriptions} used sparingly.\n\n"
        f"{character_desc}\n\n"
        f"Show {char_display} in a {composition_type} scene{comp_extra}. "
        f"{emotional_tone_description[0].upper()}{emotional_tone_description[1:]}, "
        f"interacting with {core_object_description}.\n\n"
        f"{motifs_desc}\n\n"
        f"The overall mood should be {overall_mood}. No text, no letters, no numbers, "
        f"and no labels anywhere in the image."
    )

    if image_type == "blog-header":
        prompt += (
            "\n\n=== BLOG HEADER SPECIFICATIONS ===\n\n"
            "Output format: PNG, 1536x1024 (16:9 landscape for blog header)\n"
            "Horizontal composition optimized for wide format\n"
            "Primary focus in upper two-thirds of frame\n"
            "Maximum quality settings (95% quality)\n"
            "Editorial cover image quality like The Atlantic or New Yorker or New York Times"
        )

    return prompt


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    cli_args = parse_cli_args()

    if "input" not in cli_args:
        print(
            "Usage: python GeneratePrompt.py --input <essay.md> [options]",
            file=sys.stderr,
        )
        print("\nOptions:", file=sys.stderr)
        print(
            "  --type           essay-illustration | blog-header (default: essay-illustration)",
            file=sys.stderr,
        )
        print("  --format         text | json (default: text)", file=sys.stderr)
        print(
            "  --composition    observation | horizon | dialogue | workshop | aura",
            file=sys.stderr,
        )
        print("  --character      maya | kai | both", file=sys.stderr)
        print(
            '  --colors         "Electric Blue,Neon Green" (comma-separated)',
            file=sys.stderr,
        )
        print(
            '  --motifs         "agents,networks" (comma-separated)',
            file=sys.stderr,
        )
        sys.exit(1)

    essay_content = read_essay_content(cli_args["input"])
    analysis = analyze_content(essay_content)

    composition_type = select_composition(
        essay_content, cli_args.get("composition")
    )
    character_focus = select_character(
        composition_type, cli_args.get("character")
    )
    accent_colors = select_colors(essay_content, cli_args.get("colors"))
    human3_motifs = select_motifs(essay_content, cli_args.get("motifs"))

    core_object_description = build_visual_metaphor(
        essay_content, composition_type, character_focus
    )

    image_type: ImageType = cli_args.get("type", "essay-illustration")  # type: ignore[assignment]
    emotional_tone = f"They are {analysis['tone']}"
    overall_mood = " ".join(analysis["tone"].split()[:2])

    image_prompt = generate_prompt(
        essay_theme=analysis["theme"],
        character_focus=character_focus,
        composition_type=composition_type,
        emotional_tone_description=emotional_tone,
        core_object_description=core_object_description,
        overall_mood=overall_mood,
        accent_colors=accent_colors,
        human3_motifs=human3_motifs,
        background_type="sepia",
        image_type=image_type,
    )

    output_format: OutputFormat = cli_args.get("format", "text")  # type: ignore[assignment]

    if output_format == "json":
        slug = (
            re.sub(r"[^a-z0-9]+", "-", analysis["theme"].lower()).strip("-")
            + ".png"
        )
        output = {
            "essay_theme": analysis["theme"],
            "character_focus": character_focus,
            "composition_type": composition_type,
            "emotional_tone_description": emotional_tone,
            "core_object_description": core_object_description,
            "overall_mood": overall_mood,
            "accent_colors": accent_colors,
            "human3_motifs": human3_motifs,
            "image_prompt": image_prompt,
            "suggested_filename": slug,
        }
        print(json.dumps(output, indent=2))
    else:
        print(image_prompt)


if __name__ == "__main__":
    main()
