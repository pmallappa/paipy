#!/usr/bin/env python3
"""
GetTranscript.py - Extract transcript from YouTube video

Usage:
  python GetTranscript.py <youtube-url>
  python GetTranscript.py <youtube-url> --save <output-file>

Examples:
  python GetTranscript.py "https://www.youtube.com/watch?v=abc123"
  python GetTranscript.py "https://youtu.be/abc123" --save transcript.txt
"""

import subprocess
import sys
from pathlib import Path

HELP = """
GetTranscript - Extract transcript from YouTube video using fabric

Usage:
  python GetTranscript.py <youtube-url> [options]

Options:
  --save <file>    Save transcript to file
  --help           Show this help message

Examples:
  python GetTranscript.py "https://www.youtube.com/watch?v=abc123"
  python GetTranscript.py "https://youtu.be/xyz789" --save ~/transcript.txt

Supported URL formats:
  - https://www.youtube.com/watch?v=VIDEO_ID
  - https://youtu.be/VIDEO_ID
  - https://www.youtube.com/watch?v=VIDEO_ID&t=123
  - https://youtube.com/shorts/VIDEO_ID
"""


def main() -> None:
    args = sys.argv[1:]

    if "--help" in args or not args:
        print(HELP)
        sys.exit(0)

    # Find URL
    url = next(
        (arg for arg in args if "youtube.com" in arg or "youtu.be" in arg),
        None,
    )

    if not url:
        print("Error: No YouTube URL provided", file=sys.stderr)
        print("\nUsage: python GetTranscript.py <youtube-url>")
        sys.exit(1)

    # Check for --save option
    output_file = None
    if "--save" in args:
        save_idx = args.index("--save")
        if save_idx + 1 < len(args):
            output_file = args[save_idx + 1]

    print(f"Extracting transcript from: {url}")

    try:
        result = subprocess.run(
            ["fabric", "-y", url],
            capture_output=True,
            text=True,
            timeout=120,
        )

        transcript = result.stdout

        if not transcript.strip():
            print("No transcript available for this video", file=sys.stderr)
            sys.exit(1)

        print(f"Transcript extracted: {len(transcript)} characters\n")

        if output_file:
            Path(output_file).write_text(transcript, encoding="utf-8")
            print(f"Saved to: {output_file}")
        else:
            print("--- TRANSCRIPT START ---\n")
            print(transcript)
            print("\n--- TRANSCRIPT END ---")

    except subprocess.TimeoutExpired:
        print("Error: Transcript extraction timed out", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'fabric' command not found. Install fabric first.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("Failed to extract transcript", file=sys.stderr)
        print("Possible reasons:")
        print("  - Video has no captions/transcript")
        print("  - Video is private or restricted")
        print("  - Invalid URL")
        sys.exit(1)


if __name__ == "__main__":
    main()
