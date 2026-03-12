#!/usr/bin/env python3
"""
ExtractTranscript.py

CLI tool for extracting transcripts from audio/video files using OpenAI Whisper API
Part of PAI's extracttranscript skill

Usage:
  python ExtractTranscript.py <file-or-folder> [options]

Examples:
  python ExtractTranscript.py audio.m4a
  python ExtractTranscript.py video.mp4 --format srt
  python ExtractTranscript.py ~/Podcasts/ --batch
"""

import json
import os
import sys
from pathlib import Path

try:
    import openai
except ImportError:
    print("Error: openai package not installed. Run: pip install openai", file=sys.stderr)
    sys.exit(1)

SUPPORTED_FORMATS = [".m4a", ".mp3", ".wav", ".flac", ".ogg", ".mp4", ".mpeg", ".mpga", ".webm"]
OUTPUT_FORMATS = ["txt", "json", "srt", "vtt"]


def parse_args() -> tuple[str, dict]:
    args = sys.argv[1:]

    if not args:
        print("Error: No file or folder path provided", file=sys.stderr)
        print("\nUsage: python ExtractTranscript.py <file-or-folder> [options]")
        print("\nOptions:")
        print("  --format <format>    Output format (txt, json, srt, vtt) [default: txt]")
        print("  --batch              Process all files in folder")
        print("  --output <dir>       Output directory [default: same as input]")
        print("\nEnvironment:")
        print("  OPENAI_API_KEY       Required - your OpenAI API key")
        sys.exit(1)

    file_path = args[0]
    options = {"format": "txt", "batch": False, "outputDir": None}

    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--format" and i + 1 < len(args):
            fmt = args[i + 1]
            if fmt not in OUTPUT_FORMATS:
                print(f"Error: Invalid format '{fmt}'. Must be one of: {', '.join(OUTPUT_FORMATS)}", file=sys.stderr)
                sys.exit(1)
            options["format"] = fmt
            i += 1
        elif arg == "--batch":
            options["batch"] = True
        elif arg == "--output" and i + 1 < len(args):
            options["outputDir"] = args[i + 1]
            i += 1
        i += 1

    return file_path, options


def is_supported_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_FORMATS


def get_files_from_directory(dir_path: str) -> list[str]:
    files = []
    try:
        for entry in os.listdir(dir_path):
            full_path = os.path.join(dir_path, entry)
            if os.path.isfile(full_path) and is_supported_file(full_path):
                files.append(full_path)
    except OSError as e:
        print(f"Error reading directory: {e}", file=sys.stderr)
        sys.exit(1)
    return files


def get_file_size_mb(file_path: str) -> float:
    return os.path.getsize(file_path) / (1024 * 1024)


def transcribe_file(file_path: str, options: dict, client: "openai.OpenAI") -> str:
    print(f"\nTranscribing: {os.path.basename(file_path)}")

    file_size_mb = get_file_size_mb(file_path)
    print(f"File size: {file_size_mb:.2f} MB")

    if file_size_mb > 25:
        raise RuntimeError(
            f"File size ({file_size_mb:.2f} MB) exceeds OpenAI's 25MB limit. "
            "Please use a local transcription tool or split the file manually."
        )

    print(f"Format: {options['format']}")
    print("Uploading to OpenAI...")

    response_format = "text" if options["format"] == "txt" else options["format"]

    with open(file_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            file=audio_file,
            model="whisper-1",
            response_format=response_format,
            language="en",
        )

    print("Transcription complete")

    return transcription if isinstance(transcription, str) else json.dumps(transcription, indent=2)


def save_transcript(file_path: str, transcript: str, options: dict) -> str:
    output_dir = options.get("outputDir") or os.path.dirname(file_path)
    os.makedirs(output_dir, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(file_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.{options['format']}")
    Path(output_path).write_text(transcript, encoding="utf-8")

    return output_path


def calculate_cost(file_size_mb: float) -> str:
    estimated_cost = file_size_mb * 0.006
    return f"${estimated_cost:.3f}"


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    file_path, options = parse_args()

    client = openai.OpenAI(api_key=api_key)

    if not os.path.exists(file_path):
        print(f"Error: Path does not exist: {file_path}", file=sys.stderr)
        sys.exit(1)

    if os.path.isdir(file_path):
        if not options["batch"]:
            print("Error: Path is a directory. Use --batch flag.", file=sys.stderr)
            sys.exit(1)
        print(f"Processing directory: {file_path}")
        files = get_files_from_directory(file_path)
        if not files:
            print("Error: No supported audio/video files found", file=sys.stderr)
            sys.exit(1)
        print(f"Found {len(files)} file(s) to transcribe")
    elif os.path.isfile(file_path):
        if not is_supported_file(file_path):
            print(f"Error: Unsupported format: {os.path.splitext(file_path)[1]}", file=sys.stderr)
            sys.exit(1)
        files = [file_path]
    else:
        print(f"Error: Path is neither a file nor a directory: {file_path}", file=sys.stderr)
        sys.exit(1)

    total_size_mb = sum(get_file_size_mb(f) for f in files)
    print(f"\nTotal size: {total_size_mb:.2f} MB")
    print(f"Estimated cost: {calculate_cost(total_size_mb)}\n")

    results = []
    errors = []

    for f in files:
        try:
            transcript = transcribe_file(f, options, client)
            output_path = save_transcript(f, transcript, options)
            results.append({"file": f, "output": output_path})
            print(f"Saved to: {output_path}")
        except Exception as e:
            errors.append({"file": os.path.basename(f), "error": str(e)})
            print(f"Failed to transcribe {os.path.basename(f)}: {e}", file=sys.stderr)

    print(f"\n{'='*60}")
    print(f"Transcription complete!")
    print(f"Successfully processed: {len(results)}/{len(files)} files")
    if errors:
        print(f"Failed: {len(errors)} files")
    print(f"{'='*60}")

    if results:
        print("\nOutput files:")
        for r in results:
            print(f"  - {r['output']}")

    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e['file']}: {e['error']}")


if __name__ == "__main__":
    main()
