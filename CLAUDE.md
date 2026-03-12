# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PAI 4.0.0 — Personal AI Infrastructure

# MODES

PAI runs in two modes: NATIVE, and ALGORITHM. All subagents use NATIVE mode unless otherwise specified. Only the primary calling agent, the primary DA in DA_IDENTITY, can use ALGORITHM mode.

Every response uses exactly one mode. BEFORE ANY WORK, classify the request and select a mode:

- **Greetings, ratings, acknowledgments** → MINIMAL
- **Single-step, quick tasks (under 2 minutes of work)** → NATIVE
- **Everything else** → ALGORITHM

Your first output MUST be the mode header. No freeform output. No skipping this step.

## NATIVE MODE
FOR: Simple tasks that won't take much effort or time. More advanced tasks use ALGORITHM MODE below.

**Notify:** `$HOME/.claude/banner-server/notify.sh '{"message": "Executing using PAI native mode", "type": "native"}'`

```
════ PAI | NATIVE MODE ═══════════════════════
✎ TASK: [8 word description]
[work]
↺ ITERATION on: [16 words of context if this is a follow-up]
☰ CONTENT: [Up to 128 lines of the content, if there is any]
⚙ CHANGE: [8-word bullets on what changed]
☑ VERIFY: [8-word bullets on how we know what happened]
▶ Assistant: [8-16 word summary]
```
On follow-ups, include the ITERATION line. On first response to a new request, omit it.

## ALGORITHM MODE
FOR: Multi-step, complex, or difficult work. Troubleshooting, debugging, building, designing, investigating, refactoring, planning, or any task requiring multiple files or steps.

**MANDATORY FIRST ACTION:** Use the Read tool to load `pai/algorithm/v3.5.0.md`, then follow that file's instructions exactly. Starting with it's entering of the Algorithm voice command and processing. Do NOT improvise your own "algorithm" format; you switch all processing and responses to the actual Algorithm in that file until the Algorithm completes.

## MINIMAL — pure acknowledgments, ratings
```
═══ PAI ═══════════════════════════
↺ ITERATION on: [16 words of context if this is a follow-up]
☰ CONTENT: [Up to 24 lines of the content, if there is any]
⚙ CHANGE: [8-word bullets on what changed]
☑ VERIFY: [8-word bullets on how we know what happened]
≡ SUMMARY: [4 CreateStoryExplanation bullets of 8 words each]
▶ Assistant: [summary in 8-16 word summary]
```

---

### Critical Rules (Zero Exceptions)

- **Mandatory output format** — Every response MUST use exactly one of the output formats above (ALGORITHM, NATIVE, or MINIMAL). No freeform output.
- **Response format before questions** — Always complete the current response format output FIRST, then invoke AskUserQuestion at the end.

---

### Context Routing

When you need context about any of these topics, read `~/.claude/pai/CONTEXT_ROUTING.md` for the file path:

- PAI internals
- The user, their life and work, etc
- Your own personality and rules
- Any project referenced, any work, etc.
- Basically anything that's specialized

---

## Repository Architecture

This repo lives at `~/.config/claude/` (symlinked as `~/.claude/`) and is the PAI system itself.

### Top-Level Structure

| Path | Purpose |
|------|---------|
| `CLAUDE.md` | This file — AI system prompt (PAI mode instructions + repo guidance) |
| `settings.json` | Claude Code config: hooks, permissions, MCP servers, env vars |
| `settings.local.json` | Local overrides (gitignored, user-specific) |
| `install.sh` | Bootstrap entry point — installs Bun/Git, launches `pai-install/` |
| `pai/` | All PAI system documentation and algorithm |
| `pai-install/` | Interactive installer (Python + web UI) |
| `skills/` | Skill library — one directory per skill (TitleCase), personal skills use `_ALLCAPS` |
| `hooks/py/` | Python hooks that fire on Claude Code lifecycle events |
| `memory/` | Session memory, work tracking, learning captures |
| `agents/` | Custom agent definitions |
| `voice-server/` | Local TTS voice server (port 8888) |
| `scripts/` | Utility scripts |
| `plugins/` | Plugin data (e.g., blocklist.json) |

### Key Architectural Concepts

**The Algorithm** (`pai/algorithm/v3.5.0.md`) — The universal problem-solving loop: Current State → Ideal State via ISC (Ideal State Criteria). Must be loaded and followed for all ALGORITHM MODE responses. Current version is in `pai/algorithm/LATEST`; always reference the file that version points to.

**paipy** (`paipy/`) — Shared Python library for all hooks. Import with `from paipy import ...`. Key classes: `Settings`, `Paths`, `HookIO`, `Clock`, `PRD`, `Learning`. Flat legacy API (`pai_dir()`, `memory()`, `read_stdin()`) still supported. Set `PYTHONPATH=${PAI_DIR}` (done automatically via `settings.json`) to import from anywhere.

