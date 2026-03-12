#!/usr/bin/env python3
"""
PAI Pipeline Monitor - Real-time WebSocket Server + UI

Monitors pipeline execution across multiple agents in real-time.

USAGE:
  python PipelineMonitor.py                    # Start server
  python PipelineMonitor.py --port 8765        # Custom port

Then open http://localhost:8765 for the UI

Requires: pip install websockets
"""

import asyncio
import json
import sys
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler
from typing import Any, Optional

try:
    import websockets
    from websockets.server import serve as ws_serve
except ImportError:
    websockets = None  # type: ignore

# Parse port from args
PORT = 8765
for arg in sys.argv[1:]:
    if arg.startswith("--port="):
        PORT = int(arg.split("=")[1])
    elif arg.startswith("--port") and sys.argv.index(arg) + 1 < len(sys.argv):
        PORT = int(sys.argv[sys.argv.index(arg) + 1])


# State
@dataclass
class StepExecution:
    id: str
    action: str
    status: str = "pending"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    output: Any = None
    error: Optional[str] = None


@dataclass
class PipelineExecution:
    id: str
    agent: str
    pipeline: str
    status: str = "pending"
    current_step: Optional[str] = None
    steps: list[dict] = field(default_factory=list)
    start_time: float = 0
    end_time: Optional[float] = None
    result: Any = None
    error: Optional[str] = None


executions: dict[str, dict] = {}
clients: set = set()


def broadcast(event: str, data: Any) -> None:
    """Broadcast to all connected WebSocket clients."""
    import time
    message = json.dumps({"event": event, "data": data, "timestamp": int(time.time() * 1000)})
    disconnected = set()
    for client in clients:
        try:
            asyncio.ensure_future(client.send(message))
        except Exception:
            disconnected.add(client)
    clients.difference_update(disconnected)


