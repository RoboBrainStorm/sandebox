from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import structlog
from kubernetes_asyncio import client

from .client import get_k8s_client

logger = structlog.get_logger(__name__)


async def create_sandbox_pod(
    namespace: str,
    pod_name: str,
    image: str = "python:3.12-slim",
    cpus: str = "1",
    memory: str = "512Mi",
    env: dict[str, str] | None = None,
) -> None:
    api_client = await get_k8s_client()
    core_v1 = client.CoreV1Api(api_client)

    pod_manifest = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": pod_name,
            "labels": {"app": "codegen-sandbox"},
        },
        "spec": {
            "runtimeClassName": "gvisor",
            "containers": [
                {
                    "name": "sandbox",
                    "image": image,
                    "command": ["sleep", "infinity"],
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": cpus, "memory": memory},
                    },
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "runAsUser": 65534,
                        "runAsGroup": 65534,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [{"name": "tmpfs", "mountPath": "/work"}],
                    "workingDir": "/work",
                    "env": [{"name": "PYTHONDONTWRITEBYTECODE", "value": "1"}]
                    + [{"name": k, "value": v} for k, v in (env or {}).items()],
                }
            ],
            "volumes": [
                {
                    "name": "tmpfs",
                    "emptyDir": {"medium": "Memory", "sizeLimit": "128Mi"},
                }
            ],
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
        },
    }

    try:
        await core_v1.create_namespaced_pod(namespace=namespace, body=pod_manifest)
        logger.info("sandbox_pod_created", pod_name=pod_name, namespace=namespace)
    except client.ApiException as e:
        logger.error("sandbox_pod_create_failed", error=str(e))
        raise


async def delete_pod(namespace: str, pod_name: str) -> None:
    api_client = await get_k8s_client()
    core_v1 = client.CoreV1Api(api_client)
    try:
        await core_v1.delete_namespaced_pod(name=pod_name, namespace=namespace)
        logger.info("sandbox_pod_deleted", pod_name=pod_name, namespace=namespace)
    except client.ApiException as e:
        if e.status != 404:
            logger.error("sandbox_pod_delete_failed", error=str(e))
            raise


async def exec_in_pod(
    namespace: str, pod_name: str, command: list[str]
) -> tuple[str, str, int]:
    """Execute a command in a pod and return (stdout, stderr, returncode)."""
    from kubernetes_asyncio.stream import stream

    api_client = await get_k8s_client()
    core_v1 = client.CoreV1Api(api_client)

    try:
        # stream() creates a websocket connection to the pod
        resp = await stream(
            core_v1.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )

        await resp.run_forever()

        stdout = resp.read_stdout()
        stderr = resp.read_stderr()
        returncode = resp.returncode

        return stdout, stderr, returncode
    except Exception as e:
        logger.error("sandbox_pod_exec_failed", error=str(e))
        raise


async def wait_for_pod_ready(namespace: str, pod_name: str, timeout: int = 300) -> None:
    api_client = await get_k8s_client()
    core_v1 = client.CoreV1Api(api_client)
    start_time = asyncio.get_event_loop().time()

    while asyncio.get_event_loop().time() - start_time < timeout:
        try:
            pod = await core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
            if pod.status.phase == "Running":
                # Check if all containers are ready
                all_ready = True
                for cond in pod.status.conditions or []:
                    if cond.type == "Ready" and cond.status != "True":
                        all_ready = False
                if all_ready:
                    return
            elif pod.status.phase in ["Succeeded", "Failed"]:
                raise RuntimeError(
                    f"Pod {pod_name} exited prematurely with phase {pod.status.phase}"
                )
        except client.ApiException as e:
            if e.status != 404:
                raise
        await asyncio.sleep(1)

    raise TimeoutError(f"Pod {pod_name} not ready after {timeout} seconds")


async def exec_in_pod_stream(
    namespace: str, pod_name: str, command: list[str]
) -> AsyncGenerator[dict[str, str | int], None]:
    """
    Buffered fallback for exec stream.
    In a fully supported SDK, we'd read from the websocket incrementally.
    """
    try:
        stdout, stderr, rc = await exec_in_pod(namespace, pod_name, command)
        if stdout:
            yield {"type": "stdout", "text": stdout}
        if stderr:
            yield {"type": "stderr", "text": stderr}
        yield {"type": "exit", "exit_code": rc}
    except Exception as e:
        yield {"type": "stderr", "text": str(e)}
        yield {"type": "exit", "exit_code": 1}


async def read_file_in_pod(namespace: str, pod_name: str, path: str) -> bytes:
    # use cat and base64 to ensure binary safety
    stdout, stderr, rc = await exec_in_pod(namespace, pod_name, ["cat", path])
    if rc != 0:
        raise FileNotFoundError(f"File {path} not found or unreadable: {stderr}")
    return stdout.encode("utf-8", errors="surrogateescape")


async def write_file_in_pod(
    namespace: str, pod_name: str, path: str, content: bytes
) -> None:
    import base64
    import shlex

    b64_content = base64.b64encode(content).decode("utf-8")
    # Make sure parent directory exists
    dir_path = path.rsplit("/", 1)[0] if "/" in path else ""
    if dir_path:
        await exec_in_pod(namespace, pod_name, ["mkdir", "-p", dir_path])

    stdout, stderr, rc = await exec_in_pod(
        namespace,
        pod_name,
        [
            "sh",
            "-c",
            f"echo {shlex.quote(b64_content)} | base64 -d > {shlex.quote(path)}",
        ],
    )
    if rc != 0:
        raise RuntimeError(f"Failed to write file {path}: {stderr}")


async def list_files_in_pod(namespace: str, pod_name: str, path: str) -> list[str]:
    stdout, stderr, rc = await exec_in_pod(
        namespace, pod_name, ["find", path, "-type", "f"]
    )
    if rc != 0:
        return []
    return [p for p in stdout.splitlines() if p.strip()]


async def delete_file_in_pod(namespace: str, pod_name: str, path: str) -> None:
    await exec_in_pod(namespace, pod_name, ["rm", "-f", path])


async def stat_file_in_pod(namespace: str, pod_name: str, path: str) -> dict:
    stdout, stderr, rc = await exec_in_pod(
        namespace, pod_name, ["stat", "-c", "%F|%s", path]
    )
    if rc != 0:
        raise FileNotFoundError(f"File {path} not found: {stderr}")
    parts = stdout.strip().split("|")
    type_str = "directory" if "directory" in parts[0].lower() else "file"
    return {
        "path": path,
        "type": type_str,
        "size": int(parts[1]) if len(parts) > 1 else 0,
    }
