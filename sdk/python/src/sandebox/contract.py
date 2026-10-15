from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel

from .errors import SandboxError


class SandboxConfigurationError(SandboxError):
    """Raised when the sandbox configuration is invalid."""

    pass


class UnsupportedSandboxCapability(SandboxError):
    """Raised when a sandbox provider does not support a requested capability."""

    pass


class SandboxArtifact(BaseModel):
    path: str
    content: bytes | None = None


class ProcessState(StrEnum):
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"
    STOPPED = "stopped"


class ExecResult(BaseModel):
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    ok: bool = True
    timed_out: bool = False

    def __init__(self, **data):
        if "exit_code" not in data:
            data["exit_code"] = 0 if data.get("ok", True) else 1
        super().__init__(**data)
        self.ok = self.exit_code == 0 and not self.timed_out


class RpcChannel(Protocol):
    async def send(self, message: dict[str, Any]) -> None: ...

    async def receive(self) -> dict[str, Any]: ...


class SandboxSession(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def exec(self, command: str, env: dict[str, str] | None = None) -> Any: ...

    @abstractmethod
    async def exec_stream(
        self, command: str, env: dict[str, str] | None = None
    ) -> AsyncGenerator[Any, None]: ...

    @abstractmethod
    async def start_process(
        self, command: str, env: dict[str, str] | None = None
    ) -> Any: ...

    @abstractmethod
    async def stop_process(self, handle: Any) -> None: ...

    @abstractmethod
    async def open_rpc(self, path: str) -> RpcChannel: ...

    @abstractmethod
    async def snapshot(self) -> SandboxArtifact: ...

    @abstractmethod
    async def open_server(self, port: int) -> Any: ...

    @abstractmethod
    async def deploy_server(
        self, config: dict[str, Any], env: dict[str, str] | None = None
    ) -> Any: ...

    @abstractmethod
    async def close_server(self, handle: Any) -> None: ...

    @abstractmethod
    async def get_server(self, id: str) -> Any: ...

    @abstractmethod
    async def list_servers(self) -> list[Any]: ...

    @abstractmethod
    async def server_events(self, handle: Any) -> AsyncGenerator[Any, None]: ...

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
    def capabilities(self) -> Any: ...

    @abstractmethod
    async def run_python(self, code: str) -> Any: ...

    @abstractmethod
    async def run_node(self, code: str) -> Any: ...

    @abstractmethod
    async def run_command(self, command: str) -> Any: ...

    @abstractmethod
    async def open_session(self, identity: Any | None = None) -> SandboxSession: ...
