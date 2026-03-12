#!/usr/bin/env python3
"""
Preview a markdown file in the browser
Usage: python PreviewMarkdown.py <path-to-markdown>
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

md_path = sys.argv[1] if len(sys.argv) > 1 else None
if not md_path:
    print("Usage: python PreviewMarkdown.py <path-to-markdown>", file=sys.stderr)
    sys.exit(1)

content = Path(md_path).read_text()
title = Path(md_path).stem

temp_dir = tempfile.mkdtemp(prefix="pai-preview-")
html_path = Path(temp_dir) / "preview.html"

html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <style>
    body {{
      max-width: 800px;
      margin: 40px auto;
      padding: 20px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      line-height: 1.7;
      color: #1a1a1a;
      background: #fafafa;
    }}
    h1 {{ color: #111; font-size: 2.2em; margin-bottom: 0.5em; }}
    h2 {{ color: #333; border-bottom: 1px solid #ddd; padding-bottom: 0.3em; margin-top: 1.5em; }}
    pre {{ background: #2d2d2d; color: #ccc; padding: 16px; overflow-x: auto; border-radius: 6px; }}
    code {{ background: #e8e8e8; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
    pre code {{ padding: 0; background: none; }}
    blockquote {{ border-left: 4px solid #3b82f6; margin: 0; padding-left: 20px; color: #555; }}
    strong {{ color: #000; }}
    hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
  </style>
</head>
<body>
  <div id="content"></div>
  <script>
    document.getElementById('content').innerHTML = marked.parse({json.dumps(content)});
  </script>
</body>
</html>"""

html_path.write_text(html)

# Open in browser (cross-platform)
try:
    subprocess.run(["open", str(html_path)], capture_output=True)
except FileNotFoundError:
    try:
        subprocess.run(["xdg-open", str(html_path)], capture_output=True)
    except FileNotFoundError:
        pass

print(json.dumps({
    "success": True,
    "url": f"file://{html_path}",
    "path": str(html_path),
}, indent=2))
