from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..auth import get_active_keys, issue_api_key, verify_api_key
from ..config import get_server_settings, ServerSettings
from .sandboxes import _active_sessions

router = APIRouter(prefix="/v1/admin", tags=["admin"])

_server_start_time = time.time()


class CreateKeyRequest(BaseModel):
    prefix: str = "sk-sbx"


class KeyResponse(BaseModel):
    key: str


class AdminStatsResponse(BaseModel):
    active_sandboxes: int
    uptime_seconds: float
    namespace: str
    runtime_class: str
    image: str


@router.get("/stats", response_model=AdminStatsResponse)
async def get_stats(
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> AdminStatsResponse:
    cfg = settings.sandbox_config
    return AdminStatsResponse(
        active_sandboxes=len(_active_sessions),
        uptime_seconds=time.time() - _server_start_time,
        namespace=cfg.namespace,
        runtime_class=cfg.runtime_class,
        image=cfg.image,
    )


@router.get("/keys", response_model=list[str])
async def list_keys(
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> list[str]:
    # Return masked keys
    keys = get_active_keys(settings)
    return [f"{k[:6]}...{k[-4:]}" if len(k) > 10 else "***" for k in keys]


@router.post("/keys", response_model=KeyResponse)
async def create_key(
    request: CreateKeyRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
) -> KeyResponse:
    key = issue_api_key(prefix=request.prefix)
    return KeyResponse(key=key)
