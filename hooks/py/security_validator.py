#!/usr/bin/env python3
"""
PreToolUse: Bash, Edit, Write, Read — security validation.
Blocks dangerous patterns, logs security events.
"""
import json
import re
import sys
from pathlib import Path
from paipy import read_stdin, allow, block, ask, memory, now_iso, now_filename

# Patterns that are hard-blocked
BLOCK_PATTERNS = [
    (r"rm\s+-rf\s+/(?!\w)", "Recursive delete of root"),
    (r"rm\s+-rf\s+~(?!\w)", "Recursive delete of home"),
    (r":\(\)\{\s*:\|:&\s*\};:", "Fork bomb"),
    (r"dd\s+if=/dev/zero\s+of=/dev/", "Disk wipe via dd"),
    (r"mkfs\.", "Disk format"),
    (r">\s*/dev/sd[a-z]", "Direct disk write"),
    (r"chmod\s+777\s+~", "Insecure chmod on home"),
]

# Patterns that require confirmation
ASK_PATTERNS = [
    (r"git\s+push\s+--force", "Force push"),
    (r"git\s+reset\s+--hard", "Hard reset"),
    (r"git\s+clean\s+-[fd]", "Git clean"),
    (r"DROP\s+TABLE", "SQL DROP TABLE"),
    (r"DROP\s+DATABASE", "SQL DROP DATABASE"),
    (r"TRUNCATE\s+TABLE", "SQL TRUNCATE"),
]

# Sensitive paths that should not be written
PROTECTED_WRITE_PATHS = [
    r"~/.ssh/",
    r"~/.aws/credentials",
    r"~/.gnupg/private",
    r"~/.claude/settings\.json",
]


def strip_quoted(cmd: str) -> str:
    """Remove quoted string literals to avoid false-positives on echo/printf args."""
    cmd = re.sub(r"'[^']*'", "", cmd)
    cmd = re.sub(r'"[^"]*"', "", cmd)
    return cmd


def check_bash(command: str) -> tuple[str, str] | None:
    """Returns (action, reason) or None if clean.
    Checks unquoted portions only so that echo/printf with dangerous strings
    in their arguments are not blocked.
    """
    unquoted = strip_quoted(command)
    for pattern, reason in BLOCK_PATTERNS:
        if re.search(pattern, unquoted, re.IGNORECASE):
            return "block", reason
    for pattern, reason in ASK_PATTERNS:
        if re.search(pattern, unquoted, re.IGNORECASE):
            return "ask", reason
    return None


def check_path(path: str, action: str) -> tuple[str, str] | None:
    home = str(Path.home())
    expanded = path.replace("~", home)
    if action in ("Write", "Edit"):
        for pattern in PROTECTED_WRITE_PATHS:
            resolved = pattern.replace("~", home)
            if expanded.startswith(resolved) or re.search(pattern, path):
                return "ask", f"Writing to protected path: {path}"
    return None


def log_event(tool: str, detail: str, decision: str):
    log_dir = memory("SECURITY") / now_iso()[:4] / now_iso()[5:7]
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": now_iso(),
        "tool": tool,
        "detail": detail,
        "decision": decision,
    }
    log_file = log_dir / f"security-{now_filename()}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def main():
    data = read_stdin()
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {})

    result = None

    if tool == "Bash":
        cmd = inp.get("command", "")
        result = check_bash(cmd)
        if result:
            log_event(tool, cmd[:200], result[0])

    elif tool in ("Write", "Edit", "MultiEdit"):
        path = inp.get("file_path", "")
        result = check_path(path, tool)
        if result:
            log_event(tool, path, result[0])

    elif tool == "Read":
        path = inp.get("file_path", "")
        # Only block reads of private keys / credentials
        sensitive = [r"\.pem$", r"\.key$", r"id_rsa", r"credentials\.json$"]
        for pat in sensitive:
            if re.search(pat, path):
                result = ("ask", f"Reading sensitive file: {path}")
                log_event(tool, path, "ask")
                break

    if result is None:
        allow()
    elif result[0] == "block":
        block(result[1])
    elif result[0] == "ask":
        ask(result[1])


if __name__ == "__main__":
    main()
