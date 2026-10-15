from __future__ import annotations

from typing import Annotated, Any

from core.kubernetes.client import get_k8s_client
from core.kubernetes.knative import (
    delete_knative_service,
    deploy_knative_service,
    get_knative_service,
)
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..auth import verify_api_key
from ..config import ServerSettings, get_server_settings

router = APIRouter(prefix="/v1/deployments", tags=["deployments"])


class DeploymentRequest(BaseModel):
    name: str
    image: str
    env: dict[str, str] | None = None
    command: list[str] | None = None
    namespace: str | None = None
    min_scale: int | None = None
    max_scale: int | None = None


class DeploymentResponse(BaseModel):
    name: str
    namespace: str
    url: str
    status: str


@router.post("", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    request: DeploymentRequest,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
) -> DeploymentResponse:
    ns = request.namespace or settings.sandbox_config.namespace
    min_s = (
        request.min_scale
        if request.min_scale is not None
        else settings.sandbox_config.min_scale
    )
    max_s = (
        request.max_scale
        if request.max_scale is not None
        else settings.sandbox_config.max_scale
    )

    try:
        url = await deploy_knative_service(
            namespace=ns,
            name=request.name,
            image=request.image,
            env=request.env,
            command=request.command,
            min_scale=min_s,
            max_scale=max_s,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deployment failed: {exc}",
        ) from exc

    return DeploymentResponse(
        name=request.name,
        namespace=ns,
        url=url,
        status="ready",
    )


@router.get("/{name}", response_model=DeploymentResponse)
async def get_deployment(
    name: str,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
    namespace: str | None = None,
) -> DeploymentResponse:
    ns = namespace or settings.sandbox_config.namespace
    api_client = await get_k8s_client()
    try:
        res = await get_knative_service(api_client, ns, name)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    if not res:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment {name} not found in {ns}",
        )

    url = (res.get("status") or {}).get(
        "url"
    ) or f"http://{name}.{ns}.svc.cluster.local"
    return DeploymentResponse(
        name=name,
        namespace=ns,
        url=url,
        status="ready",
    )


@router.delete("/{name}", status_code=status.HTTP_200_OK)
async def remove_deployment(
    name: str,
    _auth: Annotated[str, Depends(verify_api_key)],
    settings: Annotated[ServerSettings, Depends(get_server_settings)],
    namespace: str | None = None,
) -> dict[str, Any]:
    ns = namespace or settings.sandbox_config.namespace
    api_client = await get_k8s_client()
    try:
        await delete_knative_service(api_client, ns, name)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    return {"name": name, "deleted": True}
