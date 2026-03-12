#!/usr/bin/env python3

"""
ComposeAgent - Dynamic Agent Composition from Traits

Composes specialized agents on-the-fly by combining traits.
Merges base traits (ships with PAI) with user customizations.

Configuration files:
  Base:  ~/.claude/skills/agents/data/Traits.yaml
  User:  ~/.claude/pai/user/skillcustomizations/Agents/Traits.yaml

Usage:
  # Infer traits from task description
  python ComposeAgent.py --task "Review this security architecture"

  # Specify traits explicitly
  python ComposeAgent.py --traits "security,skeptical,thorough"

  # Output formats
  python ComposeAgent.py --task "..." --output json
  python ComposeAgent.py --task "..." --output prompt (default)

  # List available traits
  python ComposeAgent.py --list

@version 2.0.0
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Optional

import yaml

try:
    import pybars3 as pybars

    _HAS_PYBARS = True
except ImportError:
    _HAS_PYBARS = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HOME = os.environ.get("HOME", str(Path.home()))
BASE_TRAITS_PATH = f"{HOME}/.claude/skills/agents/data/Traits.yaml"
USER_TRAITS_PATH = f"{HOME}/.claude/pai/user/skillcustomizations/Agents/Traits.yaml"
TEMPLATE_PATH = f"{HOME}/.claude/skills/agents/templates/DynamicAgent.hbs"
CUSTOM_AGENTS_DIR = f"{HOME}/.claude/custom-agents"

# ---------------------------------------------------------------------------
# Types (dataclasses)
# ---------------------------------------------------------------------------


@dataclass
class ProsodySettings:
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    speed: float = 1.0
    use_speaker_boost: bool = True
    volume: float = 0.8


@dataclass
class TraitDefinition:
    name: str = ""
    description: str = ""
    prompt_fragment: Optional[str] = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class VoiceMapping:
    traits: list[str] = field(default_factory=list)
    voice: str = ""
    voice_id: Optional[str] = None
    reason: Optional[str] = None


@dataclass
class VoiceRegistryEntry:
    voice_id: str = ""
    characteristics: list[str] = field(default_factory=list)
    description: str = ""
    prosody: Optional[ProsodySettings] = None
    # Legacy flat fields (backwards compatibility)
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None


@dataclass
class VoiceMappings:
    default: str = "{PRINCIPAL.NAME}"
    default_voice_id: str = ""
    voice_registry: dict[str, VoiceRegistryEntry] = field(default_factory=dict)
    mappings: list[VoiceMapping] = field(default_factory=list)
    fallbacks: dict[str, str] = field(default_factory=dict)


@dataclass
class TraitsData:
    expertise: dict[str, TraitDefinition] = field(default_factory=dict)
    personality: dict[str, TraitDefinition] = field(default_factory=dict)
    approach: dict[str, TraitDefinition] = field(default_factory=dict)
    voice_mappings: VoiceMappings = field(default_factory=VoiceMappings)
    examples: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class ComposedAgent:
    name: str = ""
    traits: list[str] = field(default_factory=list)
    expertise: list[TraitDefinition] = field(default_factory=list)
    personality: list[TraitDefinition] = field(default_factory=list)
    approach: list[TraitDefinition] = field(default_factory=list)
    voice: str = ""
    voice_id: str = ""
    voice_reason: str = ""
    voice_settings: ProsodySettings = field(default_factory=ProsodySettings)
    color: str = ""
    prompt: str = ""


# ---------------------------------------------------------------------------
# Color palette for custom agents
# ---------------------------------------------------------------------------

AGENT_COLOR_PALETTE = [
    "#FF6B35",  # Coral Orange
    "#4ECDC4",  # Teal
    "#9B59B6",  # Purple
    "#2ECC71",  # Emerald
    "#E74C3C",  # Red
    "#3498DB",  # Blue
    "#F39C12",  # Orange
    "#1ABC9C",  # Turquoise
    "#E91E63",  # Pink
    "#00BCD4",  # Cyan
    "#8BC34A",  # Light Green
    "#FF5722",  # Deep Orange
    "#673AB7",  # Deep Purple
    "#009688",  # Teal Dark
    "#FFC107",  # Amber
]

DEFAULT_PROSODY = ProsodySettings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def deep_merge(base: dict, user: dict) -> dict:
    """Deep merge two dicts (user overrides base)."""
    result = dict(base)
    for key, user_val in user.items():
        base_val = base.get(key)
        if (
            user_val is not None
            and isinstance(user_val, dict)
            and isinstance(base_val, dict)
        ):
            result[key] = deep_merge(base_val, user_val)
        elif user_val is not None:
            result[key] = user_val
    return result


def merge_arrays(base: list, user: list) -> list:
    """Merge arrays by concatenation."""
    return base + user


def _dict_to_trait(d: dict) -> TraitDefinition:
    """Convert a raw dict to a TraitDefinition."""
    return TraitDefinition(
        name=d.get("name", ""),
        description=d.get("description", ""),
        prompt_fragment=d.get("prompt_fragment"),
        keywords=d.get("keywords", []),
    )


def _dict_to_voice_registry_entry(d: dict) -> VoiceRegistryEntry:
    prosody_raw = d.get("prosody")
    prosody = None
    if prosody_raw and isinstance(prosody_raw, dict):
        prosody = ProsodySettings(
            stability=prosody_raw.get("stability", DEFAULT_PROSODY.stability),
            similarity_boost=prosody_raw.get("similarity_boost", DEFAULT_PROSODY.similarity_boost),
            style=prosody_raw.get("style", DEFAULT_PROSODY.style),
            speed=prosody_raw.get("speed", DEFAULT_PROSODY.speed),
            use_speaker_boost=prosody_raw.get("use_speaker_boost", DEFAULT_PROSODY.use_speaker_boost),
            volume=prosody_raw.get("volume", DEFAULT_PROSODY.volume),
        )
    return VoiceRegistryEntry(
        voice_id=d.get("voice_id", ""),
        characteristics=d.get("characteristics", []),
        description=d.get("description", ""),
        prosody=prosody,
        stability=d.get("stability"),
        similarity_boost=d.get("similarity_boost"),
    )


def _raw_to_traits_data(raw: dict) -> TraitsData:
    """Convert raw parsed YAML dict into TraitsData."""
    expertise = {
        k: _dict_to_trait(v) for k, v in (raw.get("expertise") or {}).items()
    }
    personality = {
        k: _dict_to_trait(v) for k, v in (raw.get("personality") or {}).items()
    }
    approach = {
        k: _dict_to_trait(v) for k, v in (raw.get("approach") or {}).items()
    }

    vm_raw = raw.get("voice_mappings") or {}
    registry_raw = vm_raw.get("voice_registry") or {}
    voice_registry = {
        k: _dict_to_voice_registry_entry(v) for k, v in registry_raw.items()
    }

    mappings_raw = vm_raw.get("mappings") or []
    mappings = [
        VoiceMapping(
            traits=m.get("traits", []),
            voice=m.get("voice", ""),
            voice_id=m.get("voice_id"),
            reason=m.get("reason"),
        )
        for m in mappings_raw
    ]

    voice_mappings = VoiceMappings(
        default=vm_raw.get("default", "{PRINCIPAL.NAME}"),
        default_voice_id=vm_raw.get("default_voice_id", ""),
        voice_registry=voice_registry,
        mappings=mappings,
        fallbacks=vm_raw.get("fallbacks") or {},
    )

    return TraitsData(
        expertise=expertise,
        personality=personality,
        approach=approach,
        voice_mappings=voice_mappings,
        examples=raw.get("examples") or {},
    )


# ---------------------------------------------------------------------------
# Load traits
# ---------------------------------------------------------------------------


def load_traits() -> TraitsData:
    """Load and merge traits from base + user YAML files."""
    if not Path(BASE_TRAITS_PATH).exists():
        print(f"Error: Base traits file not found at {BASE_TRAITS_PATH}", file=sys.stderr)
        sys.exit(1)

    base_content = Path(BASE_TRAITS_PATH).read_text(encoding="utf-8")
    base_raw: dict = yaml.safe_load(base_content) or {}

    user_path = Path(USER_TRAITS_PATH)
    if user_path.exists():
        user_content = user_path.read_text(encoding="utf-8")
        user_raw: dict = yaml.safe_load(user_content) or {}

        merged_raw: dict[str, Any] = {
            "expertise": deep_merge(base_raw.get("expertise") or {}, user_raw.get("expertise") or {}),
            "personality": deep_merge(base_raw.get("personality") or {}, user_raw.get("personality") or {}),
            "approach": deep_merge(base_raw.get("approach") or {}, user_raw.get("approach") or {}),
            "voice_mappings": {
                "default": (user_raw.get("voice_mappings") or {}).get("default")
                    or (base_raw.get("voice_mappings") or {}).get("default")
                    or "{PRINCIPAL.NAME}",
                "default_voice_id": (user_raw.get("voice_mappings") or {}).get("default_voice_id")
                    or (base_raw.get("voice_mappings") or {}).get("default_voice_id")
                    or "",
                "voice_registry": deep_merge(
                    (base_raw.get("voice_mappings") or {}).get("voice_registry") or {},
                    (user_raw.get("voice_mappings") or {}).get("voice_registry") or {},
                ),
                "mappings": merge_arrays(
                    (base_raw.get("voice_mappings") or {}).get("mappings") or [],
                    (user_raw.get("voice_mappings") or {}).get("mappings") or [],
                ),
                "fallbacks": deep_merge(
                    (base_raw.get("voice_mappings") or {}).get("fallbacks") or {},
                    (user_raw.get("voice_mappings") or {}).get("fallbacks") or {},
                ),
            },
            "examples": deep_merge(base_raw.get("examples") or {}, user_raw.get("examples") or {}),
        }
        return _raw_to_traits_data(merged_raw)

    return _raw_to_traits_data(base_raw)


# ---------------------------------------------------------------------------
# Load template
# ---------------------------------------------------------------------------


def load_template() -> Any:
    """Load and compile the Handlebars agent template."""
    template_path = Path(TEMPLATE_PATH)
    if not template_path.exists():
        print(f"Error: Template file not found at {TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)

    content = template_path.read_text(encoding="utf-8")

    if _HAS_PYBARS:
        compiler = pybars.Compiler()
        return compiler.compile(content)
    else:
        # Fallback: simple string.Template-style replacement is not feasible
        # for Handlebars; return the raw content and do basic substitution
        return content


def render_template(template: Any, context: dict) -> str:
    """Render a Handlebars template with context."""
    if _HAS_PYBARS and callable(template):
        return template(context)
    # Fallback: return template as-is (best effort)
    return str(template)


# ---------------------------------------------------------------------------
# Infer traits
# ---------------------------------------------------------------------------


def infer_traits_from_task(task: str, traits: TraitsData) -> list[str]:
    """Infer appropriate traits from a task description."""
    inferred: list[str] = []
    task_lower = task.lower()

    for key, defn in traits.expertise.items():
        if defn.keywords and any(kw.lower() in task_lower for kw in defn.keywords):
            inferred.append(key)

    for key, defn in traits.personality.items():
        if defn.keywords and any(kw.lower() in task_lower for kw in defn.keywords):
            inferred.append(key)

    for key, defn in traits.approach.items():
        if defn.keywords and any(kw.lower() in task_lower for kw in defn.keywords):
            inferred.append(key)

    has_expertise = any(t in traits.expertise for t in inferred)
    has_personality = any(t in traits.personality for t in inferred)
    has_approach = any(t in traits.approach for t in inferred)

    if not has_personality:
        inferred.append("analytical")
    if not has_approach:
        inferred.append("thorough")
    if not has_expertise:
        inferred.append("research")

    return list(dict.fromkeys(inferred))  # unique, preserving order


# ---------------------------------------------------------------------------
# Prosody
# ---------------------------------------------------------------------------


def get_prosody(entry: Optional[VoiceRegistryEntry]) -> ProsodySettings:
    """Get prosody settings from a voice registry entry."""
    if entry is None:
        return ProsodySettings()

    if entry.prosody is not None:
        p = entry.prosody
        return ProsodySettings(
            stability=p.stability if p.stability is not None else DEFAULT_PROSODY.stability,
            similarity_boost=p.similarity_boost if p.similarity_boost is not None else DEFAULT_PROSODY.similarity_boost,
            style=p.style if p.style is not None else DEFAULT_PROSODY.style,
            speed=p.speed if p.speed is not None else DEFAULT_PROSODY.speed,
            use_speaker_boost=p.use_speaker_boost if p.use_speaker_boost is not None else DEFAULT_PROSODY.use_speaker_boost,
            volume=p.volume if p.volume is not None else DEFAULT_PROSODY.volume,
        )

    # Legacy flat fields
    return ProsodySettings(
        stability=entry.stability if entry.stability is not None else DEFAULT_PROSODY.stability,
        similarity_boost=entry.similarity_boost if entry.similarity_boost is not None else DEFAULT_PROSODY.similarity_boost,
        style=DEFAULT_PROSODY.style,
        speed=DEFAULT_PROSODY.speed,
        use_speaker_boost=DEFAULT_PROSODY.use_speaker_boost,
        volume=DEFAULT_PROSODY.volume,
    )


# ---------------------------------------------------------------------------
# Resolve voice
# ---------------------------------------------------------------------------


def resolve_voice(
    trait_keys: list[str], traits: TraitsData
) -> dict[str, Any]:
    """Resolve voice based on trait combination."""
    mappings = traits.voice_mappings
    registry = mappings.voice_registry or {}

    def get_voice_id(voice_name: str, fallback_id: Optional[str] = None) -> str:
        entry = registry.get(voice_name)
        if entry and entry.voice_id:
            return entry.voice_id
        return fallback_id or mappings.default_voice_id or ""

    # Check explicit combination mappings first
    scored = []
    for m in mappings.mappings:
        match_count = sum(1 for t in m.traits if t in trait_keys)
        is_full_match = all(t in trait_keys for t in m.traits)
        if is_full_match:
            scored.append((match_count, m))

    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        best = scored[0][1]
        voice_name = best.voice
        return {
            "voice": voice_name,
            "voiceId": best.voice_id or get_voice_id(voice_name),
            "reason": best.reason or f"Matched traits: {', '.join(best.traits)}",
            "voiceSettings": get_prosody(registry.get(voice_name)),
        }

    # Check fallbacks
    for trait in trait_keys:
        if trait in mappings.fallbacks:
            voice_name = mappings.fallbacks[trait]
            voice_id_key = f"{trait}_voice_id"
            fallback_voice_id = mappings.fallbacks.get(voice_id_key)
            return {
                "voice": voice_name,
                "voiceId": fallback_voice_id or get_voice_id(voice_name),
                "reason": f"Fallback for trait: {trait}",
                "voiceSettings": get_prosody(registry.get(voice_name)),
            }

    # Default
    return {
        "voice": mappings.default,
        "voiceId": mappings.default_voice_id or "",
        "reason": "Default voice (no specific mapping matched)",
        "voiceSettings": get_prosody(registry.get(mappings.default)),
    }


# ---------------------------------------------------------------------------
# Agent color
# ---------------------------------------------------------------------------


def generate_agent_color(trait_keys: list[str]) -> str:
    """Generate a unique color based on trait combination (consistent hash)."""
    sorted_traits = ",".join(sorted(trait_keys))
    hash_val = 0
    for ch in sorted_traits:
        hash_val = ((hash_val << 5) - hash_val) + ord(ch)
        hash_val &= 0xFFFFFFFF  # 32-bit
    # Convert to signed 32-bit for parity with JS
    if hash_val >= 0x80000000:
        hash_val -= 0x100000000
    index = abs(hash_val) % len(AGENT_COLOR_PALETTE)
    return AGENT_COLOR_PALETTE[index]


# ---------------------------------------------------------------------------
# Compose agent
# ---------------------------------------------------------------------------


def compose_agent(
    trait_keys: list[str],
    task: str,
    traits: TraitsData,
    timing: Optional[str] = None,
) -> ComposedAgent:
    """Compose an agent from traits."""
    expertise: list[TraitDefinition] = []
    personality: list[TraitDefinition] = []
    approach: list[TraitDefinition] = []

    for key in trait_keys:
        if key in traits.expertise:
            expertise.append(traits.expertise[key])
        if key in traits.personality:
            personality.append(traits.personality[key])
        if key in traits.approach:
            approach.append(traits.approach[key])

    name_parts: list[str] = []
    if expertise:
        name_parts.append(expertise[0].name)
    if personality:
        name_parts.append(personality[0].name)
    if approach:
        name_parts.append(approach[0].name)
    name = " ".join(name_parts) if name_parts else "Dynamic Agent"

    voice_info = resolve_voice(trait_keys, traits)
    color = generate_agent_color(trait_keys)

    valid_timings = ["fast", "standard", "deep"]
    timing_value = timing if timing and timing in valid_timings else None
    timing_data: dict[str, Any] = {}
    if timing_value:
        timing_data = {
            "timing": timing_value,
            "isFast": timing_value == "fast",
            "isStandard": timing_value == "standard",
            "isDeep": timing_value == "deep",
        }

    template = load_template()
    context = {
        "name": name,
        "task": task,
        "expertise": [{"name": e.name, "description": e.description} for e in expertise],
        "personality": [{"name": p.name, "description": p.description} for p in personality],
        "approach": [{"name": a.name, "description": a.description} for a in approach],
        "voice": voice_info["voice"],
        "voiceId": voice_info["voiceId"],
        "voiceSettings": {
            "stability": voice_info["voiceSettings"].stability,
            "similarity_boost": voice_info["voiceSettings"].similarity_boost,
            "style": voice_info["voiceSettings"].style,
            "speed": voice_info["voiceSettings"].speed,
            "use_speaker_boost": voice_info["voiceSettings"].use_speaker_boost,
            "volume": voice_info["voiceSettings"].volume,
        },
        "color": color,
        **timing_data,
    }
    prompt = render_template(template, context)

    return ComposedAgent(
        name=name,
        traits=trait_keys,
        expertise=expertise,
        personality=personality,
        approach=approach,
        voice=voice_info["voice"],
        voice_id=voice_info["voiceId"],
        voice_reason=voice_info["reason"],
        voice_settings=voice_info["voiceSettings"],
        color=color,
        prompt=prompt,
    )


# ---------------------------------------------------------------------------
# List traits
# ---------------------------------------------------------------------------


def list_traits(traits: TraitsData) -> None:
    """List all available traits."""
    print("AVAILABLE TRAITS (base + user merged)\n")

    print("EXPERTISE (domain knowledge):")
    for key, defn in traits.expertise.items():
        print(f"  {key:<15} - {defn.name}")

    print("\nPERSONALITY (behavior style):")
    for key, defn in traits.personality.items():
        print(f"  {key:<15} - {defn.name}")

    print("\nAPPROACH (work style):")
    for key, defn in traits.approach.items():
        print(f"  {key:<15} - {defn.name}")

    print("\nVOICES AVAILABLE:")
    registry = traits.voice_mappings.voice_registry or {}
    for name, entry in registry.items():
        prosody = get_prosody(entry)
        print(f"  {name:<12} - {entry.description}")
        print(
            f"               stability:{prosody.stability} "
            f"style:{prosody.style} speed:{prosody.speed} volume:{prosody.volume}"
        )

    if traits.examples:
        print("\nEXAMPLE COMPOSITIONS:")
        for key, example in traits.examples.items():
            desc = example.get("description", "")
            trait_list = example.get("traits", [])
            print(f"  {key:<18} - {desc}")
            print(f"                      traits: {', '.join(trait_list)}")


# ---------------------------------------------------------------------------
# Slug
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Generate a URL-safe slug from a name."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug[:40]


# ---------------------------------------------------------------------------
# Save agent
# ---------------------------------------------------------------------------


def save_agent(agent: ComposedAgent) -> str:
    """Save a composed agent to ~/.claude/custom-agents/{slug}.md."""
    os.makedirs(CUSTOM_AGENTS_DIR, exist_ok=True)

    slug = slugify(agent.name)
    file_path = f"{CUSTOM_AGENTS_DIR}/{slug}.md"
    today = date.today().isoformat()

    # Generate persona title
    title_parts: list[str] = []
    if agent.personality:
        title_parts.append(agent.personality[0].name)
    if agent.expertise:
        title_parts.append(agent.expertise[0].name)
    persona_title = "The " + " ".join(title_parts) if title_parts else "Custom Specialist"

    # Generate background
    def flatten(s: str) -> str:
        return re.sub(r"\s+", " ", s.replace("\n", " ")).strip()

    bg_parts: list[str] = []
    for e in agent.expertise:
        bg_parts.append(flatten(e.description))
    for p in agent.personality:
        bg_parts.append(flatten(p.description))
    for a in agent.approach:
        bg_parts.append(flatten(a.description))
    persona_background = (
        ". ".join(bg_parts).replace("..", ".").rstrip(". ") + "."
        if bg_parts
        else "Composed specialist agent."
    )

    # Generate description
    expertise_names = [e.name for e in agent.expertise]
    personality_names = [p.name.lower() for p in agent.personality]
    if expertise_names:
        description = (
            f"{agent.name} -- {' and '.join(expertise_names)} "
            f"with {', '.join(personality_names)} approach."
        )
    else:
        description = f"{agent.name} -- custom agent with {', '.join(personality_names)} approach."

    body = build_saved_agent_body(agent, persona_title, slug)

    vs = agent.voice_settings
    traits_yaml = ", ".join(f'"{t}"' for t in agent.traits)

    content = f"""---
