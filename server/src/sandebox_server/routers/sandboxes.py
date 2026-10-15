from __future__ import annotations

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core import (
    ExecutionResult,
    GvisorSandbox,
    KnativeProvider,
    KnativeSandboxSession,
    SandboxConfig,
    SessionIdentity,
)
from ..auth import verify_api_key
from ..config import get_server_settings, ServerSettings

router = APIRouter(prefix="/v1/sandboxes", tags=["sandboxes"])

# Global session tracker
_active_sessions: dict[str, KnativeSandboxSession] = {}


class CreateSandboxRequest(BaseModel):
    workspace_id: str = "default"
    user_id: str = "default"
    session_id: str | None = None
    image: str | None = None
    cpu_limit: str | None = None
    memory_limit: str | None = None


class SandboxResponse(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    pod_name: str
    status: str


class ExecRequest(BaseModel):
    command: str
    env: dict[str, str] | None = None


class RunRequest(BaseModel):
    command: str | None = None
    code: str | None = None
    language: str = "bash"  # "python", "node", "bash"
    files: dict[str, str] | None = None
    use_gvisor: bool = False


@router.post("", response_model=SandboxResponse, status_code=status.HTTP_201_CREATED)
async def create_sandbox(
    request: CreateSandboxRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> SandboxResponse:
    session_id = request.session_id or uuid.uuid4().hex
    identity = SessionIdentity(
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        session_id=session_id,
    )

    cfg = settings.sandbox_config
    if request.image or request.cpu_limit or request.memory_limit:
        cfg = SandboxConfig(
            namespace=cfg.namespace,
            image=request.image or cfg.image,
            runtime_class=cfg.runtime_class,
            cpu_limit=request.cpu_limit or cfg.cpu_limit,
            memory_limit=request.memory_limit or cfg.memory_limit,
            min_scale=cfg.min_scale,
            max_scale=cfg.max_scale,
            execution_timeout=cfg.execution_timeout,
            model_registry_push=cfg.model_registry_push,
            model_registry_pull=cfg.model_registry_pull,
            buildkit_addr=cfg.buildkit_addr,
        )

    session = KnativeSandboxSession(identity, config=cfg)
    try:
        await session.start()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start sandbox pod: {exc}",
        ) from exc

    _active_sessions[session_id] = session
    return SandboxResponse(
        id=session_id,
        workspace_id=request.workspace_id,
        user_id=request.user_id,
        pod_name=session.pod_name,
        status="ready",
    )


@router.get("", response_model=list[SandboxResponse])
async def list_sandboxes(
    _auth: Annotated[str, Depends(verify_api_key)],
) -> list[SandboxResponse]:
    return [
        SandboxResponse(
            id=s.identity.session_id,
            workspace_id=s.identity.workspace_id,
            user_id=s.identity.user_id,
            pod_name=s.pod_name,
            status="ready",
        )
        for s in _active_sessions.values()
    ]


@router.get("/{session_id}", response_model=SandboxResponse)
async def get_sandbox(
    session_id: str,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> SandboxResponse:
    session = _active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sandbox {session_id} not found")
    return SandboxResponse(
        id=session.identity.session_id,
        workspace_id=session.identity.workspace_id,
        user_id=session.identity.user_id,
        pod_name=session.pod_name,
        status="ready",
    )


@router.post("/{session_id}/exec", response_model=ExecutionResult)
async def exec_in_sandbox(
    session_id: str,
    request: ExecRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> ExecutionResult:
    session = _active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sandbox {session_id} not found")

    return await session.exec(command=request.command, env=request.env)


@router.post("/{session_id}/exec-stream")
async def exec_stream_in_sandbox(
    session_id: str,
    request: ExecRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> StreamingResponse:
    session = _active_sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sandbox {session_id} not found")

    async def event_generator():
        async for event in session.exec_stream(command=request.command, env=request.env):
            yield f"data: {json.dumps({'type': event.type, 'data': event.data})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/{session_id}", status_code=status.HTTP_200_OK)
async def stop_sandbox(
    session_id: str,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> dict[str, Any]:
    session = _active_sessions.pop(session_id, None)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sandbox {session_id} not found")

    await session.stop()
    return {"id": session_id, "stopped": True}


@router.post("/run", response_model=ExecutionResult)
async def run_one_shot(
    request: RunRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> ExecutionResult:
    cfg = settings.sandbox_config

    if request.use_gvisor and request.language == "python" and request.code:
        gvisor = GvisorSandbox(config=cfg)
        files = request.files or {"main.py": request.code}
        exec_res = await gvisor.run_python(files=files, entry="import main")
        return ExecutionResult(
            exit_code=exec_res.exit_code,
            stdout=exec_res.stdout,
            stderr=exec_res.stderr,
        )

    provider = KnativeProvider(config=cfg)
    if request.language == "python" and request.code:
        return await provider.run_python(request.code)
    elif request.language == "node" and request.code:
        return await provider.run_node(request.code)
    elif request.command:
        return await provider.run_command(request.command)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Must provide command or code")
