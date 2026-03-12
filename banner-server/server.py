#!/usr/bin/env python3
"""PAI Banner Server — visual notification display, port 8889.

POST /notify  { "message": "...", "type": "entry|phase|native|success|warn|info" }
Returns 200 "ok" and prints a coloured banner to this terminal.
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8889

# ── ANSI ────────────────────────────────────────────────────────────────────
R  = "\033[0m"
B  = "\033[1m"
D  = "\033[2m"
CY = "\033[96m"   # bright cyan
BL = "\033[94m"   # bright blue
GR = "\033[92m"   # bright green
YL = "\033[93m"   # bright yellow
MG = "\033[95m"   # bright magenta
WH = "\033[97m"   # bright white

STYLES = {
    "entry":   (CY, "◆"),
    "phase":   (BL, "▶"),
    "native":  (GR, "◈"),
    "success": (GR, "☑"),
    "warn":    (YL, "⚠"),
    "info":    (WH, "·"),
    "learn":   (MG, "✦"),
}

# ── Banner ───────────────────────────────────────────────────────────────────

def print_banner(message: str, kind: str = "info") -> None:
    colour, icon = STYLES.get(kind, STYLES["info"])
    ts    = time.strftime("%H:%M:%S")
    inner = f"  {icon}  {message}"
    width = max(len(inner) + 4, 48)
    pad   = " " * (width - len(inner) - 1)
    bar   = "─" * width
    print(f"\n{colour}{B}┌{bar}┐{R}")
    print(f"{colour}{B}│{inner}{pad}│{R}")
    print(f"{colour}{B}└{bar}┘{R}  {D}{ts}{R}")
    sys.stdout.flush()


# ── Handler ──────────────────────────────────────────────────────────────────

class BannerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length) or b"{}")
            print_banner(body.get("message", ""), body.get("type", "info"))
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        except Exception as exc:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def log_message(self, *_):
        pass  # suppress request noise


# ── Entry ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    srv = HTTPServer(("127.0.0.1", PORT), BannerHandler)
    print_banner(f"PAI Banner Server  ·  port {PORT}", "entry")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{D}Banner server stopped.{R}")