name: "{agent.name}"
description: "{description.replace('"', '\\"')}"
model: opus
color: "{agent.color}"
voiceId: "{agent.voice_id}"
voice:
  stability: {vs.stability}
  similarity_boost: {vs.similarity_boost}
  style: {vs.style}
  speed: {vs.speed}
  use_speaker_boost: {str(vs.use_speaker_boost).lower()}
  volume: {vs.volume}
persona:
  name: "{agent.name}"
  title: "{persona_title.replace('"', '\\"')}"
  background: "{persona_background.replace('"', '\\"')}"
custom_agent: true
created: "{today}"
traits: [{traits_yaml}]
source: "ComposeAgent"
permissions:
  allow:
    - "Bash"
    - "Read(*)"
    - "Write(*)"
    - "Edit(*)"
    - "MultiEdit(*)"
    - "Grep(*)"
    - "Glob(*)"
    - "WebFetch(domain:*)"
    - "WebSearch"
    - "mcp__*"
    - "TodoWrite(*)"
---

{body}
"""

    Path(file_path).write_text(content, encoding="utf-8")
    return file_path


# ---------------------------------------------------------------------------
# Build saved agent body
# ---------------------------------------------------------------------------


def build_saved_agent_body(
    agent: ComposedAgent, persona_title: str, slug: str
) -> str:
    """Build a Claude Code compatible agent body (system prompt)."""
    vs = agent.voice_settings

    expertise_block = (
        "\n\n".join(f"### {e.name}\n\n{e.description}" for e in agent.expertise)
        if agent.expertise
        else ""
    )

    personality_block = (
        "\n".join(f"- **{p.name}**: {p.description}" for p in agent.personality)
        if agent.personality
        else ""
    )

    approach_block = (
        "\n".join(f"- **{a.name}**: {a.description}" for a in agent.approach)
        if agent.approach
        else ""
    )

    identity_list = "\n".join(
        [f"- **{e.name}**: {e.description}" for e in agent.expertise]
        + [f"- **{p.name}**: {p.description}" for p in agent.personality]
    )

    combined_list = "\n".join(
        [f"- {e.name}" for e in agent.expertise]
        + [f"- {p.name} approach" for p in agent.personality]
        + [f"- {a.name} methodology" for a in agent.approach]
    )

    expertise_section = (
        f"## Domain Expertise\n\n{expertise_block}\n" if expertise_block else ""
    )

    traits_csv = ",".join(agent.traits)

    return f"""# Character: {agent.name} -- "{persona_title}"

