#!/usr/bin/env python3
"""Transcribe - Word-level transcription via Whisper."""
import json, subprocess, sys
from pathlib import Path

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    input_file = args[0] if args else None
    output_idx = sys.argv.index("--output") if "--output" in sys.argv else -1
    output_path = sys.argv[output_idx + 1] if output_idx >= 0 else None

    if not input_file:
        print("Usage: python transcribe.py <audio-file> [--output <path>]", file=sys.stderr); sys.exit(1)
    input_path = Path(input_file)
    if not input_path.exists():
        print(f"File not found: {input_file}", file=sys.stderr); sys.exit(1)

    out_file = Path(output_path) if output_path else input_path.with_suffix(".transcript.json")
    print(f"Transcribing: {input_file}\nOutput: {out_file}")

    has_fast = subprocess.run(["which", "insanely-fast-whisper"], capture_output=True).returncode == 0
    has_whisper = subprocess.run(["which", "whisper"], capture_output=True).returncode == 0

    if has_fast:
        print("Using insanely-fast-whisper (MPS accelerated)...")
        result = subprocess.run(["insanely-fast-whisper", "--file-name", str(input_path), "--transcript-path", str(out_file),
            "--device-id", "mps", "--timestamp", "word", "--model-name", "openai/whisper-large-v3", "--batch-size", "4"],
            capture_output=True, text=True)
        if result.returncode == 0: print("Transcription complete.")
        else: print("insanely-fast-whisper failed, trying standard whisper...", file=sys.stderr)

    if not has_fast or not out_file.exists():
        if not has_whisper:
            print("No whisper variant found. Install: pip install openai-whisper", file=sys.stderr); sys.exit(1)
        print("Using standard whisper...")
        tmp_dir = out_file.parent / ".whisper-tmp"
        tmp_dir.mkdir(exist_ok=True)
        subprocess.run(["whisper", str(input_path), "--model", "medium", "--language", "en",
            "--word_timestamps", "True", "--output_format", "json", "--output_dir", str(tmp_dir)], capture_output=True)
        whisper_out = tmp_dir / input_path.with_suffix(".json").name
        if whisper_out.exists():
            data = json.loads(whisper_out.read_text())
            chunks = [{"text": w["word"], "timestamp": [w["start"], w["end"]]}
                for seg in data.get("segments", []) for w in seg.get("words", [])]
            full_text = "".join(c["text"] for c in chunks)
            out_file.write_text(json.dumps({"text": full_text, "chunks": chunks}, indent=2))
            subprocess.run(["rm", "-rf", str(tmp_dir)])
            print("Transcription complete.")
        else:
            print("Whisper produced no output.", file=sys.stderr)
            subprocess.run(["rm", "-rf", str(tmp_dir)]); sys.exit(1)

    transcript = json.loads(out_file.read_text())
    print(f"Words: {len(transcript.get('chunks', []))} | Text: {len(transcript.get('text', ''))} chars\nSaved: {out_file}")

if __name__ == "__main__": main()
