from __future__ import annotations

import structlog
from kubernetes_asyncio import client
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)

KNATIVE_GROUP = "serving.knative.dev"
KNATIVE_VERSION = "v1"


async def create_knative_service(
    api_client: ApiClient,
    namespace: str,
    name: str,
    image: str,
    env: dict[str, str] | None = None,
    command: list[str] | None = None,
    min_scale: int = 0,
    max_scale: int = 10,
) -> dict:
    custom = client.CustomObjectsApi(api_client)
    env_vars = [{"name": k, "value": v} for k, v in (env or {}).items()]
    container: dict = {"image": image, "env": env_vars}
    if command:
        container["command"] = command
    body = {
        "apiVersion": f"{KNATIVE_GROUP}/{KNATIVE_VERSION}",
        "kind": "Service",
        "metadata": {"name": name, "namespace": namespace},
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "autoscaling.knative.dev/min-scale": str(min_scale),
                        "autoscaling.knative.dev/max-scale": str(max_scale),
                    }
                },
                "spec": {"containers": [container]},
            }
        },
    }
    result = await custom.create_namespaced_custom_object(
        group=KNATIVE_GROUP,
        version=KNATIVE_VERSION,
        namespace=namespace,
        plural="services",
        body=body,
    )
    logger.info("knative_service_created", name=name, namespace=namespace)
    return result


async def deploy_knative_service(
    namespace: str,
    name: str,
    image: str,
    env: dict[str, str] | None = None,
    command: list[str] | None = None,
    min_scale: int = 0,
    max_scale: int = 10,
) -> str:
    """
    Load kube config (in-cluster, else local kubeconfig), create the Knative
    Service, and return its in-cluster URL. Mirrors model_run_service's config
    loading so callers don't manage the ApiClient lifecycle.
    """
    from kubernetes_asyncio import config as k8s_config

    try:
        k8s_config.load_incluster_config()
    except Exception:
        await k8s_config.load_kube_config()

    async with ApiClient() as api_client:
        result = await create_knative_service(
            api_client,
            namespace=namespace,
            name=name,
            image=image,
            env=env,
            command=command,
            min_scale=min_scale,
            max_scale=max_scale,
        )

    # Knative populates status.url asynchronously; fall back to the conventional
    # internal DNS name if it isn't ready yet.
    url = (result.get("status") or {}).get("url")
    if not url:
        url = f"http://{name}.{namespace}.svc.cluster.local"
    return url


async def delete_knative_service(
    api_client: ApiClient, namespace: str, name: str
) -> None:
    custom = client.CustomObjectsApi(api_client)
    try:
        await custom.delete_namespaced_custom_object(
            group=KNATIVE_GROUP,
            version=KNATIVE_VERSION,
            namespace=namespace,
            plural="services",
            name=name,
        )
        logger.info("knative_service_deleted", name=name, namespace=namespace)
    except client.exceptions.ApiException as e:
        if e.status != 404:
            logger.error("knative_service_delete_failed", error=str(e))
            raise


async def get_knative_service(
    api_client: ApiClient, namespace: str, name: str
) -> dict | None:
    custom = client.CustomObjectsApi(api_client)
    try:
        res = await custom.get_namespaced_custom_object(
            group=KNATIVE_GROUP,
            version=KNATIVE_VERSION,
            namespace=namespace,
            plural="services",
            name=name,
        )
        return res
    except client.exceptions.ApiException as e:
        if e.status == 404:
            return None
        logger.error("knative_service_get_failed", error=str(e))
        raise
