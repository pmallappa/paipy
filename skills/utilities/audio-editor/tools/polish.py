#!/usr/bin/env python3
"""Polish - Cleanvoice API cloud polish."""
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
API_BASE = "https://api.cleanvoice.ai/v2"

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    audio_file = args[0] if args else None
    output_idx = sys.argv.index("--output") if "--output" in sys.argv else -1
    output_path = sys.argv[output_idx + 1] if output_idx >= 0 else None

    if not audio_file:
        print("Usage: python polish.py <audio-file> [--output <path>]", file=sys.stderr); sys.exit(1)
    audio_path = Path(audio_file)
    if not audio_path.exists():
        print(f"File not found: {audio_file}", file=sys.stderr); sys.exit(1)

    api_key = os.environ.get("CLEANVOICE_API_KEY")
    if not api_key:
        print("CLEANVOICE_API_KEY not found.", file=sys.stderr); sys.exit(1)

    out_file = Path(output_path) if output_path else audio_path.with_name(f"{audio_path.stem}_polished{audio_path.suffix}")
    print(f"Audio: {audio_file}\nOutput: {out_file}")

    with httpx.Client(timeout=300) as client:
        # Upload
        print("\nUploading to Cleanvoice...")
        with open(audio_path, "rb") as f:
            resp = client.post(f"{API_BASE}/upload", headers={"X-API-Key": api_key}, files={"file": (audio_path.name, f)})
        resp.raise_for_status()
        file_id = resp.json().get("id") or resp.json().get("file_id")
        print(f"Uploaded: {file_id}")

        # Process
        print("Starting Cleanvoice processing...")
        resp = client.post(f"{API_BASE}/edit", headers={"Content-Type": "application/json", "X-API-Key": api_key},
            json={"input": {"files": [file_id]}, "config": {"filler_words": True, "mouth_sounds": True, "deadair": False, "normalize": True}})
        resp.raise_for_status()
        edit_id = resp.json().get("id") or resp.json().get("edit_id")

        # Poll
        print("Processing...")
        for i in range(360):
            time.sleep(5)
            resp = client.get(f"{API_BASE}/edit/{edit_id}", headers={"X-API-Key": api_key})
            if not resp.is_success: continue
            status_data = resp.json()
            status = status_data.get("status")
            if status in ("completed", "done"):
                download_url = status_data.get("result", {}).get("url") or status_data.get("download_url")
                if not download_url: print("No download URL", file=sys.stderr); sys.exit(1)
                dl_resp = client.get(download_url)
                dl_resp.raise_for_status()
                out_file.write_bytes(dl_resp.content)
                print(f"\nPolish Complete\nOutput: {out_file} ({len(dl_resp.content)//1024//1024}MB)")
                sys.exit(0)
            elif status in ("failed", "error"):
                print(f"Processing failed: {status_data.get('error')}", file=sys.stderr); sys.exit(1)
            print(f"\r  Status: {status} ({(i+1)*5}s elapsed)", end="", flush=True)
        print("\nTimeout: >30 min", file=sys.stderr); sys.exit(1)

if __name__ == "__main__": main()
