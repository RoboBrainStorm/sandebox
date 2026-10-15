from __future__ import annotations

import os
from typing import Any

import httpx

from .errors import (
    SandboxAuthError,
    SandboxConnectionError,
    SandboxError,
    SandboxNotFoundError,
)
from .models import (
    AdminStatsResponse,
    BuildResponse,
    DeploymentResponse,
    ExecutionResult,
    SandboxResponse,
)
from .session import AsyncSandboxSessionClient, SandboxSessionClient


class AsyncSandboxClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = (
            base_url or os.environ.get("SANDEBOX_URL", "http://localhost:8000")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get(
            "SANDEBOX_API_KEY", "sk-sandebox-dev-key"
        )
        headers = {"X-API-Key": self.api_key}
        self._client = httpx.AsyncClient(
            base_url=self.base_url, headers=headers, timeout=timeout
        )

    async def __aenter__(self) -> AsyncSandboxClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    def _handle_error(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise SandboxAuthError(f"Authentication failed: {resp.text}")
        if resp.status_code == 404:
            raise SandboxNotFoundError(f"Resource not found: {resp.text}")
        if not resp.is_success:
            raise SandboxError(
                f"API request failed with status {resp.status_code}: {resp.text}"
            )

    async def create_sandbox(
        self,
        workspace_id: str = "default",
        user_id: str = "default",
        session_id: str | None = None,
        image: str | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> AsyncSandboxSessionClient:
        payload = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "session_id": session_id,
            "image": image,
            "cpu_limit": cpu_limit,
            "memory_limit": memory_limit,
        }
        try:
            resp = await self._client.post("/v1/sandboxes", json=payload)
        except httpx.ConnectError as exc:
            raise SandboxConnectionError(
                f"Failed to connect to sandebox server at {self.base_url}"
            ) from exc

        self._handle_error(resp)
        data = resp.json()
        return AsyncSandboxSessionClient(session_id=data["id"], client=self._client)

    async def list_sandboxes(self) -> list[SandboxResponse]:
        resp = await self._client.get("/v1/sandboxes")
        self._handle_error(resp)
        return [SandboxResponse(**s) for s in resp.json()]

    async def get_sandbox(self, session_id: str) -> SandboxResponse:
        resp = await self._client.get(f"/v1/sandboxes/{session_id}")
        self._handle_error(resp)
        return SandboxResponse(**resp.json())

    async def stop_sandbox(self, session_id: str) -> dict[str, Any]:
        resp = await self._client.delete(f"/v1/sandboxes/{session_id}")
        self._handle_error(resp)
        return resp.json()

    async def run_command(self, command: str) -> ExecutionResult:
        resp = await self._client.post(
            "/v1/sandboxes/run", json={"command": command, "language": "bash"}
        )
        self._handle_error(resp)
        return ExecutionResult(**resp.json())

    async def run_python(self, code: str) -> ExecutionResult:
        resp = await self._client.post(
            "/v1/sandboxes/run", json={"code": code, "language": "python"}
        )
        self._handle_error(resp)
        return ExecutionResult(**resp.json())

    async def run_node(self, code: str) -> ExecutionResult:
        resp = await self._client.post(
            "/v1/sandboxes/run", json={"code": code, "language": "node"}
        )
        self._handle_error(resp)
        return ExecutionResult(**resp.json())

    async def build_image(
        self,
        repo_path: str,
        target_name: str,
        is_agent: bool = False,
        prefix: str = "sandebox",
    ) -> BuildResponse:
        resp = await self._client.post(
            "/v1/builds",
            json={
                "repo_path": repo_path,
                "target_name": target_name,
                "is_agent": is_agent,
                "prefix": prefix,
            },
        )
        self._handle_error(resp)
        return BuildResponse(**resp.json())

    async def deploy_service(
        self,
        name: str,
        image: str,
        env: dict[str, str] | None = None,
        command: list[str] | None = None,
        namespace: str | None = None,
        min_scale: int | None = None,
        max_scale: int | None = None,
    ) -> DeploymentResponse:
        resp = await self._client.post(
            "/v1/deployments",
            json={
                "name": name,
                "image": image,
                "env": env,
                "command": command,
                "namespace": namespace,
                "min_scale": min_scale,
                "max_scale": max_scale,
            },
        )
        self._handle_error(resp)
        return DeploymentResponse(**resp.json())

    async def get_deployment(
        self, name: str, namespace: str | None = None
    ) -> DeploymentResponse:
        params = {"namespace": namespace} if namespace else {}
        resp = await self._client.get(f"/v1/deployments/{name}", params=params)
        self._handle_error(resp)
        return DeploymentResponse(**resp.json())

    async def delete_deployment(
        self, name: str, namespace: str | None = None
    ) -> dict[str, Any]:
        params = {"namespace": namespace} if namespace else {}
        resp = await self._client.delete(f"/v1/deployments/{name}", params=params)
        self._handle_error(resp)
        return resp.json()

    async def get_stats(self) -> AdminStatsResponse:
        resp = await self._client.get("/v1/admin/stats")
        self._handle_error(resp)
        return AdminStatsResponse(**resp.json())


class SandboxClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 60.0,
    ):
        self.base_url = (
            base_url or os.environ.get("SANDEBOX_URL", "http://localhost:8000")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get(
            "SANDEBOX_API_KEY", "sk-sandebox-dev-key"
        )
        headers = {"X-API-Key": self.api_key}
        self._client = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=timeout
        )

    def __enter__(self) -> SandboxClient:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _handle_error(self, resp: httpx.Response) -> None:
        if resp.status_code in (401, 403):
            raise SandboxAuthError(f"Authentication failed: {resp.text}")
        if resp.status_code == 404:
            raise SandboxNotFoundError(f"Resource not found: {resp.text}")
        if not resp.is_success:
            raise SandboxError(
                f"API request failed with status {resp.status_code}: {resp.text}"
            )

    def create_sandbox(
        self,
        workspace_id: str = "default",
        user_id: str = "default",
        session_id: str | None = None,
        image: str | None = None,
        cpu_limit: str | None = None,
        memory_limit: str | None = None,
    ) -> SandboxSessionClient:
        payload = {
            "workspace_id": workspace_id,
            "user_id": user_id,
            "session_id": session_id,
            "image": image,
            "cpu_limit": cpu_limit,
            "memory_limit": memory_limit,
        }
        try:
            resp = self._client.post("/v1/sandboxes", json=payload)
        except httpx.ConnectError as exc:
            raise SandboxConnectionError(
                f"Failed to connect to sandebox server at {self.base_url}"
            ) from exc

        self._handle_error(resp)
        data = resp.json()
        return SandboxSessionClient(session_id=data["id"], client=self._client)

    def run_command(self, command: str) -> ExecutionResult:
        resp = self._client.post(
            "/v1/sandboxes/run", json={"command": command, "language": "bash"}
        )
        self._handle_error(resp)
        return ExecutionResult(**resp.json())
