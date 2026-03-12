"""
PAI Installer v4.0 -- Web Server
FastAPI HTTP + WebSocket server for the thick-client web installer.
Serves static files and handles WebSocket communication.
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse, Response
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print(
        "FastAPI and uvicorn are required for the web server.\n"
        "Install them with: pip install fastapi uvicorn websockets",
        file=sys.stderr,
    )
    sys.exit(1)

from web.routes import add_client, handle_ws_message, remove_client

PORT = int(os.environ.get("PAI_INSTALL_PORT", "1337"))
PUBLIC_DIR = Path(__file__).parent.parent / "public"

# -- MIME Types ---------------------------------------------------------------

MIME_TYPES = {
    ".html": "text/html",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".woff2": "font/woff2",
    ".ttf": "font/ttf",
    ".ico": "image/x-icon",
}

# -- Inactivity Timeout -------------------------------------------------------

INACTIVITY_SECONDS = 30 * 60  # 30 minutes
_inactivity_task: Optional[asyncio.Task] = None


async def _inactivity_shutdown() -> None:
    """Shut down the server after inactivity timeout."""
    await asyncio.sleep(INACTIVITY_SECONDS)
    print("\n[PAI Installer] Shutting down due to inactivity.")
    os._exit(0)


def _reset_inactivity() -> None:
    """Reset the inactivity timer."""
    global _inactivity_task
    if _inactivity_task and not _inactivity_task.done():
        _inactivity_task.cancel()
    try:
        loop = asyncio.get_event_loop()
        _inactivity_task = loop.create_task(_inactivity_shutdown())
    except RuntimeError:
        pass


# -- FastAPI App ---------------------------------------------------------------

app = FastAPI(title="PAI Installer", version="4.0")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for installer communication."""
    await websocket.accept()
    add_client(websocket)
    _reset_inactivity()

    try:
        await websocket.send_json({"type": "connected", "port": PORT})

        while True:
            data = await websocket.receive_text()
            _reset_inactivity()
            handle_ws_message(websocket, data)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        remove_client(websocket)


@app.get("/{path:path}")
async def serve_static(path: str) -> Response:
    """Serve static files from the public directory."""
    _reset_inactivity()

    if not path or path == "/":
        path = "index.html"

    full_path = PUBLIC_DIR / path

    # Security: prevent directory traversal
    try:
        full_path = full_path.resolve()
        if not str(full_path).startswith(str(PUBLIC_DIR.resolve())):
            return Response("Forbidden", status_code=403)
    except Exception:
        return Response("Forbidden", status_code=403)

    if full_path.exists() and full_path.is_file():
        ext = full_path.suffix
        mime = MIME_TYPES.get(ext, "application/octet-stream")
        content = full_path.read_bytes()
        return Response(
            content=content,
            media_type=mime,
            headers={"cache-control": "no-cache, no-store, must-revalidate"},
        )

    # Fallback to index.html for SPA routing
    index_path = PUBLIC_DIR / "index.html"
    if index_path.exists():
        return Response(
            content=index_path.read_bytes(),
            media_type="text/html",
            headers={"cache-control": "no-cache"},
        )

    return Response("Not Found", status_code=404)


def start_server() -> None:
    """Start the web server."""
    print(f"PAI Installer server running on http://127.0.0.1:{PORT}/")
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=PORT,
        log_level="warning",
    )


if __name__ == "__main__":
    start_server()
