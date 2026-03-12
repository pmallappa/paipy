#!/usr/bin/env python3
"""Pipeline - End-to-end audio editing pipeline: transcribe -> analyze -> edit -> polish."""
import subprocess, sys, time
from pathlib import Path

TOOLS_DIR = Path(__file__).parent

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    audio_file = args[0] if args else None
    do_polish = "--polish" in sys.argv
    aggressive = "--aggressive" in sys.argv
    preview = "--preview" in sys.argv
    output_idx = sys.argv.index("--output") if "--output" in sys.argv else -1
    output_path = sys.argv[output_idx + 1] if output_idx >= 0 else None

    if not audio_file:
        print("Usage: python pipeline.py <audio-file> [--polish] [--aggressive] [--preview] [--output <path>]", file=sys.stderr); sys.exit(1)
    audio_path = Path(audio_file)
    if not audio_path.exists():
        print(f"File not found: {audio_file}", file=sys.stderr); sys.exit(1)

    ext = audio_path.suffix
    base = audio_path.stem
    d = audio_path.parent
    start_time = time.time()

    print("=" * 42 + "\n       audio-editor Pipeline\n" + "=" * 42)
    print(f"Input: {audio_file}\nMode: {'aggressive' if aggressive else 'standard'}{' + polish' if do_polish else ''}\n")

    # Step 1: Transcribe
    transcript_file = d / f"{base}.transcript.json"
    if transcript_file.exists():
        print(f"Transcript exists, reusing: {transcript_file}")
    else:
        r = subprocess.run([sys.executable, str(TOOLS_DIR / "transcribe.py"), str(audio_path), "--output", str(transcript_file)])
        if r.returncode != 0: print("Transcription failed.", file=sys.stderr); sys.exit(1)

    # Step 2: Analyze
    edits_file = d / f"{base}.edits.json"
    cmd = [sys.executable, str(TOOLS_DIR / "analyze.py"), str(transcript_file), "--output", str(edits_file)]
    if aggressive: cmd.append("--aggressive")
    r = subprocess.run(cmd)
    if r.returncode != 0: print("Analysis failed.", file=sys.stderr); sys.exit(1)

    if preview:
        import json
        edits = json.loads(edits_file.read_text())
        print(f"\nFound {len(edits)} proposed edits. Run without --preview to apply.")
        sys.exit(0)

    # Step 3: Edit
    edited_file = d / f"{base}_edited_pre-polish{ext}" if do_polish else Path(output_path) if output_path else d / f"{base}_edited{ext}"
    r = subprocess.run([sys.executable, str(TOOLS_DIR / "edit.py"), str(audio_path), str(edits_file), "--output", str(edited_file)])
    if r.returncode != 0: print("Editing failed.", file=sys.stderr); sys.exit(1)

    # Step 4: Polish
    if do_polish:
        polished_file = Path(output_path) if output_path else d / f"{base}_edited{ext}"
        r = subprocess.run([sys.executable, str(TOOLS_DIR / "polish.py"), str(edited_file), "--output", str(polished_file)])
        if r.returncode != 0: print(f"Polish failed. Edited file at: {edited_file}", file=sys.stderr); sys.exit(1)
        edited_file.unlink(missing_ok=True)

    final_file = Path(output_path) if output_path else d / f"{base}_edited{ext}" if do_polish else edited_file
    elapsed = time.time() - start_time
    print(f"\nPipeline Complete\nOutput: {final_file}\nElapsed: {elapsed:.1f}s")

if __name__ == "__main__": main()
