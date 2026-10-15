from __future__ import annotations

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)


async def create_job(
    api_client: ApiClient,
    namespace: str,
    name: str,
    image: str,
    command: list[str],
    env: dict[str, str] | None = None,
    labels: dict[str, str] | None = None,
) -> client.V1Job:
    batch_v1 = client.BatchV1Api(api_client)
    env_vars = [client.V1EnvVar(name=k, value=v) for k, v in (env or {}).items()]
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=name, namespace=namespace, labels=labels or {}
        ),
        spec=client.V1JobSpec(
            backoff_limit=0,
            ttl_seconds_after_finished=3600,
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    restart_policy="Never",
                    containers=[
                        client.V1Container(
                            name="worker", image=image, command=command, env=env_vars
                        )
                    ],
                )
            ),
        ),
    )
    result = await batch_v1.create_namespaced_job(namespace=namespace, body=job)
    logger.info("k8s_job_created", name=name, namespace=namespace)
    return result


async def delete_job(api_client: ApiClient, namespace: str, name: str) -> None:
    batch_v1 = client.BatchV1Api(api_client)
    await batch_v1.delete_namespaced_job(
        name=name,
        namespace=namespace,
        body=client.V1DeleteOptions(propagation_policy="Foreground"),
    )
    logger.info("k8s_job_deleted", name=name, namespace=namespace)
