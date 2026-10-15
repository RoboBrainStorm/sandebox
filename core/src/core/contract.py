from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel


class SandboxConfigurationError(Exception):
    """Raised when the sandbox configuration is invalid."""

    pass


class UnsupportedSandboxCapability(Exception):
    """Raised when a sandbox provider does not support a requested capability."""

    pass


class SandboxCapabilities(BaseModel):
    execution: bool = False
    session: bool = False
    servers: bool = False


class SessionIdentity(BaseModel):
    workspace_id: str
    user_id: str
    session_id: str

    @property
    def stable_key(self) -> str:
        return f"{self.workspace_id}-{self.user_id}-{self.session_id}"


class ExecutionResult(BaseModel):
    exit_code: int
    stdout: str
    stderr: str


class SandboxEvent(BaseModel):
    type: str
    data: dict[str, Any]


class SandboxArtifact(BaseModel):
    path: str
    content: bytes | None = None


class ProcessHandle(BaseModel):
    pid: str
    command: str


class ServerHandle(BaseModel):
    id: str
    url: str
    port: int
    status: str


class RpcChannel(Protocol):
    async def send(self, message: dict[str, Any]) -> None: ...

    async def receive(self) -> dict[str, Any]: ...


class SandboxSession(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def exec(
        self, command: str, env: dict[str, str] | None = None
    ) -> ExecutionResult: ...

    @abstractmethod
    async def exec_stream(
        self, command: str, env: dict[str, str] | None = None
    ) -> AsyncGenerator[SandboxEvent, None]: ...

    @abstractmethod
    async def start_process(
        self, command: str, env: dict[str, str] | None = None
    ) -> ProcessHandle: ...

    @abstractmethod
    async def stop_process(self, handle: ProcessHandle) -> None: ...

    @abstractmethod
    async def open_rpc(self, path: str) -> RpcChannel: ...

    @abstractmethod
    async def snapshot(self) -> SandboxArtifact: ...

    @abstractmethod
    async def open_server(self, port: int) -> ServerHandle: ...

    @abstractmethod
    async def deploy_server(
        self, config: dict[str, Any], env: dict[str, str] | None = None
    ) -> ServerHandle: ...

    @abstractmethod
    async def close_server(self, handle: ServerHandle) -> None: ...

    @abstractmethod
    async def get_server(self, id: str) -> ServerHandle: ...

    @abstractmethod
    async def list_servers(self) -> list[ServerHandle]: ...

    @abstractmethod
    async def server_events(
        self, handle: ServerHandle
    ) -> AsyncGenerator[SandboxEvent, None]: ...

    @abstractmethod
    async def read_file(self, path: str) -> bytes: ...

    @abstractmethod
    async def write_file(self, path: str, content: bytes) -> None: ...

    @abstractmethod
    async def list_files(self, path: str) -> list[str]: ...

    @abstractmethod
    async def delete_file(self, path: str) -> None: ...

    @abstractmethod
    async def stat_file(self, path: str) -> dict[str, Any]: ...


class SandboxProvider(ABC):
    @property
    @abstractmethod
    def capabilities(self) -> SandboxCapabilities: ...

    @abstractmethod
    async def run_python(self, code: str) -> ExecutionResult: ...

    @abstractmethod
    async def run_node(self, code: str) -> ExecutionResult: ...

    @abstractmethod
    async def run_command(self, command: str) -> ExecutionResult: ...

    def get_sandbox_env(self, identity: SessionIdentity) -> dict[str, str]:
        return {
            "SANDBOX_WORKSPACE_ID": identity.workspace_id,
            "SANDBOX_SESSION_ID": identity.session_id,
            "SANDBOX_USER_ID": identity.user_id,
        }

    @abstractmethod
    async def open_session(
        self, identity: SessionIdentity | None = None
    ) -> SandboxSession: ...


class ProcessState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


class ExecResult(ExecutionResult):
    ok: bool = True
    timed_out: bool = False

    def __init__(self, **data):
        if "exit_code" not in data:
            data["exit_code"] = 0 if data.get("ok", True) else 1
        if "stdout" not in data:
            data["stdout"] = ""
        if "stderr" not in data:
            data["stderr"] = ""
        super().__init__(**data)
        self.ok = self.exit_code == 0 and not self.timed_out


__all__ = [
    "ExecResult",
    "ExecutionResult",
    "ProcessHandle",
    "ProcessState",
    "SandboxArtifact",
    "SandboxCapabilities",
    "SandboxConfigurationError",
    "SandboxEvent",
    "SandboxProvider",
    "SandboxSession",
    "ServerHandle",
    "SessionIdentity",
    "UnsupportedSandboxCapability",
]
