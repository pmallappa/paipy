"""paipy — PAI Python library.

OOP-based library for Claude Code hooks, tools, and migration utilities.

New API (classes):
    from paipy import Settings, Paths, Clock, HookIO
    settings = Settings.get()
    settings.da_name()

Legacy API (flat functions — backward compatible):
    from paipy import read_stdin, allow, block, pai_dir, memory, now_iso

Set PYTHONPATH=${PAI_DIR} to make this package importable from anywhere.
"""

__version__ = "1.0.0"

# ── Core classes ───────────────────────────────────────────────────────────
from ._paths import Paths
from .settings import Settings, Identity, Principal, VoiceProsody, VoicePersonality
from .clock import Clock, TimestampComponents
from .hook_io import HookIO, HookInput
from .tab import TabState
from .validators import Validators
from .changes import ChangeDetector, FileChange, IntegrityState
from .prd import PRD, CriterionEntry
from .learning import Learning
from .notifications import record_session_start, get_session_duration_minutes, send_push

# ── Flat API (backward compatible) ─────────────────────────────────────────

# Paths
pai_dir = Paths.pai_dir
project_dir = Paths.project_dir
data_dir = Paths.data_dir
memory = Paths.memory
settings_path = Paths.settings_file

# Settings
def load_settings() -> dict:
    """Load settings.json as a plain dict. Returns {} on failure."""
    return Settings.get().load()

def get_identity() -> Identity:
    return Settings.get().identity()

def get_principal() -> Principal:
    return Settings.get().principal()

def get_da_name() -> str:
    return Settings.get().da_name()

def get_principal_name() -> str:
    return Settings.get().principal_name()

def get_voice_id() -> str:
    return Settings.get().voice_id()

def get_settings() -> dict:
    return Settings.get().load()

def get_default_identity() -> Identity:
    return Identity()

def get_default_principal() -> Principal:
    return Principal()

def get_algorithm_voice():
    return Settings.get().algorithm_voice()

def get_voice_prosody():
    return Settings.get().voice_prosody()

def get_voice_personality():
    return Settings.get().voice_personality()

def clear_cache() -> None:
    Settings._instance = None

SETTINGS_PATH = str(Paths.settings_file())

# Clock
now_iso = Clock.iso
now_filename = Clock.filename
now_ym = Clock.year_month
now_date = Clock.date
get_pst_timestamp = Clock.timestamp
get_pst_date = Clock.date
get_year_month = Clock.year_month
get_iso_timestamp = Clock.iso
get_filename_timestamp = Clock.filename
get_pst_components = Clock.components
get_timezone_display = Clock.timezone_display

# Hook IO
read_stdin = HookIO.read
read_hook_input = HookIO.read_structured
allow = HookIO.allow
block = HookIO.block
ask = HookIO.ask
inject = HookIO.inject
is_subagent = HookIO.is_subagent

# Tab state
set_tab_state = TabState.set_state
read_tab_state = TabState.read_state
strip_prefix = TabState.strip_prefix
set_phase_tab = TabState.set_phase
get_session_one_word = TabState.get_session_one_word
persist_kitty_session = TabState.persist_session
cleanup_kitty_session = TabState.cleanup_session

# Validators
is_valid_voice_completion = Validators.is_valid_voice_completion
get_voice_fallback = Validators.get_voice_fallback
is_valid_working_title = Validators.is_valid_working_title
is_valid_completion_title = Validators.is_valid_completion_title
is_valid_question_title = Validators.is_valid_question_title
trim_to_valid_title = Validators.trim_to_valid_title
get_working_fallback = Validators.get_working_fallback
get_completion_fallback = Validators.get_completion_fallback
get_question_fallback = Validators.get_question_fallback
gerund_to_past_tense = Validators.gerund_to_past_tense

# Change detection
parse_tool_use_blocks = ChangeDetector.parse_tool_use_blocks
categorize_change = ChangeDetector.categorize_change
is_significant_change = ChangeDetector.is_significant_change
should_document_changes = ChangeDetector.should_document_changes
read_integrity_state = ChangeDetector.read_integrity_state
is_in_cooldown = ChangeDetector.is_in_cooldown
hash_changes = ChangeDetector.hash_changes
is_duplicate_run = ChangeDetector.is_duplicate_run
get_cooldown_end_time = ChangeDetector.get_cooldown_end_time
determine_significance = ChangeDetector.determine_significance
infer_change_type = ChangeDetector.infer_change_type
generate_descriptive_title = ChangeDetector.generate_descriptive_title

# PRD
get_work_dir = PRD.get_work_dir
get_work_json = PRD.get_work_json
find_latest_prd = PRD.find_latest_prd
parse_frontmatter = PRD.parse_frontmatter
write_frontmatter_field = PRD.write_frontmatter_field
count_criteria = PRD.count_criteria
parse_criteria_list = PRD.parse_criteria_list
read_registry = PRD.read_registry
write_registry = PRD.write_registry
sync_to_work_json = PRD.sync_to_work_json
update_session_name_in_work_json = PRD.update_session_name_in_work_json
upsert_session = PRD.upsert_session
curate_title = PRD.curate_title
generate_prd_filename = PRD.generate_prd_filename
generate_prd_id = PRD.generate_prd_id
generate_prd_template = PRD.generate_prd_template

# Learning
get_learning_category = Learning.get_learning_category
is_learning_capture = Learning.is_learning_capture
load_learning_digest = Learning.load_learning_digest
load_wisdom_frames = Learning.load_wisdom_frames
load_failure_patterns = Learning.load_failure_patterns
load_signal_trends = Learning.load_signal_trends
