#!/usr/bin/env python3
"""
Check Anthropic Changes - Comprehensive Update Monitoring

Monitors 30+ official Anthropic sources for updates and provides
AI-powered recommendations for improving PAI infrastructure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx

HOME = Path.home()
SKILL_DIR = HOME / ".claude" / "skills" / "pai-upgrade"
STATE_DIR = SKILL_DIR / "State"
STATE_FILE = STATE_DIR / "last-check.json"
SOURCES_FILE = SKILL_DIR / "sources.json"
LOG_DIR = SKILL_DIR / "Logs"
LOG_FILE = LOG_DIR / "run-history.jsonl"

# Parse args
parser = argparse.ArgumentParser()
parser.add_argument("days", nargs="?", type=int, default=30)
parser.add_argument("--force", action="store_true")

def md5_hash(content: str) -> str:
    return hashlib.md5(content.encode()).hexdigest()

def load_sources() -> dict:
    try:
        return json.loads(SOURCES_FILE.read_text())
    except Exception as e:
        print(f"Failed to load sources.json: {e}", file=sys.stderr); sys.exit(1)

def load_state(days: int) -> dict:
    if not STATE_FILE.exists():
        return {"last_check_timestamp": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(), "sources": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"last_check_timestamp": (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(), "sources": {}}

def save_state(state: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception as e:
        print(f"Failed to save state: {e}", file=sys.stderr)

def log_run(updates_found: int, high: int, medium: int, low: int) -> None:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "updates_found": updates_found,
                 "high_priority": high, "medium_priority": medium, "low_priority": low}
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass

def get_last_run_info() -> Optional[dict]:
    try:
        if not LOG_FILE.exists(): return None
        lines = LOG_FILE.read_text().strip().split("\n")
        if not lines: return None
        last = json.loads(lines[-1])
        last_time = datetime.fromisoformat(last["timestamp"].replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - last_time).days
        return {"days_ago": days_ago, "last_timestamp": last["timestamp"]}
    except Exception:
        return None

async def fetch_blog(source: dict, state: dict, force: bool) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(source["url"])
            if resp.status_code != 200: return []
            html = resp.text
            content_hash = md5_hash(html[:5000])
            state_key = f"blog_{source['name'].lower().replace(' ', '_')}"
            if not force and state.get("sources", {}).get(state_key, {}).get("last_hash") == content_hash:
                return []
            return [{"source": source["name"], "category": "blog", "type": "blog",
                     "title": f"{source['name']}: Latest update", "url": source["url"],
                     "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "hash": content_hash,
                     "priority": source["priority"], "summary": f"New content detected on {source['name']}"}]
    except Exception:
        return []

async def fetch_github_repo(source: dict, state: dict, days: int, force: bool) -> list[dict]:
    updates = []
    token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "PAI-Anthropic-Monitor"}
    if token: headers["Authorization"] = f"token {token}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if source.get("check_commits"):
                since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
                url = f"https://api.github.com/repos/{source['owner']}/{source['repo']}/commits?since={since}&per_page=10"
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    for commit in resp.json():
                        updates.append({"source": source["name"], "category": "github", "type": "commit",
                            "title": commit["commit"]["message"].split("\n")[0], "url": commit["html_url"],
                            "date": commit["commit"]["author"]["date"][:10], "sha": commit["sha"],
                            "priority": source["priority"], "summary": f"Commit by {commit['commit']['author']['name']}"})
            if source.get("check_releases"):
                url = f"https://api.github.com/repos/{source['owner']}/{source['repo']}/releases?per_page=5"
                resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    for release in resp.json():
                        updates.append({"source": source["name"], "category": "github", "type": "release",
                            "title": f"{release['tag_name']}: {release.get('name', 'New Release')}",
                            "url": release["html_url"], "date": release["published_at"][:10],
                            "version": release["tag_name"], "priority": source["priority"],
                            "summary": (release.get("body") or "See release notes")[:200]})
    except Exception:
        pass
    return updates

def generate_recommendation(update: dict) -> str:
    title_lower = update["title"].lower()
    if "skill" in title_lower: return "PAI Impact: CRITICAL for skills ecosystem"
    if "mcp" in title_lower or "mcp" in update.get("source", "").lower(): return "PAI Impact: HIGH - MCP infrastructure"
    if "command" in title_lower: return "PAI Impact: HIGH - Command system update"
    if "agent" in title_lower or "hook" in title_lower: return "PAI Impact: HIGH - Agent/Hook system change"
    if update["type"] == "release": return "PAI Impact: HIGH - Platform update"
    return "PAI Impact: LOW - General awareness"

def assess_relevance(update: dict) -> str:
    title_lower = update["title"].lower()
    high_kw = ["skill", "mcp", "command", "agent", "hook", "breaking", "claude code"]
    if any(k in title_lower for k in high_kw): return "HIGH"
    if update["type"] == "release": return "HIGH"
    low_kw = ["typo", "readme", "test", "minor"]
    if any(k in title_lower for k in low_kw): return "LOW"
    return update.get("priority", "MEDIUM")

async def main_async():
    args_parsed = parser.parse_args()
    days = args_parsed.days
    force = args_parsed.force

    print(f"Checking Anthropic sources for updates...\nDate: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\nLooking back: {days} days\nForce: {force}\n")

    last_run = get_last_run_info()
    if last_run: print(f"Last run: {last_run['days_ago']} days ago")
    else: print("First run - no previous history")

    sources = load_sources()
    state = load_state(days)
    all_updates: list[dict] = []

    # Fetch blogs
    for blog in sources.get("blogs", []):
        all_updates.extend(await fetch_blog(blog, state, force))
    # Fetch GitHub repos
    for repo in sources.get("github_repos", []):
        all_updates.extend(await fetch_github_repo(repo, state, days, force))

    print(f"Fetch complete. Found {len(all_updates)} updates.\n")

    if not all_updates:
        print("No new updates found."); return

    for update in all_updates:
        update["recommendation"] = generate_recommendation(update)
        update["priority"] = assess_relevance(update)

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    all_updates.sort(key=lambda u: (priority_order.get(u["priority"], 2), u.get("date", "")))

    high = [u for u in all_updates if u["priority"] == "HIGH"]
    medium = [u for u in all_updates if u["priority"] == "MEDIUM"]
    low = [u for u in all_updates if u["priority"] == "LOW"]

    print("=" * 80 + f"\n# Anthropic Changes Report\nPeriod: Last {days} days\nUpdates: {len(all_updates)}\n")

    if high:
        print(f"## HIGH PRIORITY ({len(high)})\n")
        for u in high:
            print(f"### [{u['category'].upper()}] {u['title']}\nSource: {u['source']} | Date: {u['date']}\nLink: {u['url']}\n{u['recommendation']}\n---\n")
    if medium:
        print(f"## MEDIUM PRIORITY ({len(medium)})\n")
        for u in medium:
            print(f"- {u['title']} - {u['date']}")
    if low:
        print(f"\n## LOW PRIORITY ({len(low)})\n")
        for u in low:
            print(f"- {u['title']} - {u['date']}")

    # Save state
    new_state = {"last_check_timestamp": datetime.now(timezone.utc).isoformat(), "sources": {**state.get("sources", {})}}
    save_state(new_state)
    log_run(len(all_updates), len(high), len(medium), len(low))
    print("\nState saved successfully")

def main():
    import asyncio
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
