from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from core import ContainerBuilder

from ..auth import verify_api_key
from ..config import ServerSettings, get_server_settings

router = APIRouter(prefix="/v1/builds", tags=["builds"])

_builds: dict[str, dict[str, Any]] = {}


class BuildRequest(BaseModel):
    repo_path: str
    target_name: str
    is_agent: bool = False
    prefix: str = "sandebox"


class BuildResponse(BaseModel):
    id: str
    target_name: str
    image_tag: str
    status: str


@router.post("", response_model=BuildResponse, status_code=status.HTTP_201_CREATED)
async def create_build(
    request: BuildRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> BuildResponse:
    build_id = f"build-{uuid.uuid4().hex[:8]}"
    builder = ContainerBuilder(config=settings.sandbox_config)

    try:
        if request.is_agent:
            pull_tag = builder.build_and_push_agent(
                repo_path=request.repo_path,
                agent_name=request.target_name,
                prefix=request.prefix,
            )
        else:
            pull_tag = builder.build_and_push(
                repo_path=request.repo_path,
                model_name=request.target_name,
                prefix=request.prefix,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Build failed: {exc}",
        ) from exc

    resp = BuildResponse(
        id=build_id,
        target_name=request.target_name,
        image_tag=pull_tag,
        status="completed",
    )
    _builds[build_id] = resp.model_dump()
    return resp


@router.get("", response_model=list[BuildResponse])
async def list_builds(
    _auth: Annotated[str, Depends(verify_api_key)],
) -> list[BuildResponse]:
    return [BuildResponse(**b) for b in _builds.values()]


@router.get("/{build_id}", response_model=BuildResponse)
async def get_build(
    build_id: str,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> BuildResponse:
    b = _builds.get(build_id)
    if not b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Build {build_id} not found"
        )
    return BuildResponse(**b)
