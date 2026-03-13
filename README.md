# PAI — Personal AI Infrastructure

> Magnifying human capabilities through Claude Code.

PAI is a configuration and capability layer that runs inside [Claude Code](https://claude.ai/code). It adds a structured execution engine (The Algorithm), a skills library, lifecycle hooks, persistent memory, and voice output — all wired together through a settings chain and loaded automatically every session.

## Directory Layout

PAI config lives at `~/.config/claude/`. Claude Code expects its config at `~/.claude/` — use a symlink:

```
~/.config/claude/   ← canonical location (this repo)
~/.claude           → symlink to ~/.config/claude
```

```
~/.config/claude/
├── README.md                  # This file
├── CLAUDE.md                  # Master AI prompt (modes, algorithm, routing)
├── settings.json              # Top-level config (extends chain entry point)
├── settings.user.json         # User overrides: API endpoint, models, status line
├── settings.default.json      # Base config: permissions, hooks, env vars, MCP
│
├── install.sh                 # Bootstrap installer (needs only bash + curl)
├── pai-install/               # Guided installer (TypeScript/Bun, web UI)
│
├── pai/                       # System docs, algorithm, user context
│   ├── algorithm/             # Versioned algorithm files + LATEST pointer
│   ├── user/                  # Personal context (identity, projects, goals)
│   └── README.md              # PAI system overview
│
├── hooks/                     # Python lifecycle hooks (PreToolUse, SessionEnd, etc.)
├── skills/                    # Skill library (TitleCase = shareable, _ALLCAPS = personal)
├── memory/                    # Persistent memory (WORK, LEARNING, STATE, RESEARCH)
├── agents/                    # Custom agent definitions
├── scripts/                   # Utility scripts
├── plugins/                   # Plugin data (blocklist, etc.)
├── voice-server/              # Local TTS server (port 8888)
└── banner-server/             # In-session notification server
```

## Setup

### New Install

```bash
# Clone to the canonical location
git clone https://github.com/danielmiessler/PAI ~/.config/claude

# Symlink so Claude Code finds it
ln -s ~/.config/claude ~/.claude

# Run the installer (handles Bun, Git, Claude Code, voice, config)
bash ~/.config/claude/install.sh
```

The installer opens a guided web UI. It collects your name, AI identity, API keys, and voice preferences — then generates your `settings.user.json` and configures everything automatically.

### Manual Setup (no installer)

```bash
git clone https://github.com/danielmiessler/PAI ~/.config/claude
ln -s ~/.config/claude ~/.claude

# Copy and edit the user settings template
cp ~/.config/claude/settings.user.json.example ~/.config/claude/settings.user.json
# Edit settings.user.json: set ANTHROPIC_BASE_URL, model names, etc.
```

### Existing `~/.claude/` Installation

If you already have PAI at `~/.claude/` and want to move to `~/.config/claude/`:

```bash
mv ~/.claude ~/.config/claude
ln -s ~/.config/claude ~/.claude
```

## Settings Chain

Config is split across three files that extend each other:

```
settings.json          (repo root, outermost)
  └── extends: settings.user.json    (your personal overrides, gitignored)
        └── extends: settings.default.json   (base: permissions, hooks, env)
```

**Rule:** Each file should only contain what it owns. Do **not** put a partial `permissions` block in `settings.json` — the entire `permissions` object must live in one file (`settings.default.json`) or it will silently override and discard the `allow`/`deny`/`ask` lists from the parent.

| File | Purpose | Committed |
|------|---------|-----------|
| `settings.json` | Entry point, `extends` chain only | Yes |
| `settings.user.json` | API endpoint, model names, status line | No (gitignored) |
| `settings.default.json` | Permissions, hooks, env vars, MCP servers | Yes |

## How PAI Works

Every Claude Code session:

1. **`CLAUDE.md` loads** — defines execution modes (NATIVE / ALGORITHM / MINIMAL), The Algorithm, and the context routing table
2. **SessionStart hooks fire** — `load_context.py` injects relationship memory, active work, and learning readback
3. **Algorithm mode** — for complex tasks, Claude loads `pai/algorithm/v3.5.0.md` and follows its 7-phase execution loop (Observe → Think → Plan → Build → Execute → Verify → Learn)

Skills activate automatically based on `USE WHEN` triggers in each skill's `SKILL.md`. Hooks enforce security, capture ratings, sync PRDs, and update memory on every tool call and session boundary.

## Key Commands

```bash
# Launch PAI (from anywhere after install)
pai

# Rebuild CLAUDE.md from template
bun pai/tools/BuildCLAUDE.ts

# Run a hook manually
echo '{}' | python hooks/py/load_context.py

# Run a skill tool
bun run skills/Research/Tools/Search.ts

# Validate settings.json
python -c "import json; json.load(open('settings.json'))"

# Check current algorithm version
cat pai/algorithm/LATEST

# Send a test notification
bash banner-server/notify.sh '{"message": "test", "type": "native"}'
```

## Extending PAI

- **Add a skill** — Use the CreateSkill skill (via `/utilities`) or create `skills/YourSkill/SKILL.md` + `Workflows/`
- **Add a hook** — Create handler in `hooks/py/handlers/`, register matcher in `settings.default.json → hooks`
- **Add user context** — Create files in `pai/user/`, reference them in `CLAUDE.md`'s context routing table
- **Personal skills** — Name with `_ALLCAPS/` prefix; they're gitignored and never shared

## Security Notes

- `~/.config/claude/` is private — never commit API keys, session content, or personal data
- `pai/user/` is restricted — its content must never appear in the public PAI repo
- Before any `git push`: verify remote with `git remote -v`
- `settings.user.json` and SSH keys require explicit confirmation to read or edit (enforced by hooks)

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Every tool call asks for permission | `permissions` block in `settings.json` shadows base config | Remove `permissions` from `settings.json`; put `defaultMode` in `settings.default.json` |
| Algorithm file read prompts for permission | Same as above | Same fix |
| `pai` command not found | Shell alias not loaded | `source ~/.zshrc` |
| Hooks not firing | `PAI_DIR` env var wrong | Check `settings.default.json → env.PAI_DIR` matches your actual path |
| Voice server not responding | Port 8888 in use | `lsof -ti:8888 \| xargs kill` |
| `bun: command not found` | Bun not in PATH | `export PATH="$HOME/.bun/bin:$PATH"` |

## More

- `pai/README.md` — PAI system internals (algorithm, skills, hooks, memory)
- `pai-install/README.md` — Installer architecture and WebSocket protocol
- `pai/algorithm/v3.5.0.md` — The Algorithm (load automatically in ALGORITHM mode)
