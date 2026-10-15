from __future__ import annotations

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)


async def create_service(
    api_client: ApiClient,
    namespace: str,
    name: str,
    port: int = 8080,
    selector: dict[str, str] | None = None,
) -> client.V1Service:
    core_v1 = client.CoreV1Api(api_client)
    svc = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=client.V1ObjectMeta(name=name, namespace=namespace),
        spec=client.V1ServiceSpec(
            selector=selector or {"app": name},
            ports=[client.V1ServicePort(port=port, target_port=port)],
            type="ClusterIP",
        ),
    )
    result = await core_v1.create_namespaced_service(namespace=namespace, body=svc)
    logger.info("k8s_service_created", name=name, namespace=namespace)
    return result
