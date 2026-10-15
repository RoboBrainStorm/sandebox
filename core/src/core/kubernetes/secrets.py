from __future__ import annotations

import base64

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)


async def create_secret(
    api_client: ApiClient,
    namespace: str,
    name: str,
    data: dict[str, str],
) -> client.V1Secret:
    core_v1 = client.CoreV1Api(api_client)
    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}
    secret = client.V1Secret(
        api_version="v1",
        kind="Secret",
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        data=encoded,
    )
    result = await core_v1.create_namespaced_secret(namespace=namespace, body=secret)
    logger.info("k8s_secret_created", name=name, namespace=namespace)
    return result


async def delete_secret(api_client: ApiClient, namespace: str, name: str) -> None:
    core_v1 = client.CoreV1Api(api_client)
    await core_v1.delete_namespaced_secret(name=name, namespace=namespace)
    logger.info("k8s_secret_deleted", name=name, namespace=namespace)
