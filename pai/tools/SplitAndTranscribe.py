#!/usr/bin/env python3
"""
split-and-transcribe.py

Helper to split large audio files and transcribe them using OpenAI Whisper API.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


def split_audio_file(file_path: str, chunk_size_mb: int = 20) -> tuple[list[dict], str]:
    """Split audio file into chunks using FFmpeg."""
    temp_dir = tempfile.mkdtemp(prefix="transcript-")
    ext = Path(file_path).suffix
    chunk_pattern = str(Path(temp_dir) / f"chunk_%03d{ext}")
    chunk_minutes = chunk_size_mb  # ~1MB per minute estimate

    print(f"Splitting file into ~{chunk_size_mb}MB chunks...")

    result = subprocess.run(
        [
            "ffmpeg", "-i", file_path,
            "-f", "segment",
            "-segment_time", str(chunk_minutes * 60),
            "-c", "copy",
            chunk_pattern,
        ],
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg exited with code {result.returncode}")

    chunk_files = sorted(
        f for f in Path(temp_dir).iterdir()
        if f.name.startswith("chunk_")
    )

    chunks = [{"path": str(f), "index": i + 1} for i, f in enumerate(chunk_files)]
    print(f"Split into {len(chunks)} chunks")

    return chunks, temp_dir


def transcribe_chunk(chunk: dict, client: "OpenAI", fmt: str) -> str:
    """Transcribe a single chunk."""
    with open(chunk["path"], "rb") as f:
        transcription = client.audio.transcriptions.create(
            file=f,
            model="whisper-1",
            response_format="text" if fmt == "txt" else fmt,
            language="en",
        )

    if isinstance(transcription, str):
        return transcription
    return str(transcription)


def split_and_transcribe(file_path: str, api_key: str, fmt: str = "txt") -> str:
    """Main function for split and transcribe."""
    if OpenAI is None:
        raise RuntimeError("openai package required: pip install openai")

    client = OpenAI(api_key=api_key)
    file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)

    print(f"File size: {file_size_mb:.2f} MB (exceeds 25MB limit)")
    print("Splitting file for transcription...")

    chunks, temp_dir = split_audio_file(file_path, 20)

    try:
        transcripts: list[str] = []

        for i, chunk in enumerate(chunks):
            chunk_size = Path(chunk["path"]).stat().st_size / (1024 * 1024)
            print(f"\nTranscribing chunk {chunk['index']}/{len(chunks)} ({chunk_size:.2f} MB)...")

            transcript = transcribe_chunk(chunk, client, fmt)
            transcripts.append(transcript)
            print(f"Chunk {chunk['index']} complete")

        print("\nAll chunks transcribed")

        if fmt == "txt":
            merged = "\n\n".join(transcripts)
        elif fmt == "json":
            merged = "\n".join(transcripts)
        else:
            merged = "\n\n".join(transcripts)

        return merged
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("Cleaned up temporary files")


def main() -> None:
    file_path = sys.argv[1] if len(sys.argv) > 1 else None
    fmt = sys.argv[2] if len(sys.argv) > 2 else "txt"

    if not file_path:
        print("Usage: python SplitAndTranscribe.py <file> [format]", file=sys.stderr)
        sys.exit(1)

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    try:
        transcript = split_and_transcribe(file_path, api_key, fmt)
        print("\nFinal transcript:\n")
        print(transcript)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