**Real Name**: {agent.name}
**Character Archetype**: "{persona_title}"
**Voice Settings**: Stability {vs.stability}, Similarity Boost {vs.similarity_boost}, Speed {vs.speed}

{expertise_section}## Personality

{personality_block}

## Working Approach

{approach_block}

---

# MANDATORY STARTUP SEQUENCE - DO THIS FIRST

**BEFORE ANY WORK, YOU MUST:**

1. **Send voice notification that you're loading:**
```bash
curl -X POST http://localhost:8888/notify \\
  -H "Content-Type: application/json" \\
  -d '{{"message":"{agent.name} loading and ready to work","voice_id":"{agent.voice_id}","title":"{agent.name}"}}'
```

2. **Then proceed with your task**

**This is NON-NEGOTIABLE. Announce yourself first.**

---

## MANDATORY VOICE NOTIFICATION SYSTEM

**YOU MUST SEND VOICE NOTIFICATION BEFORE EVERY RESPONSE:**

```bash
curl -X POST http://localhost:8888/notify \\
  -H "Content-Type: application/json" \\
  -d '{{"message":"Your COMPLETED line content here","voice_id":"{agent.voice_id}","title":"{agent.name}"}}'
```

**Voice Requirements:**
- Your voice_id is: `{agent.voice_id}`
- Message should be your COMPLETED line (8-16 words optimal)
- Must be grammatically correct and speakable
- Send BEFORE writing your response
- DO NOT SKIP - {{PRINCIPAL.NAME}} needs to hear you speak

