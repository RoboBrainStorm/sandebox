from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from .errors import SandboxError, SandboxNotFoundError
from .models import ExecutionResult, SandboxEvent


class AsyncSandboxSessionClient:
    def __init__(self, session_id: str, client: httpx.AsyncClient):
        self.session_id = session_id
        self._client = client

    async def exec(
        self, command: str, env: dict[str, str] | None = None
    ) -> ExecutionResult:
        resp = await self._client.post(
            f"/v1/sandboxes/{self.session_id}/exec",
            json={"command": command, "env": env},
        )
        if resp.status_code == 404:
            raise SandboxNotFoundError(f"Sandbox {self.session_id} not found")
        if not resp.is_success:
            raise SandboxError(f"Exec failed with status {resp.status_code}: {resp.text}")

        data = resp.json()
        return ExecutionResult(**data)

    async def exec_stream(
        self, command: str, env: dict[str, str] | None = None
    ) -> AsyncGenerator[SandboxEvent, None]:
        async with self._client.stream(
            "POST",
            f"/v1/sandboxes/{self.session_id}/exec-stream",
            json={"command": command, "env": env},
            headers={"Accept": "text/event-stream"},
        ) as response:
            if response.status_code == 404:
                raise SandboxNotFoundError(f"Sandbox {self.session_id} not found")
            if not response.is_success:
                raise SandboxError(f"Exec stream failed with status {response.status_code}")

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    payload = line[len("data: "):].strip()
                    if payload:
                        try:
                            parsed = json.loads(payload)
                            yield SandboxEvent(type=parsed.get("type", "stdout"), data=parsed.get("data", {}))
                        except Exception:
                            continue

    async def stop(self) -> None:
        resp = await self._client.delete(f"/v1/sandboxes/{self.session_id}")
        if resp.status_code != 404 and not resp.is_success:
            raise SandboxError(f"Stop failed with status {resp.status_code}: {resp.text}")


class SandboxSessionClient:
    def __init__(self, session_id: str, client: httpx.Client):
        self.session_id = session_id
        self._client = client

    def exec(
        self, command: str, env: dict[str, str] | None = None
    ) -> ExecutionResult:
        resp = self._client.post(
            f"/v1/sandboxes/{self.session_id}/exec",
            json={"command": command, "env": env},
        )
        if resp.status_code == 404:
            raise SandboxNotFoundError(f"Sandbox {self.session_id} not found")
        if not resp.is_success:
            raise SandboxError(f"Exec failed with status {resp.status_code}: {resp.text}")

        data = resp.json()
        return ExecutionResult(**data)

    def stop(self) -> None:
        resp = self._client.delete(f"/v1/sandboxes/{self.session_id}")
        if resp.status_code != 404 and not resp.is_success:
            raise SandboxError(f"Stop failed with status {resp.status_code}: {resp.text}")
