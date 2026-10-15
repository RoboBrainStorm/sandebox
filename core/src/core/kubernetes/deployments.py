from __future__ import annotations

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)


async def create_deployment(
    api_client: ApiClient,
    namespace: str,
    name: str,
    image: str,
    command: list[str] | None = None,
    port: int = 8080,
    replicas: int = 1,
    env: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
) -> client.V1Deployment:
    apps_v1 = client.AppsV1Api(api_client)
    pod_labels = labels if labels is not None else {"app": name}
    match_labels = labels if labels is not None else {"app": name}
    env_vars = [client.V1EnvVar(name=k, value=v) for k, v in (env or {}).items()]
    container_kwargs = {
        "name": name,
        "image": image,
        "ports": [client.V1ContainerPort(container_port=port)],
        "env": env_vars,
    }
    if command:
        container_kwargs["command"] = command

    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=client.V1ObjectMeta(name=name, namespace=namespace, labels=pod_labels),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(match_labels=match_labels),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=pod_labels),
                spec=client.V1PodSpec(
                    containers=[
                        client.V1Container(**container_kwargs)
                    ]
                ),
            ),
        ),
    )
    result = await apps_v1.create_namespaced_deployment(
        namespace=namespace, body=deployment
    )
    logger.info("k8s_deployment_created", name=name, namespace=namespace)
    return result