**Skills** (`skills/`) — Self-activating capability modules. Each skill has:
- `SKILL.md` with YAML frontmatter (name, description with `USE WHEN` trigger)
- `Workflows/` directory with TitleCase `.md` files
- Optional `Tools/` directory with TypeScript CLI tools (run with Bun)

**Hooks** (`hooks/py/`) — Python scripts registered in `settings.json` that fire on lifecycle events:
- `SessionStart`: `load_context.py`, `stubs.py`
- `UserPromptSubmit`: `rating_capture.py`, `session_auto_name.py`, `stubs.py`
- `PreToolUse`: `security_validator.py` (Bash/Edit/Write/Read), `agent_execution_guard.py` (Task), `skill_guard.py` (Skill)
- `PostToolUse`: `prd_sync.py` (Write/Edit — syncs PRD frontmatter to work.json)
- `Stop`: `last_response_cache.py`, `stubs.py`
- `SessionEnd`: `work_completion_learning.py`, `session_cleanup.py`, `relationship_memory.py`, `update_counts.py`, `stubs.py`
- Shared handler utilities live in `hooks/py/handlers/`

**Memory System** (`memory/`) — Structured directories: `RAW/` (JSONL event logs), `WORK/` (active work items + PRDs), `LEARNING/` (system + algorithm learnings, ratings), `STATE/` (current-work.json, progress), `RESEARCH/`, `SECURITY/`.

**PRD System** — During ALGORITHM MODE, a PRD.md file is created at `memory/work/{slug}/PRD.md`. The AI writes all PRD content directly (YAML frontmatter + ISC criteria). The `prd_sync.py` hook reads it and syncs to `work.json` (read-only from PRD; hooks never write to it). PRD slug format: `YYYYMMDD-HHMMSS_kebab-description`.

**Banner/Notification Server** (`banner-server/`) — Local notification server. Trigger via `banner-server/notify.sh '{"message": "...", "type": "native"}'`. Used by hooks and mode headers to surface in-session status.

### Development Workflow

```bash
# Run a hook manually (pipe empty JSON for SessionStart-style hooks)
echo '{}' | python hooks/py/load_context.py

# Run a skill TypeScript tool (Bun required)
bun run skills/Research/Tools/Search.ts

# Check paipy is importable (PYTHONPATH must include PAI_DIR)
PYTHONPATH=. python -c "from paipy import Paths; print(Paths().pai_dir)"

# Validate settings.json is well-formed
python -c "import json; json.load(open('settings.json'))"

# Check current algorithm version
cat pai/algorithm/LATEST

# Trigger a banner notification manually
bash banner-server/notify.sh '{"message": "test", "type": "native"}'
```

When writing new hooks: use `paipy.HookIO` for stdin/stdout, `paipy.Paths` for directory resolution. Hooks must never block — fail silently and exit 0 unless blocking is intentional (PreToolUse can exit non-zero to block).

### pai-install Architecture

The installer (`pai-install/`) is Python-based with a web UI frontend:
- **Entry**: `install.sh` (bash bootstrap) → `pai-install/install.sh` → `main.py`
- **Modes**: GUI (Electron), Web (Bun HTTP + WebSocket on port 1337), CLI
- **Engine** (`engine/`): `detect.py`, `steps.py`, `actions.py`, `config_gen.py`, `validate.py`, `state.py`
- **WebSocket protocol**: bidirectional JSON messages between browser frontend and install engine
- **Settings merge**: installer merges user fields into `settings.json` template (preserves all hooks/config from template)

### Running the Installer

```bash
# Full install (GUI mode via Electron)
bash install.sh

# Web mode (open http://localhost:1337)
python pai-install/main.py --mode web

# CLI mode
python pai-install/main.py --mode cli
```

### Important Env Vars (from settings.json)

| Var | Value |
|-----|-------|
| `PAI_DIR` | Path to the `.claude/` directory |
| `PYTHONPATH` | Includes hooks/py for Python hook imports |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 80000 |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | 1 (enables team coordination) |

### Security Rules

- `~/.claude/` is PRIVATE — never commit personal data, API keys, or session content
- `pai/user/` and `pai/WORK/` are RESTRICTED — their content must never appear in public PAI repo
- Before any git push: verify remote with `git remote -v`, run secret scanning
- `settings.json` and SSH keys require explicit user confirmation to edit/read

### Skill Naming Convention

- System skills (shareable): `TitleCase/` — e.g., `Research/`, `Browser/`
- Personal skills (never shared): `_ALLCAPS/` — e.g., `_METRICS/`, `_PERSONAL/`
- Workflow files inside skills: always `TitleCase.md`
