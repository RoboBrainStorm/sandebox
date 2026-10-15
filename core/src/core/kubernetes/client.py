from __future__ import annotations

import structlog
from kubernetes_asyncio import config
from kubernetes_asyncio.client import ApiClient

logger = structlog.get_logger(__name__)

_api_client: ApiClient | None = None


async def get_k8s_client() -> ApiClient:
    global _api_client
    if _api_client is not None:
        return _api_client
    try:
        config.load_incluster_config()
        logger.info("k8s_client_in_cluster")
    except config.ConfigException:
        await config.load_kube_config()
        logger.info("k8s_client_kubeconfig")
    _api_client = ApiClient()
    return _api_client


async def close_k8s_client() -> None:
    global _api_client
    if _api_client:
        await _api_client.close()
        _api_client = None
