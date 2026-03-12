#!/usr/bin/env python3
"""Analyze - LLM-powered edit classification."""
import json, os, sys, time
from pathlib import Path
import httpx

def load_env():
    env_path = Path(os.environ.get("PAI_CONFIG_DIR", Path.home() / ".config/PAI")) / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" not in line: continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key not in os.environ: os.environ[key] = value

load_env()

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    input_file = args[0] if args else None
    output_idx = sys.argv.index("--output") if "--output" in sys.argv else -1
    output_path = sys.argv[output_idx + 1] if output_idx >= 0 else None
    aggressive = "--aggressive" in sys.argv

    if not input_file:
        print("Usage: python analyze.py <transcript.json> [--output <path>] [--aggressive]", file=sys.stderr); sys.exit(1)
    if not Path(input_file).exists():
        print(f"File not found: {input_file}", file=sys.stderr); sys.exit(1)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not found.", file=sys.stderr); sys.exit(1)

    out_file = output_path or input_file.replace(".transcript.json", ".edits.json").replace(".json", ".edits.json")
    transcript = json.loads(Path(input_file).read_text())
    chunks = transcript.get("chunks", [])
    if not chunks:
        print("No word chunks found", file=sys.stderr); sys.exit(1)

    # Phase 1: Detect long pauses
    pause_threshold = 3.0 if aggressive else 5.0
    pause_edits = []
    for i in range(1, len(chunks)):
        prev_end = chunks[i-1]["timestamp"][1] or chunks[i-1]["timestamp"][0]
        curr_start = chunks[i]["timestamp"][0]
        gap = curr_start - prev_end
        if gap > pause_threshold:
            cut_start = prev_end + 1.0
            if curr_start - cut_start > 0.5:
                ctx = " ".join(c["text"].strip() for c in chunks[max(0,i-3):i+3])
                pause_edits.append({"type": "CUT_DEAD_AIR", "start": round(cut_start, 2), "end": round(curr_start, 2),
                    "reason": f"{gap:.1f}s pause (keeping 1.0s)", "context": ctx, "confidence": 1.0})
    print(f"Found {len(pause_edits)} long pauses (>{pause_threshold}s)")

    # Phase 2: LLM analysis would go here (placeholder)
    all_edits = pause_edits
    all_edits.sort(key=lambda e: e["start"])

    # Merge overlapping
    merged = []
    for edit in all_edits:
        if merged and edit["start"] < merged[-1]["end"] + 0.3:
            merged[-1]["end"] = max(merged[-1]["end"], edit["end"])
        else:
            merged.append(dict(edit))

    total_cut = sum(e["end"] - e["start"] for e in merged)
    print(f"\nTotal edits: {len(merged)}\nTotal time to cut: {total_cut:.1f}s ({total_cut/60:.1f} min)")
    Path(out_file).write_text(json.dumps(merged, indent=2))
    print(f"Saved: {out_file}")

if __name__ == "__main__": main()
