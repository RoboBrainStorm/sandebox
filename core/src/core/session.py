from __future__ import annotations

import shlex
from collections.abc import AsyncGenerator
from typing import Any

from .config import SandboxConfig
from .contract import (
    ExecutionResult,
    ProcessHandle,
    RpcChannel,
    SandboxArtifact,
    SandboxEvent,
    SandboxSession,
    ServerHandle,
    SessionIdentity,
    UnsupportedSandboxCapability,
)
from .kubernetes.client import get_k8s_client
from .kubernetes.knative import (
    delete_knative_service,
    deploy_knative_service,
    get_knative_service,
)
from .kubernetes.namespaces import ensure_namespace
from .kubernetes.pods import (
    create_sandbox_pod,
    delete_file_in_pod,
    delete_pod,
    exec_in_pod,
    exec_in_pod_stream,
    list_files_in_pod,
    read_file_in_pod,
    stat_file_in_pod,
    wait_for_pod_ready,
    write_file_in_pod,
)
from .utils import get_pod_name, get_service_name


class KnativeSandboxSession(SandboxSession):
    def __init__(self, identity: SessionIdentity, config: SandboxConfig | None = None):
        self.identity = identity
        self.config = config or SandboxConfig.from_env()
        self.namespace = self.config.namespace
        self.pod_name = get_pod_name(identity)
        self.image = self.config.image
        self.cpus = self.config.cpu_limit
        self.memory = self.config.memory_limit
        self._tracked_processes: set[str] = set()

    async def start(self) -> None:
        api_client = await get_k8s_client()
        await ensure_namespace(api_client, self.namespace)

        try:
            await create_sandbox_pod(
                namespace=self.namespace,
                pod_name=self.pod_name,
                image=self.image,
                cpus=self.cpus,
                memory=self.memory,
            )
        except Exception as e:
            if "AlreadyExists" not in str(e):
                raise

        await wait_for_pod_ready(self.namespace, self.pod_name, timeout=60)

    async def stop(self) -> None:
        await delete_pod(self.namespace, self.pod_name)

    async def exec(
        self, command: str, env: dict[str, str] | None = None
    ) -> ExecutionResult:
        args = shlex.split(command)
        if env:
            env_args = ["env"] + [f"{k}={v}" for k, v in env.items()] + args
            args = env_args

        stdout, stderr, rc = await exec_in_pod(self.namespace, self.pod_name, args)
        return ExecutionResult(exit_code=rc, stdout=stdout, stderr=stderr)

    async def exec_stream(
        self, command: str, env: dict[str, str] | None = None
    ) -> AsyncGenerator[SandboxEvent, None]:
        args = shlex.split(command)
        if env:
            env_args = ["env"] + [f"{k}={v}" for k, v in env.items()] + args
            args = env_args

        async for chunk in exec_in_pod_stream(self.namespace, self.pod_name, args):
            if chunk["type"] == "stdout":
                yield SandboxEvent(type="stdout", data={"chunk": chunk["text"]})
            elif chunk["type"] == "stderr":
                yield SandboxEvent(type="stderr", data={"chunk": chunk["text"]})

    async def start_process(
        self, command: str, env: dict[str, str] | None = None
    ) -> ProcessHandle:
        args = shlex.split(command)
        if env:
            env_args = ["env"] + [f"{k}={v}" for k, v in env.items()] + args
            args = env_args

        escaped_cmd = shlex.join(args)
        bg_cmd = ["sh", "-c", f"nohup {escaped_cmd} > /dev/null 2>&1 & echo $!"]
        stdout, stderr, rc = await exec_in_pod(self.namespace, self.pod_name, bg_cmd)

        pid = stdout.strip()
        self._tracked_processes.add(pid)
        return ProcessHandle(pid=pid, command=command)

    async def stop_process(self, handle: ProcessHandle) -> None:
        await exec_in_pod(self.namespace, self.pod_name, ["kill", "-9", handle.pid])
        self._tracked_processes.discard(handle.pid)

    async def open_rpc(self, path: str) -> RpcChannel:
        raise UnsupportedSandboxCapability(
            "open_rpc is not supported on Knative over exec websockets."
        )

    async def snapshot(self) -> SandboxArtifact:
        raise UnsupportedSandboxCapability(
            "snapshot filtering and export not implemented yet."
        )

    async def open_server(self, port: int) -> ServerHandle:
        raise UnsupportedSandboxCapability(
            "open_server not supported natively; use deploy_server to spawn a Knative service."
        )

    async def deploy_server(self, config: dict[str, Any]) -> ServerHandle:
        port = config.get("port", 8080)
        command = config.get("command", "sleep infinity")
        service_name = get_service_name(self.identity, port)

        cmd = shlex.split(command)

        url = await deploy_knative_service(
            namespace=self.namespace,
            name=service_name,
            image=self.image,
            env=config.get("env"),
            command=cmd,
            min_scale=self.config.min_scale,
            max_scale=self.config.max_scale,
        )
        return ServerHandle(id=service_name, url=url, port=port, status="ready")

    async def close_server(self, handle: ServerHandle) -> None:
        api_client = await get_k8s_client()
        await delete_knative_service(api_client, self.namespace, handle.id)

    async def get_server(self, id: str) -> ServerHandle:
        api_client = await get_k8s_client()
        res = await get_knative_service(api_client, self.namespace, id)
        if not res:
            raise ValueError(f"Server {id} not found")
        url = (res.get("status") or {}).get(
            "url"
        ) or f"http://{id}.{self.namespace}.svc.cluster.local"
        return ServerHandle(id=id, url=url, port=80, status="ready")

    async def list_servers(self) -> list[ServerHandle]:
        raise UnsupportedSandboxCapability("list_servers not implemented for Knative")

    async def server_events(
        self, handle: ServerHandle
    ) -> AsyncGenerator[SandboxEvent, None]:
        yield SandboxEvent(
            type="status",
            data={"id": handle.id, "status": handle.status, "url": handle.url},
        )

    async def read_file(self, path: str) -> bytes:
        return await read_file_in_pod(self.namespace, self.pod_name, path)

    async def write_file(self, path: str, content: bytes) -> None:
        await write_file_in_pod(self.namespace, self.pod_name, path, content)

    async def list_files(self, path: str) -> list[str]:
        return await list_files_in_pod(self.namespace, self.pod_name, path)

    async def delete_file(self, path: str) -> None:
        await delete_file_in_pod(self.namespace, self.pod_name, path)

    async def stat_file(self, path: str) -> dict[str, Any]:
        return await stat_file_in_pod(self.namespace, self.pod_name, path)