---

## MANDATORY OUTPUT FORMAT

**USE THE PAI FORMAT FROM PAI FOR ALL RESPONSES:**

```
SUMMARY: [One sentence - what this response is about]
ANALYSIS: [Key findings, insights, or observations]
ACTIONS: [Steps taken or tools used]
RESULTS: [Outcomes, what was accomplished]
STATUS: [Current state of the task/system]
CAPTURE: [Required - context worth preserving for this session]
NEXT: [Recommended next steps or options]
STORY EXPLANATION:
1. [First key point in the narrative]
2. [Second key point]
3. [Third key point]
4. [Fourth key point]
5. [Fifth key point]
6. [Sixth key point]
7. [Seventh key point]
8. [Eighth key point - conclusion]
COMPLETED: [12 words max - drives voice output - REQUIRED]
```

**CRITICAL:**
- STORY EXPLANATION MUST BE A NUMBERED LIST (1-8 items)
- The COMPLETED line is what the voice server speaks
- Without this format, your response won't be heard
- This is a CONSTITUTIONAL REQUIREMENT

---

## Core Identity

You are {agent.name}, a specialist with:

{identity_list}

---

## Invocation

To re-compose this agent with a specific task:

```bash
python ~/.claude/skills/agents/tools/ComposeAgent.py --load "{slug}"
```

