#!/usr/bin/env python3
"""RenderTemplate - PAI Templating Engine using Jinja2."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
try:
    import jinja2
except ImportError:
    print("Install jinja2: pip install Jinja2", file=sys.stderr); sys.exit(1)
try:
    import yaml
except ImportError:
    yaml = None

def _resolve_path(p: str) -> Path:
    path = Path(p)
    if path.is_absolute(): return path
    return Path(__file__).parent.parent.parent / p

def _load_data(data_path: str) -> dict:
    full = _resolve_path(data_path)
    if not full.exists(): raise FileNotFoundError(f"Data file not found: {full}")
    text = full.read_text(encoding="utf-8")
    if data_path.endswith(".json"): return json.loads(text)
    if yaml: return yaml.safe_load(text)
    raise RuntimeError("PyYAML not installed for YAML files")

def render_template(template_path: str, data_path: str, output_path: str = None, preview: bool = False) -> str:
    full = _resolve_path(template_path)
    if not full.exists(): raise FileNotFoundError(f"Template not found: {full}")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(full.parent)))
    template = env.get_template(full.name)
    data = _load_data(data_path)
    rendered = template.render(**data)
    if preview: print("\n=== PREVIEW ===\n" + rendered + "\n=== END PREVIEW ===\n")
    if output_path:
        out = _resolve_path(output_path)
        out.write_text(rendered, encoding="utf-8")
        print(f"Rendered to: {out}")
    return rendered

def main():
    parser = argparse.ArgumentParser(description="PAI Template Renderer")
    parser.add_argument("-t", "--template", required=True)
    parser.add_argument("-d", "--data", required=True)
    parser.add_argument("-o", "--output")
    parser.add_argument("-p", "--preview", action="store_true")
    args = parser.parse_args()
    try:
        render_template(args.template, args.data, args.output, args.preview)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__": main()
