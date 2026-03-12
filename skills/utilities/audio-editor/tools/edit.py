#!/usr/bin/env python3
"""Edit - Execute audio edits with ffmpeg."""
import json, subprocess, sys
from pathlib import Path

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    audio_file = args[0] if len(args) > 0 else None
    edits_file = args[1] if len(args) > 1 else None
    output_idx = sys.argv.index("--output") if "--output" in sys.argv else -1
    output_path = sys.argv[output_idx + 1] if output_idx >= 0 else None

    if not audio_file or not edits_file:
        print("Usage: python edit.py <audio-file> <edits.json> [--output <path>]", file=sys.stderr); sys.exit(1)
    audio_path, edits_path = Path(audio_file), Path(edits_file)
    if not audio_path.exists() or not edits_path.exists():
        print(f"File not found", file=sys.stderr); sys.exit(1)

    ext = audio_path.suffix
    out_file = Path(output_path) if output_path else audio_path.with_name(f"{audio_path.stem}_edited{ext}")
    edits = json.loads(edits_path.read_text())
    if not edits:
        print("No edits to apply. Copying original.")
        subprocess.run(["cp", str(audio_path), str(out_file)]); sys.exit(0)

    probe = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", str(audio_path)], capture_output=True, text=True)
    probe_data = json.loads(probe.stdout)
    total_duration = float(probe_data["format"]["duration"])
    bitrate = round(int(probe_data["format"]["bit_rate"]) / 1000)

    edits.sort(key=lambda e: e["start"])
    keep_segments, prev_end = [], 0.0
    for edit in edits:
        if edit["start"] > prev_end: keep_segments.append((prev_end, edit["start"]))
        prev_end = max(prev_end, edit["end"])
    if prev_end < total_duration: keep_segments.append((prev_end, total_duration))

    FADE_S = 0.04
    filter_parts, labels = [], []
    for i, (start, end) in enumerate(keep_segments):
        duration = end - start
        label = f"a{i}"
        f = f"[0:a]atrim={start:.3f}:{end:.3f},asetpts=PTS-STARTPTS"
        if i > 0: f += f",afade=t=in:st=0:d={FADE_S}:curve=qsin"
        if i < len(keep_segments) - 1:
            fade_start = max(0, duration - FADE_S)
            f += f",afade=t=out:st={fade_start:.3f}:d={FADE_S}:curve=qsin"
        f += f"[{label}]"
        filter_parts.append(f)
        labels.append(f"[{label}]")

    filter_parts.append(f"{''.join(labels)}concat=n={len(keep_segments)}:v=0:a=1[out]")
    filter_file = audio_path.parent / f".{audio_path.stem}_filter.txt"
    filter_file.write_text(";\n".join(filter_parts))

    codec = ["-codec:a", "libmp3lame", "-b:a", f"{max(bitrate, 96)}k"] if ext == ".mp3" else ["-codec:a", "pcm_s16le"] if ext == ".wav" else ["-codec:a", "libmp3lame", "-b:a", "128k"]
    subprocess.run(["ffmpeg", "-y", "-i", str(audio_path), "-filter_complex_script", str(filter_file), "-map", "[out]"] + codec + ["-ar", "48000", str(out_file)], capture_output=True)
    filter_file.unlink(missing_ok=True)
    print(f"Edit Complete\nOutput: {out_file}")

if __name__ == "__main__": main()
