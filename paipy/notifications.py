#!/usr/bin/env python3
"""
notifications.py -- Session timing + ntfy push notifications.

Session timing is used by load_context to record session start.
ntfy push is available for hooks that need mobile/desktop notifications.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Literal, Optional, List

SESSION_START_FILE = "/tmp/pai-session-start.txt"


def record_session_start() -> None:
    """Record the session start timestamp."""
    try:
        import time
        Path(SESSION_START_FILE).write_text(str(int(time.time() * 1000)))
    except Exception:
        pass


def get_session_duration_minutes() -> float:
    """Get session duration in minutes since start."""
    try:
        if os.path.exists(SESSION_START_FILE):
            import time
            start_time = int(Path(SESSION_START_FILE).read_text())
            return (time.time() * 1000 - start_time) / 1000 / 60
    except Exception:
        pass
    return 0.0


# ntfy Push (fire-and-forget)

NotificationPriority = Literal["min", "low", "default", "high", "urgent"]


def _load_ntfy_config() -> dict:
    """Load ntfy configuration from settings.json."""
    try:
        import re
        pai_dir = os.environ.get("PAI_DIR", os.path.join(str(Path.home()), ".claude"))
        settings_path = os.path.join(pai_dir, "settings.json")
        if not os.path.exists(settings_path):
            return {"enabled": False, "topic": "", "server": "ntfy.sh"}

        raw = Path(settings_path).read_text()
        # Expand ${VAR} patterns
        raw = re.sub(
            r"\$\{(\w+)\}",
            lambda m: os.environ.get(m.group(1), ""),
            raw,
        )
        settings = json.loads(raw)
        ntfy = settings.get("notifications", {}).get("ntfy", {})
        return {
            "enabled": ntfy.get("enabled", False),
            "topic": ntfy.get("topic", ""),
            "server": ntfy.get("server", "ntfy.sh"),
        }
    except Exception:
        return {"enabled": False, "topic": "", "server": "ntfy.sh"}


def send_push(
    message: str,
    title: Optional[str] = None,
    priority: Optional[NotificationPriority] = None,
    tags: Optional[List[str]] = None,
) -> bool:
    """Send a push notification via ntfy. Returns True on success."""
    config = _load_ntfy_config()
    if not config["enabled"] or not config["topic"]:
        return False

    try:
        headers = {"Content-Type": "text/plain"}
        if title:
            headers["Title"] = title
        if priority:
            priority_map = {"min": "1", "low": "2", "default": "3", "high": "4", "urgent": "5"}
            headers["Priority"] = priority_map.get(priority, "3")
        if tags:
            headers["Tags"] = ",".join(tags)

        url = f"https://{config['server']}/{config['topic']}"
        req = urllib.request.Request(
            url,
            data=message.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