# HTML UI (same as TypeScript version)
HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PAI Pipeline Kanban</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
      background: #0f172a; color: #e2e8f0; min-height: 100vh; padding: 20px;
    }
    .header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
              padding-bottom: 16px; border-bottom: 1px solid #334155; }
    .header h1 { font-size: 24px; color: #3b82f6; }
    .status-dot { width: 12px; height: 12px; border-radius: 50%; background: #22c55e;
                  animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    .status-dot.disconnected { background: #ef4444; animation: none; }
    .stats { display: flex; gap: 16px; margin-bottom: 20px; }
    .stat { background: #1e293b; padding: 12px 20px; border-radius: 8px; border: 1px solid #334155; }
    .stat-value { font-size: 28px; font-weight: bold; color: #3b82f6; }
    .stat-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }
    .kanban-container { display: flex; gap: 12px; min-height: calc(100vh - 180px);
                        overflow-x: auto; padding-bottom: 20px; }
    .kanban-column { min-width: 280px; max-width: 320px; flex-shrink: 0; background: #1e293b;
                     border-radius: 12px; border: 1px solid #334155; display: flex; flex-direction: column; }
    .column-header { padding: 16px; border-bottom: 1px solid #334155; }
    .column-title { font-size: 13px; font-weight: 600; color: #94a3b8; text-transform: uppercase;
                    display: flex; align-items: center; gap: 8px; }
    .column-count { background: #334155; color: #e2e8f0; font-size: 11px; padding: 2px 8px;
                    border-radius: 10px; margin-left: auto; }
    .column-cards { flex: 1; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
    .card { background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 12px; }
    .card.running { border-color: #3b82f6; }
    .card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .card-pipeline { font-weight: 600; color: #f1f5f9; font-size: 13px; }
    .card-agent { font-size: 11px; color: #64748b; background: #334155; padding: 2px 8px; border-radius: 4px; }
    .card-progress { margin-top: 10px; display: flex; gap: 4px; }
    .progress-dot { width: 8px; height: 8px; border-radius: 50%; background: #334155; }
    .progress-dot.completed { background: #22c55e; }
    .progress-dot.running { background: #3b82f6; }
    .progress-dot.failed { background: #ef4444; }
    .empty { text-align: center; padding: 40px 20px; color: #64748b; font-size: 13px; }
  </style>
</head>
<body>
  <div class="header">
    <div class="status-dot" id="status-dot"></div>
    <h1>PAI Pipeline Kanban</h1>
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-value" id="total-count">0</div><div class="stat-label">Pipelines</div></div>
    <div class="stat"><div class="stat-value" id="running-count">0</div><div class="stat-label">Running</div></div>
    <div class="stat"><div class="stat-value" id="completed-count">0</div><div class="stat-label">Done</div></div>
    <div class="stat"><div class="stat-value" id="failed-count">0</div><div class="stat-label">Failed</div></div>
  </div>
  <div class="kanban-container" id="kanban">
    <div class="empty" style="width: 100%;">Waiting for pipeline executions...</div>
  </div>
  <script>
    const pipelines = new Map();
    let ws;
    function connect() {
      ws = new WebSocket('ws://' + location.host + '/ws');
      ws.onopen = () => document.getElementById('status-dot').classList.remove('disconnected');
      ws.onclose = () => { document.getElementById('status-dot').classList.add('disconnected'); setTimeout(connect, 2000); };
      ws.onmessage = (event) => { const msg = JSON.parse(event.data); handleEvent(msg.event, msg.data); };
    }
    function handleEvent(event, data) {
      if (event === 'init') { data.executions.forEach(exec => pipelines.set(exec.id, exec)); render(); }
      else if (event.startsWith('pipeline:')) { pipelines.set(data.id, data); render(); }
      else if (event.startsWith('step:')) {
        const exec = pipelines.get(data.executionId);
        if (exec) { const step = exec.steps.find(s => s.id === data.stepId); if (step) Object.assign(step, data); render(); }
      }
    }
    function render() {
      const container = document.getElementById('kanban');
      const arr = Array.from(pipelines.values());
      document.getElementById('total-count').textContent = arr.length;
      document.getElementById('running-count').textContent = arr.filter(p => p.status === 'running').length;
      document.getElementById('completed-count').textContent = arr.filter(p => p.status === 'completed').length;
      document.getElementById('failed-count').textContent = arr.filter(p => p.status === 'failed').length;
      if (arr.length === 0) { container.innerHTML = '<div class="empty">Waiting for pipeline executions...</div>'; return; }
      container.innerHTML = arr.map(exec => `
        <div class="card ${exec.status}">
          <div class="card-header"><span class="card-pipeline">${exec.pipeline}</span><span class="card-agent">${exec.agent}</span></div>
          <div class="card-progress">${exec.steps.map(s => `<div class="progress-dot ${s.status}"></div>`).join('')}</div>
          ${exec.error ? `<div style="color:#fca5a5;font-size:11px;margin-top:8px">${exec.error}</div>` : ''}
        </div>
      `).join('');
    }
    connect();
  </script>
</body>
</html>"""


async def handle_http(path: str, request_headers: Any) -> tuple:
    """Simple HTTP handler for non-WebSocket requests."""
    return (200, [("Content-Type", "text/html")], HTML.encode())


async def handle_websocket(websocket: Any) -> None:
    """Handle WebSocket connections."""
    clients.add(websocket)
    try:
        # Send current state
        init_msg = json.dumps({
            "event": "init",
            "data": {"executions": list(executions.values())},
            "timestamp": int(asyncio.get_event_loop().time() * 1000),
        })
        await websocket.send(init_msg)
        async for message in websocket:
            pass  # Handle incoming messages if needed
    finally:
        clients.discard(websocket)


async def handle_api(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Handle HTTP API requests using a simple async HTTP server."""
    pass


def main() -> None:
    if websockets is None:
        print("Error: websockets package required. Install with: pip install websockets", file=sys.stderr)
        sys.exit(1)

    print(f"""
+===================================================================+
|                     PAI Pipeline Monitor                          |
+===================================================================+
|                                                                   |
|  Server running at:  http://localhost:{PORT}                       |
|  WebSocket:          ws://localhost:{PORT}/ws                      |
|                                                                   |
|  API Endpoints:                                                   |
|    POST /api/start   - Start new pipeline execution               |
|    POST /api/update  - Update pipeline status                     |
|    POST /api/step    - Update step status                         |
|                                                                   |
+===================================================================+
""")

    # For a full implementation, use aiohttp or similar
    # This is a simplified version showing the structure
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

        def do_POST(self) -> None:
            import time
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length else {}

            if self.path == "/api/start":
                exec_id = str(uuid.uuid4())
                execution = {
                    "id": exec_id,
                    "agent": body.get("agent", "unknown"),
                    "pipeline": body.get("pipeline", ""),
                    "status": "pending",
                    "steps": [{"id": s["id"], "action": s["action"], "status": "pending"} for s in body.get("steps", [])],
                    "startTime": int(time.time() * 1000),
                }
                executions[exec_id] = execution
                self._json_response({"id": exec_id})

            elif self.path == "/api/update":
                exec_data = executions.get(body.get("id"))
                if not exec_data:
                    self._json_response({"error": "Not found"}, 404)
                    return
                if body.get("status"):
                    exec_data["status"] = body["status"]
                if body.get("currentStep"):
                    exec_data["currentStep"] = body["currentStep"]
                if body.get("result"):
                    exec_data["result"] = body["result"]
                if body.get("error"):
                    exec_data["error"] = body["error"]
                if body.get("status") in ("completed", "failed"):
                    exec_data["endTime"] = int(time.time() * 1000)
                self._json_response({"ok": True})

            elif self.path == "/api/step":
                exec_data = executions.get(body.get("executionId"))
                if not exec_data:
                    self._json_response({"error": "Not found"}, 404)
                    return
                step = next((s for s in exec_data["steps"] if s["id"] == body.get("stepId")), None)
                if not step:
                    self._json_response({"error": "Step not found"}, 404)
                    return
                if body.get("status"):
                    step["status"] = body["status"]
                if body.get("status") == "running":
                    step["startTime"] = int(time.time() * 1000)
                if body.get("status") in ("completed", "failed"):
                    step["endTime"] = int(time.time() * 1000)
                if body.get("output") is not None:
                    step["output"] = body["output"]
                if body.get("error"):
                    step["error"] = body["error"]
                self._json_response({"ok": True})
            else:
                self._json_response({"error": "Not found"}, 404)

        def _json_response(self, data: dict, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, format: str, *args: Any) -> None:
            pass  # Suppress default logging

    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
