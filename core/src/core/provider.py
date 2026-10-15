from __future__ import annotations

import asyncio
import uuid

from .config import SandboxConfig
from .contract import (
    ExecutionResult,
    SandboxCapabilities,
    SandboxProvider,
    SandboxSession,
    SessionIdentity,
)
from .kubernetes.client import get_k8s_client
from .kubernetes.namespaces import ensure_namespace
from .kubernetes.pods import (
    create_sandbox_pod,
    delete_pod,
    exec_in_pod,
    wait_for_pod_ready,
)
from .session import KnativeSandboxSession


class KnativeProvider(SandboxProvider):
    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig.from_env()

    @property
    def capabilities(self) -> SandboxCapabilities:
        return SandboxCapabilities(execution=True, session=True, servers=True)

    async def _run_in_ephemeral_pod(self, command: list[str]) -> ExecutionResult:
        api_client = await get_k8s_client()
        namespace = self.config.namespace
        await ensure_namespace(api_client, namespace)

        pod_name = f"rb-exec-{uuid.uuid4().hex[:8]}"
        image = self.config.image
        cpus = self.config.cpu_limit
        memory = self.config.memory_limit
        timeout = self.config.execution_timeout

        await create_sandbox_pod(
            namespace=namespace,
            pod_name=pod_name,
            image=image,
            cpus=cpus,
            memory=memory,
        )

        try:
            await wait_for_pod_ready(namespace, pod_name, timeout=30)

            stdout, stderr, rc = await asyncio.wait_for(
                exec_in_pod(namespace, pod_name, command), timeout=timeout
            )
            return ExecutionResult(exit_code=rc, stdout=stdout, stderr=stderr)
        except TimeoutError:
            return ExecutionResult(
                exit_code=124,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
            )
        finally:
            await delete_pod(namespace, pod_name)

    async def run_python(self, code: str) -> ExecutionResult:
        import base64

        b64_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        command = ["sh", "-c", f"echo {b64_code} | base64 -d | python3"]
        return await self._run_in_ephemeral_pod(command)

    async def run_node(self, code: str) -> ExecutionResult:
        import base64

        b64_code = base64.b64encode(code.encode("utf-8")).decode("utf-8")
        command = ["sh", "-c", f"echo {b64_code} | base64 -d | node"]
        return await self._run_in_ephemeral_pod(command)

    async def run_command(self, command: str) -> ExecutionResult:
        import shlex

        args = shlex.split(command)
        return await self._run_in_ephemeral_pod(args)

    async def open_session(
        self, identity: SessionIdentity | None = None
    ) -> SandboxSession:
        if not identity:
            identity = SessionIdentity(
                workspace_id=uuid.uuid4().hex,
                user_id="system",
                session_id=uuid.uuid4().hex,
            )
        session = KnativeSandboxSession(identity, config=self.config)
        await session.start()
        return session