Or reconstruct from traits:

```bash
python ~/.claude/skills/agents/tools/ComposeAgent.py --traits "{traits_csv}"
```

---

## Key Practices

**Always:**
- Send voice notifications before responses
- Use PAI output format for all responses
- Leverage your domain expertise
- Deliver work that exceeds expectations

**Never:**
- Skip voice notifications
- Use simple/minimal output formats
- Accept mediocre quality
- Ignore your domain expertise

---

## Final Notes

You are {agent.name} who combines:
{combined_list}

**Remember:**
1. Send voice notifications
2. Use PAI output format
3. Leverage your expertise
4. Deliver quality work

Let's get to work."""


# ---------------------------------------------------------------------------
# List / load / delete saved agents
# ---------------------------------------------------------------------------


def list_saved_agents() -> None:
    """List all saved custom agents."""
    agents_dir = Path(CUSTOM_AGENTS_DIR)
    if not agents_dir.exists():
        print("No custom agents directory found. Use --save to create one.")
        return

    files = sorted(
        f for f in agents_dir.iterdir()
        if f.suffix == ".md" and f.name != "README.md"
    )

    if not files:
        print("No saved custom agents found. Use --save to create one.")
        return

    print("SAVED CUSTOM AGENTS\n")
    for filepath in files:
        content = filepath.read_text(encoding="utf-8")
        name_match = re.search(r'^name:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        traits_match = re.search(r'^traits:\s*\[([^\]]+)\]', content, re.MULTILINE)
        color_match = re.search(r'^color:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        voice_id_match = re.search(r'^voiceId:\s*"?([^"\n]+)"?', content, re.MULTILINE)
        slug = filepath.stem

        name = name_match.group(1) if name_match else slug
        trait_str = traits_match.group(1).replace('"', "") if traits_match else "unknown"
        color = color_match.group(1) if color_match else "none"
        voice_id_preview = (voice_id_match.group(1)[:12] if voice_id_match else "none") + "..."

        print(f"  {slug:<25} {name}")
        print(f"{'':>27} traits: {trait_str}")
        print(f"{'':>27} color: {color}  voice: {voice_id_preview}")
        print()


