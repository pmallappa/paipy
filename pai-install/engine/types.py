"""
PAI Installer v4.0 -- Type Definitions
Shared types for engine, CLI, and web frontends.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional, Union


# -- System Detection -------------------------------------------------------


@dataclass
class OSInfo:
    platform: Literal["darwin", "linux"]
    arch: str
    version: str
    name: str  # e.g., "macOS 15.2" or "Ubuntu 24.04"


@dataclass
class ShellInfo:
    name: str
    version: str
    path: str


@dataclass
class ToolInfo:
    installed: bool
    version: Optional[str] = None
    path: Optional[str] = None


@dataclass
class BrewInfo:
    installed: bool
    path: Optional[str] = None


@dataclass
class ToolsInfo:
    bun: ToolInfo
    git: ToolInfo
    claude: ToolInfo
    node: ToolInfo
    brew: BrewInfo


@dataclass
class ExistingInfo:
    pai_installed: bool
    pai_version: Optional[str] = None
    settings_path: Optional[str] = None
    has_api_keys: bool = False
    eleven_labs_key_found: bool = False
    backup_paths: List[str] = field(default_factory=list)


@dataclass
class DetectionResult:
    os: OSInfo
    shell: ShellInfo
    tools: ToolsInfo
    existing: ExistingInfo
    timezone: str
    home_dir: str
    pai_dir: str  # resolved ~/.claude
    config_dir: str  # resolved ~/.config/PAI


# -- Install Steps -----------------------------------------------------------

StepId = Literal[
    "system-detect",
    "prerequisites",
    "api-keys",
    "identity",
    "repository",
    "configuration",
    "voice",
    "validation",
]


@dataclass
class StepDefinition:
    id: StepId
    name: str
    description: str
    number: int  # 1-8
    required: bool
    depends_on: List[StepId]
    condition: Optional[Callable[["InstallState"], bool]] = None


StepStatus = Literal["pending", "active", "completed", "skipped", "failed"]


# -- Install State -----------------------------------------------------------


@dataclass
class CollectedData:
    eleven_labs_key: Optional[str] = None
    principal_name: Optional[str] = None
    timezone: Optional[str] = None
    ai_name: Optional[str] = None
    catchphrase: Optional[str] = None
    projects_dir: Optional[str] = None
    temperature_unit: Optional[Literal["fahrenheit", "celsius"]] = None
    voice_type: Optional[Literal["female", "male", "custom"]] = None
    custom_voice_id: Optional[str] = None


@dataclass
class StepError:
    step: StepId
    message: str
    timestamp: str
    recoverable: bool


@dataclass
class InstallState:
    version: str
    started_at: str
    updated_at: str
    current_step: StepId
    completed_steps: List[StepId]
    skipped_steps: List[StepId]
    mode: Literal["cli", "web"]
    detection: Optional[DetectionResult] = None
    collected: CollectedData = field(default_factory=CollectedData)
    install_type: Optional[Literal["fresh", "upgrade"]] = None
    errors: List[StepError] = field(default_factory=list)


# -- Configuration -----------------------------------------------------------


@dataclass
class PAIConfig:
    principal_name: str
    timezone: str
    ai_name: str
    catchphrase: str
    projects_dir: Optional[str] = None
    temperature_unit: Optional[Literal["fahrenheit", "celsius"]] = None
    voice_type: Optional[str] = None
    voice_id: Optional[str] = None
    pai_dir: str = ""
    config_dir: str = ""


# -- WebSocket Protocol -------------------------------------------------------

# Server -> Client messages (represented as dicts in Python)
# Client -> Server messages (represented as dicts in Python)

# These are typed as dicts for JSON serialization.
# Use type annotations in function signatures for documentation.

ServerMessage = Dict[str, Any]
ClientMessage = Dict[str, Any]


# -- Validation ---------------------------------------------------------------


@dataclass
class ValidationCheck:
    name: str
    passed: bool
    detail: str
    critical: bool


@dataclass
class InstallSummary:
    pai_version: str
    principal_name: str
    ai_name: str
    timezone: str
    voice_enabled: bool
    voice_mode: str
    catchphrase: str
    install_type: Literal["fresh", "upgrade"]
    completed_steps: int
    total_steps: int


# -- Engine Events -------------------------------------------------------------

EngineEvent = Dict[str, Any]
EngineEventHandler = Callable[[EngineEvent], Any]


# -- Voice ---------------------------------------------------------------------

DEFAULT_VOICES = {
    "male": "pNInz6obpgDQGcFmaJgB",   # Adam
    "female": "21m00Tcm4TlvDq8ikWAM",  # Rachel
}
