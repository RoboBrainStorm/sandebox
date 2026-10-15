"""
Standard runner injected into every model image at build time.

The model container starts by running this script. It reads the run payload
from env, imports the user's Engine class, executes it, and POSTs the result
back to the API callback URL before exiting.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import time
from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class EngineProtocol(Protocol):
    def run(self, input_data: dict) -> dict: ...


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rb_runner")


def _callback(url: str, payload: dict) -> None:
    for attempt in range(3):
        try:
            r = httpx.post(url, json=payload, timeout=30)
            r.raise_for_status()
            return
        except Exception as exc:
            log.warning("callback attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2**attempt)
    log.error("all callback attempts failed — result lost")


def main() -> None:
    run_id = os.environ["RUN_ID"]
    callback_url = os.environ["CALLBACK_URL"]
    input_data = json.loads(base64.b64decode(os.environ["INPUT_JSON_B64"]))

    log.info("run_id=%s starting", run_id)

    try:
        from engine import Engine  # noqa: PLC0415 — model-provided module

        if not issubclass(Engine, EngineProtocol):
            raise TypeError(
                "engine.Engine must implement run(self, input_data: dict) -> dict"
            )

        engine = Engine()
        result = engine.run(input_data)
        _callback(callback_url, {"status": "completed", "outputs": result})
        log.info("run_id=%s completed", run_id)
    except Exception as exc:
        log.error("run_id=%s failed: %s", run_id, exc)
        _callback(callback_url, {"status": "failed", "error": str(exc)})
        sys.exit(1)


if __name__ == "__main__":
    main()
