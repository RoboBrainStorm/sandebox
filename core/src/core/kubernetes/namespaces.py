from __future__ import annotations

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)


async def ensure_namespace(
    api_client: ApiClient, name: str, labels: dict[str, str] | None = None
) -> None:
    core_v1 = client.CoreV1Api(api_client)
    ns = client.V1Namespace(
        api_version="v1",
        kind="Namespace",
        metadata=client.V1ObjectMeta(name=name, labels=labels or {}),
    )
    try:
        await core_v1.create_namespace(body=ns)
        logger.info("k8s_namespace_created", name=name)
    except client.exceptions.ApiException as e:
        if e.status == 409:
            pass  # already exists
        else:
            raise
