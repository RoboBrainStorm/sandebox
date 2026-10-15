"""
Standard HTTP runner injected into every custom-agent image at build time.

Unlike the model runner (rb_runner.py, a one-shot script), an agent pod is a
Knative service: a long-lived HTTP server that scales to zero and wakes on
request. This server imports the user's agent entrypoint and serves /invoke.

Agent repo contract (parallel to the model's engine.Engine.run):
    agent.py must expose either
        def run(input_data: dict) -> dict
    or
        class Agent:  def run(self, input_data: dict) -> dict

Endpoints:
    GET  /        -> 200 (Knative readiness/liveness probe)
    POST /invoke  -> {"execution_id": str, "input_data": {...}}
                     returns {"output_data": {...}} or {"error": str} (500)

Uses only the Python stdlib so it works in any agent image without forcing
extra dependencies. Listens on $PORT (Knative sets PORT=8080).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agent_runner")


def _load_entrypoint() -> Callable[[dict], dict]:
    """Resolve the agent's run() callable from the user-provided agent.py."""
    import agent as user_agent  # noqa: PLC0415 — agent-provided module

    if hasattr(user_agent, "run") and callable(user_agent.run):
        return user_agent.run
    if hasattr(user_agent, "Agent"):
        instance = user_agent.Agent()
        return instance.run
    raise TypeError(
        "agent.py must expose run(input_data: dict) -> dict "
        "or class Agent with a run(self, input_data: dict) -> dict method"
    )


# Set once at container start (in main) so this module stays import-safe for tests.
_run: Callable[[dict], dict] | None = None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        self._send(200, {"status": "ok"})

    def do_POST(self) -> None:  # noqa: N802 — BaseHTTPRequestHandler API
        if self.path.rstrip("/") != "/invoke":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            execution_id = body.get("execution_id")
            input_data = body.get("input_data", {})
            log.info("invoke execution_id=%s", execution_id)
            if _run is None:
                raise RuntimeError("agent entrypoint not initialized")
            output = _run(input_data)
            self._send(200, {"output_data": output})
        except Exception as exc:  # noqa: BLE001 — report any agent error to caller
            log.exception("invoke failed")
            self._send(500, {"error": str(exc)})

    def log_message(self, *args: Any) -> None:  # silence default access logging
        return


def main() -> None:
    global _run
    # Resolve the entrypoint at startup so a broken contract fails the pod fast.
    _run = _load_entrypoint()
    port = int(os.environ.get("PORT", "8080"))
    log.info("agent_runner listening on :%d", port)
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