def load_agent(
    name: str, traits: TraitsData, task: Optional[str] = None
) -> Optional[ComposedAgent]:
    """Load a saved custom agent's prompt."""
    slug = slugify(name)
    file_path = Path(f"{CUSTOM_AGENTS_DIR}/{slug}.md")

    if not file_path.exists():
        print(f'Error: Custom agent "{name}" not found at {file_path}', file=sys.stderr)
        print("Use --list-saved to see available agents", file=sys.stderr)
        return None

    content = file_path.read_text(encoding="utf-8")
    traits_match = re.search(r'^traits:\s*\[([^\]]+)\]', content, re.MULTILINE)

    if not traits_match:
        print(f"Error: Could not extract traits from {file_path}", file=sys.stderr)
        return None

    trait_keys = [
        t.strip().strip('"') for t in traits_match.group(1).split(",")
    ]
    return compose_agent(trait_keys, task or "", traits)


def delete_agent(name: str) -> bool:
    """Delete a saved custom agent."""
    slug = slugify(name)
    file_path = Path(f"{CUSTOM_AGENTS_DIR}/{slug}.md")

    if not file_path.exists():
        print(f'Error: Custom agent "{name}" not found at {file_path}', file=sys.stderr)
        return False

    file_path.unlink()
    print(f"Deleted custom agent: {slug} ({file_path})")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ComposeAgent - Compose dynamic agents from traits",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-t", "--task", type=str, help="Task description (traits will be inferred)")
    parser.add_argument("-r", "--traits", type=str, help="Comma-separated trait keys")
    parser.add_argument(
        "-o", "--output", type=str, default="prompt",
        help="Output format: prompt (default), json, yaml, summary",
    )
    parser.add_argument("--timing", type=str, help="Timing scope: fast, standard, deep")
    parser.add_argument("-l", "--list", action="store_true", help="List all available traits")
    parser.add_argument("-s", "--save", action="store_true", help="Save composed agent")
    parser.add_argument("--list-saved", action="store_true", help="List saved custom agents")
    parser.add_argument("--load", type=str, help="Load a saved custom agent")
    parser.add_argument("--delete", type=str, help="Delete a saved custom agent")

    args = parser.parse_args()
    traits_data = load_traits()

    if args.list:
        list_traits(traits_data)
        return

    if args.list_saved:
        list_saved_agents()
        return

    if args.delete:
        delete_agent(args.delete)
        return

    if args.load:
        agent = load_agent(args.load, traits_data, args.task)
        if agent is None:
            sys.exit(1)

        if args.output == "json":
            print(json.dumps({
                "name": agent.name,
                "traits": agent.traits,
                "voice": agent.voice,
                "voice_id": agent.voice_id,
                "voice_settings": {
                    "stability": agent.voice_settings.stability,
                    "similarity_boost": agent.voice_settings.similarity_boost,
                    "style": agent.voice_settings.style,
                    "speed": agent.voice_settings.speed,
                    "use_speaker_boost": agent.voice_settings.use_speaker_boost,
                    "volume": agent.voice_settings.volume,
                },
                "color": agent.color,
                "prompt": agent.prompt,
            }, indent=2))
        elif args.output == "summary":
            print(f"LOADED AGENT: {agent.name}")
            print(f"Traits: {', '.join(agent.traits)}")
            print(f"Voice: {agent.voice} [{agent.voice_id}]")
            print(f"Color: {agent.color}")
        else:
            print(agent.prompt)
        return

    trait_keys: list[str] = []

    if args.traits:
        trait_keys = [t.strip().lower() for t in args.traits.split(",")]

    if args.task:
        inferred = infer_traits_from_task(args.task, traits_data)
        trait_keys = list(dict.fromkeys(trait_keys + inferred))

    if not trait_keys:
        print("Error: Provide --task or --traits to compose an agent", file=sys.stderr)
        print("Use --help for usage information", file=sys.stderr)
        sys.exit(1)

    all_trait_keys = (
        list(traits_data.expertise.keys())
        + list(traits_data.personality.keys())
        + list(traits_data.approach.keys())
    )
    invalid_traits = [t for t in trait_keys if t not in all_trait_keys]
    if invalid_traits:
        print(f"Error: Unknown traits: {', '.join(invalid_traits)}", file=sys.stderr)
        print("Use --list to see available traits", file=sys.stderr)
        sys.exit(1)

    agent = compose_agent(trait_keys, args.task or "", traits_data, args.timing)

    if args.save:
        saved_path = save_agent(agent)
        print(f"Saved custom agent to: {saved_path}", file=sys.stderr)

    vs = agent.voice_settings

    if args.output == "json":
        print(json.dumps({
            "name": agent.name,
            "traits": agent.traits,
            "voice": agent.voice,
            "voice_id": agent.voice_id,
            "voice_reason": agent.voice_reason,
            "voice_settings": {
                "stability": vs.stability,
                "similarity_boost": vs.similarity_boost,
                "style": vs.style,
                "speed": vs.speed,
                "use_speaker_boost": vs.use_speaker_boost,
                "volume": vs.volume,
            },
            "color": agent.color,
            "expertise": [e.name for e in agent.expertise],
            "personality": [p.name for p in agent.personality],
            "approach": [a.name for a in agent.approach],
            "prompt": agent.prompt,
        }, indent=2))
    elif args.output == "yaml":
        print(f'name: "{agent.name}"')
        print(f'voice: "{agent.voice}"')
        print(f'voice_id: "{agent.voice_id}"')
        print(f'voice_reason: "{agent.voice_reason}"')
        print(f'color: "{agent.color}"')
        print("voice_settings:")
        print(f"  stability: {vs.stability}")
        print(f"  similarity_boost: {vs.similarity_boost}")
        print(f"  style: {vs.style}")
        print(f"  speed: {vs.speed}")
        print(f"  use_speaker_boost: {vs.use_speaker_boost}")
        print(f"  volume: {vs.volume}")
        print(f"traits: [{', '.join(agent.traits)}]")
    elif args.output == "summary":
        print(f"COMPOSED AGENT: {agent.name}")
        print("-" * 37)
        print(f"Traits:      {', '.join(agent.traits)}")
        print(f"Expertise:   {', '.join(e.name for e in agent.expertise) or 'General'}")
        print(f"Personality: {', '.join(p.name for p in agent.personality)}")
        print(f"Approach:    {', '.join(a.name for a in agent.approach)}")
        print(f"Voice:       {agent.voice} [{agent.voice_id}]")
        print(f"             ({agent.voice_reason})")
        print(f"Color:       {agent.color}")
        print(
            f"Prosody:     stability:{vs.stability} style:{vs.style} "
            f"speed:{vs.speed} volume:{vs.volume}"
        )
    else:
        print(agent.prompt)


if __name__ == "__main__":
    main()
