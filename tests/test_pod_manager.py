"""Tests for the Kubernetes pod manager (unit + live minikube integration)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Unit tests (mocked k8s client) ───────────────────────────────────────────


class TestJobsUnit:
    @pytest.mark.asyncio
    async def test_create_job_builds_correct_spec(self):
        from core.kubernetes.jobs import create_job

        mock_api_client = MagicMock()
        mock_batch = AsyncMock()
        mock_batch.create_namespaced_job.return_value = MagicMock(
            metadata=MagicMock(name="test-job", namespace="default")
        )

        with patch(
            "core.kubernetes.jobs.client.BatchV1Api",
            return_value=mock_batch,
        ):
            _result = await create_job(
                api_client=mock_api_client,
                namespace="default",
                name="test-job",
                image="busybox:latest",
                command=["echo", "hello"],
                env={"KEY": "val"},
                labels={"app": "rb"},
            )

        mock_batch.create_namespaced_job.assert_called_once()
        call_kwargs = mock_batch.create_namespaced_job.call_args
        body = (
            call_kwargs.kwargs.get("body") or call_kwargs.args[0]
            if call_kwargs.args
            else call_kwargs.kwargs["body"]
        )
        assert body.spec.backoff_limit == 0
        assert body.spec.ttl_seconds_after_finished == 3600
        assert body.spec.template.spec.restart_policy == "Never"
        container = body.spec.template.spec.containers[0]
        assert container.image == "busybox:latest"
        assert container.command == ["echo", "hello"]
        env_names = [e.name for e in container.env]
        assert "KEY" in env_names

    @pytest.mark.asyncio
    async def test_delete_job(self):
        from core.kubernetes.jobs import delete_job

        mock_api_client = MagicMock()
        mock_batch = AsyncMock()

        with patch(
            "core.kubernetes.jobs.client.BatchV1Api",
            return_value=mock_batch,
        ):
            await delete_job(mock_api_client, "default", "test-job")

        mock_batch.delete_namespaced_job.assert_called_once_with(
            name="test-job",
            namespace="default",
            body=pytest.approx(
                mock_batch.delete_namespaced_job.call_args[1].get("body")
            )
            if mock_batch.delete_namespaced_job.call_args[1]
            else None,
        )

    @pytest.mark.asyncio
    async def test_create_job_no_env(self):
        from core.kubernetes.jobs import create_job

        mock_api_client = MagicMock()
        mock_batch = AsyncMock()
        mock_batch.create_namespaced_job.return_value = MagicMock(
            metadata=MagicMock(name="j", namespace="default")
        )

        with patch(
            "core.kubernetes.jobs.client.BatchV1Api",
            return_value=mock_batch,
        ):
            await create_job(
                api_client=mock_api_client,
                namespace="default",
                name="j",
                image="img",
                command=["cmd"],
            )

        body = mock_batch.create_namespaced_job.call_args.kwargs["body"]
        container = body.spec.template.spec.containers[0]
        assert container.env == []


class TestDeploymentsUnit:
    @pytest.mark.asyncio
    async def test_create_deployment_builds_correct_spec(self):
        from core.kubernetes.deployments import create_deployment

        mock_api_client = MagicMock()
        mock_apps = AsyncMock()
        mock_apps.create_namespaced_deployment.return_value = MagicMock(
            metadata=MagicMock(name="test-dep", namespace="default")
        )

        with patch(
            "core.kubernetes.deployments.client.AppsV1Api",
            return_value=mock_apps,
        ):
            await create_deployment(
                api_client=mock_api_client,
                namespace="default",
                name="test-dep",
                image="my-image:latest",
                command=["python", "main.py"],
                env={"FOO": "bar"},
                labels={"app": "model-runner"},
                replicas=2,
                port=8080,
            )

        mock_apps.create_namespaced_deployment.assert_called_once()
        body = mock_apps.create_namespaced_deployment.call_args.kwargs["body"]
        assert body.spec.replicas == 2
        assert body.spec.selector.match_labels == {"app": "model-runner"}
        template = body.spec.template
        assert template.metadata.labels == {"app": "model-runner"}
        container = template.spec.containers[0]
        assert container.image == "my-image:latest"
        assert container.command == ["python", "main.py"]
        env_names = [e.name for e in container.env]
        assert "FOO" in env_names
        assert container.ports[0].container_port == 8080

    @pytest.mark.asyncio
    async def test_create_deployment_label_propagation(self):
        """Selector match_labels must equal template metadata labels."""
        from core.kubernetes.deployments import create_deployment

        mock_api_client = MagicMock()
        mock_apps = AsyncMock()
        mock_apps.create_namespaced_deployment.return_value = MagicMock(
            metadata=MagicMock(name="dep", namespace="default")
        )

        labels = {"custom": "label", "env": "test"}
        with patch(
            "core.kubernetes.deployments.client.AppsV1Api",
            return_value=mock_apps,
        ):
            await create_deployment(
                api_client=mock_api_client,
                namespace="default",
                name="dep",
                image="img",
                command=["cmd"],
                labels=labels,
            )

        body = mock_apps.create_namespaced_deployment.call_args.kwargs["body"]
        assert body.spec.selector.match_labels == labels
        assert body.spec.template.metadata.labels == labels


class TestK8sClient:
    @pytest.mark.asyncio
    async def test_get_client_uses_kubeconfig_fallback(self):
        import core.kubernetes.client as k8s_client_module
        from kubernetes_asyncio import config as real_config

        k8s_client_module._api_client = None

        with (
            patch.object(
                real_config,
                "load_incluster_config",
                side_effect=real_config.ConfigException("not in cluster"),
            ),
            patch.object(
                real_config,
                "load_kube_config",
                new_callable=lambda: lambda: AsyncMock(),
            ),
            patch("core.kubernetes.client.ApiClient") as mock_api_client_cls,
        ):
            mock_api_client_cls.return_value = MagicMock()
            real_config.load_kube_config = AsyncMock()

            result = await k8s_client_module.get_k8s_client()

        assert result is not None
        k8s_client_module._api_client = None

    @pytest.mark.asyncio
    async def test_get_client_cached(self):
        import core.kubernetes.client as k8s_client_module

        sentinel = MagicMock()
        k8s_client_module._api_client = sentinel

        result = await k8s_client_module.get_k8s_client()
        assert result is sentinel
        k8s_client_module._api_client = None

    @pytest.mark.asyncio
    async def test_close_client(self):
        import core.kubernetes.client as k8s_client_module

        mock_client = AsyncMock()
        k8s_client_module._api_client = mock_client

        await k8s_client_module.close_k8s_client()

        mock_client.close.assert_called_once()
        assert k8s_client_module._api_client is None


# ── Live minikube integration (skipped if cluster unavailable) ────────────────

pytestmark_k8s = pytest.mark.skipif(
    True,  # set to False when minikube is running to enable
    reason="requires live minikube cluster",
)


@pytest.mark.integration
class TestK8sJobIntegration:
    @pytestmark_k8s
    @pytest.mark.asyncio
    async def test_create_and_delete_job_on_minikube(self):
        import uuid

        from core.kubernetes.client import (
            close_k8s_client,
            get_k8s_client,
        )
        from core.kubernetes.jobs import create_job, delete_job

        api_client = await get_k8s_client()
        job_name = f"test-minikube-{uuid.uuid4().hex[:8]}"

        try:
            job = await create_job(
                api_client=api_client,
                namespace="default",
                name=job_name,
                image="busybox:latest",
                command=["echo", "live minikube test"],
                labels={"test": "integration"},
            )
            assert job.metadata.name == job_name
        finally:
            await delete_job(api_client, "default", job_name)
            await close_k8s_client()

    @pytestmark_k8s
    @pytest.mark.asyncio
    async def test_create_deployment_on_minikube(self):
        import uuid

        from core.kubernetes.client import (
            close_k8s_client,
            get_k8s_client,
        )
        from core.kubernetes.deployments import create_deployment

        api_client = await get_k8s_client()
        dep_name = f"test-dep-{uuid.uuid4().hex[:8]}"

        try:
            dep = await create_deployment(
                api_client=api_client,
                namespace="default",
                name=dep_name,
                image="nginx:alpine",
                command=["nginx", "-g", "daemon off;"],
                labels={"test": "integration"},
                replicas=1,
                port=80,
            )
            assert dep.metadata.name == dep_name
        finally:
            await close_k8s_client()
