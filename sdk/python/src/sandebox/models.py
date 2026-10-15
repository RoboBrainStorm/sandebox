from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


class SandboxResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    pod_name: str
    status: str


class BuildResponse(BaseModel):
    id: str
    target_name: str
    image_tag: str
    status: str


class DeploymentResponse(BaseModel):
    name: str
    namespace: str
    url: str
    status: str


class AdminStatsResponse(BaseModel):
    active_sandboxes: int
    uptime_seconds: float
    namespace: str
    runtime_class: str
    image: str


class SessionIdentity(BaseModel):
    workspace_id: str
    user_id: str
    session_id: str

    @property
    def stable_key(self) -> str:
        return f"{self.workspace_id}-{self.user_id}-{self.session_id}"


class SandboxEvent(BaseModel):
    type: str
    data: dict[str, Any]


class ProcessHandle(BaseModel):
    pid: str
    command: str


class ServerHandle(BaseModel):
    id: str
    url: str
    port: int
    status: str


class SandboxCapabilities(BaseModel):
    execution: bool = True
    session: bool = True
    servers: bool = True
