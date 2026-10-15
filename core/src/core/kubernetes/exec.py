"""Invoke a deployed agent's on-demand pod over HTTP.

Shared by the execution worker (run_execution) and the tool catalog (so a deployed
agent can be called as a tool from the loop). The pod runs agent_runner.py and
exposes POST /invoke -> {"output_data": {...}}.
"""

from __future__ import annotations

from typing import Any

import httpx

# Generous timeout to absorb Knative scale-from-zero cold starts.
_INVOKE_TIMEOUT = 120.0


async def invoke_agent_pod(
    service_url: str,
    input_data: dict[str, Any],
    execution_id: str | None = None,
) -> dict[str, Any]:
    url = service_url.rstrip("/") + "/invoke"
    payload: dict[str, Any] = {"input_data": input_data}
    if execution_id is not None:
        payload["execution_id"] = execution_id
    async with httpx.AsyncClient(timeout=_INVOKE_TIMEOUT) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("output_data", {})
