#!/usr/bin/env python3
"""
YouTubeApi - YouTube Data API v3 client

Usage:
  python YouTubeApi.py <command> [options]

Commands:
  channel              Get channel statistics
  videos [count]       Get recent videos with stats (default: 10)
  video <id|title>     Get stats for specific video
  search <query>       Search channel videos

Environment:
  YOUTUBE_API_KEY      API key (required)
  YOUTUBE_CHANNEL_ID   Channel ID (default: UCnCikd0s4i9KoDtaHPlK-JA)
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

# ANSI colors
RESET = "\x1b[0m"
BOLD = "\x1b[1m"
GREEN = "\x1b[32m"
YELLOW = "\x1b[33m"
BLUE = "\x1b[34m"
CYAN = "\x1b[36m"
RED = "\x1b[31m"
DIM = "\x1b[2m"


# Load environment
def load_env() -> dict[str, str]:
    env_path = (
        Path(os.environ["PAI_CONFIG_DIR"]) / ".env"
        if os.environ.get("PAI_CONFIG_DIR")
        else Path.home() / ".config" / "PAI" / ".env"
    )
    env: dict[str, str] = {}
    try:
        for line in env_path.read_text().splitlines():
            import re
            match = re.match(r'^([^#=]+)=(.*)$', line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip().strip("'\"")
                env[key] = value
    except FileNotFoundError:
        pass
    return env


env = load_env()
API_KEY = os.environ.get("YOUTUBE_API_KEY") or env.get("YOUTUBE_API_KEY", "")
CHANNEL_ID = os.environ.get("YOUTUBE_CHANNEL_ID") or env.get("YOUTUBE_CHANNEL_ID", "UCnCikd0s4i9KoDtaHPlK-JA")
BASE_URL = "https://www.googleapis.com/youtube/v3"

if not API_KEY:
    print(f"{RED}Error: YOUTUBE_API_KEY not set{RESET}", file=sys.stderr)
    sys.exit(1)


def api_get(endpoint: str, params: dict[str, str]) -> dict:
    if httpx is None:
        raise RuntimeError("httpx required: pip install httpx")

    params["key"] = API_KEY
    response = httpx.get(f"{BASE_URL}{endpoint}", params=params, timeout=30)
    if response.status_code != 200:
        error = response.json()
        raise RuntimeError(error.get("error", {}).get("message", f"API error: {response.status_code}"))
    return response.json()


def format_num(n: Any) -> str:
    return f"{int(n):,}"


# Commands

def get_channel() -> None:
    data = api_get("/channels", {"part": "snippet,statistics", "id": CHANNEL_ID})
    ch = data["items"][0]
    print(f"\n{BOLD}{CYAN}Channel: {ch['snippet']['title']}{RESET}")
    print(f"{DIM}{ch['snippet'].get('customUrl', '')}{RESET}\n")
    print(f"{GREEN}Subscribers:{RESET} {format_num(ch['statistics']['subscriberCount'])}")
    print(f"{GREEN}Total Views:{RESET} {format_num(ch['statistics']['viewCount'])}")
    print(f"{GREEN}Videos:{RESET}      {format_num(ch['statistics']['videoCount'])}")


def get_recent_videos(count: int = 10) -> None:
    search = api_get("/search", {
        "part": "snippet",
        "channelId": CHANNEL_ID,
        "order": "date",
        "maxResults": str(count),
        "type": "video",
    })

    video_ids = ",".join(v["id"]["videoId"] for v in search["items"])

    stats = api_get("/videos", {"part": "statistics", "id": video_ids})
    stats_map = {v["id"]: v["statistics"] for v in stats["items"]}

    print(f"\n{BOLD}{CYAN}Recent Videos{RESET}\n")
    print(f"{DIM}{'Title':<50} {'Views':>10} {'Likes':>8}{RESET}")
    print("-" * 70)

    for video in search["items"]:
        s = stats_map.get(video["id"]["videoId"], {})
        title = video["snippet"]["title"][:48].ljust(50)
        views = format_num(s.get("viewCount", 0)).rjust(10)
        likes = format_num(s.get("likeCount", 0)).rjust(8)
        print(f"{title} {GREEN}{views}{RESET} {YELLOW}{likes}{RESET}")


def get_video_stats(query: str) -> None:
    import re
    video_id = query

    if not re.match(r"^[a-zA-Z0-9_-]{11}$", query):
        search = api_get("/search", {
            "part": "snippet",
            "channelId": CHANNEL_ID,
            "q": query,
            "type": "video",
            "maxResults": "1",
        })
        if not search["items"]:
            print(f"{RED}No video found matching: {query}{RESET}", file=sys.stderr)
            sys.exit(1)
        video_id = search["items"][0]["id"]["videoId"]

    data = api_get("/videos", {"part": "snippet,statistics,contentDetails", "id": video_id})

    if not data["items"]:
        print(f"{RED}Video not found: {video_id}{RESET}", file=sys.stderr)
        sys.exit(1)

    v = data["items"][0]
    from datetime import datetime
    published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))

    print(f"\n{BOLD}{CYAN}{v['snippet']['title']}{RESET}")
    print(f"{DIM}https://youtube.com/watch?v={v['id']}{RESET}\n")
    print(f"{GREEN}Views:{RESET}    {format_num(v['statistics']['viewCount'])}")
    print(f"{GREEN}Likes:{RESET}    {format_num(v['statistics']['likeCount'])}")
    print(f"{GREEN}Comments:{RESET} {format_num(v['statistics']['commentCount'])}")
    print(f"{GREEN}Published:{RESET} {published.strftime('%Y-%m-%d')}")


def search_videos(query: str) -> None:
    data = api_get("/search", {
        "part": "snippet",
        "channelId": CHANNEL_ID,
        "q": query,
        "type": "video",
        "maxResults": "10",
    })

    print(f'\n{BOLD}{CYAN}Search: "{query}"{RESET}\n')

    for v in data["items"]:
        print(f"{GREEN}{v['snippet']['title']}{RESET}")
        print(f"  {DIM}https://youtube.com/watch?v={v['id']['videoId']}{RESET}")


def show_help() -> None:
    print(f"""
{BOLD}YouTubeApi{RESET} - YouTube Data API v3 client

{CYAN}Usage:{RESET}
  python YouTubeApi.py <command> [options]

{CYAN}Commands:{RESET}
  channel              Get channel statistics
  videos [count]       Get recent videos with stats (default: 10)
  video <id|title>     Get stats for specific video
  search <query>       Search channel videos

{CYAN}Examples:{RESET}
  python YouTubeApi.py channel
  python YouTubeApi.py videos 5
  python YouTubeApi.py video "ThreatLocker"
  python YouTubeApi.py search "AI agents"
""")


# Main

def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else None
    rest = args[1:]

    if cmd == "channel":
        get_channel()
    elif cmd == "videos":
        count = int(rest[0]) if rest else 10
        get_recent_videos(count)
    elif cmd == "video":
        if not rest:
            print(f"{RED}Error: video ID or title required{RESET}", file=sys.stderr)
            sys.exit(1)
        get_video_stats(" ".join(rest))
    elif cmd == "search":
        if not rest:
            print(f"{RED}Error: search query required{RESET}", file=sys.stderr)
            sys.exit(1)
        search_videos(" ".join(rest))
    elif cmd in ("--help", "-h", None):
        show_help()
    else:
        print(f"{RED}Unknown command: {cmd}{RESET}", file=sys.stderr)
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
