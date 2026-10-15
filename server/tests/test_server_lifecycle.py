from unittest.mock import AsyncMock, patch
import pytest
import httpx
from httpx import ASGITransport

from sandebox_server.app import app


@pytest.fixture
def auth_headers():
    return {"X-API-Key": "sk-sandebox-dev-key"}


@pytest.mark.asyncio
async def test_health_endpoints():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

        resp = await client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_auth_protection():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/sandboxes")
        assert resp.status_code == 401

        resp = await client.get("/v1/sandboxes", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_sandbox_lifecycle(auth_headers):
    transport = ASGITransport(app=app)

    async def mock_stream_chunks(*args, **kwargs):
        yield {"type": "stdout", "text": "hello streaming\n"}

    with patch("core.session.create_sandbox_pod", new_callable=AsyncMock), \
         patch("core.session.wait_for_pod_ready", new_callable=AsyncMock), \
         patch("core.session.ensure_namespace", new_callable=AsyncMock), \
         patch("core.session.get_k8s_client", new_callable=AsyncMock), \
         patch("core.session.delete_pod", new_callable=AsyncMock), \
         patch("core.session.exec_in_pod", new_callable=AsyncMock) as mock_exec, \
         patch("core.session.exec_in_pod_stream", side_effect=mock_stream_chunks):

        mock_exec.return_value = ("hello world\n", "", 0)

        async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
            # 1. Create sandbox
            create_resp = await client.post("/v1/sandboxes", json={"workspace_id": "ws-1", "user_id": "u-1"})
            assert create_resp.status_code == 201
            sbx = create_resp.json()
            session_id = sbx["id"]
            assert sbx["status"] == "ready"

            # 2. List sandboxes
            list_resp = await client.get("/v1/sandboxes")
            assert list_resp.status_code == 200
            assert any(s["id"] == session_id for s in list_resp.json())

            # 3. Exec in sandbox
            exec_resp = await client.post(f"/v1/sandboxes/{session_id}/exec", json={"command": "echo 'hello world'"})
            assert exec_resp.status_code == 200
            assert exec_resp.json()["stdout"] == "hello world\n"
            assert exec_resp.json()["exit_code"] == 0

            # 4. Exec stream
            stream_resp = await client.post(f"/v1/sandboxes/{session_id}/exec-stream", json={"command": "echo stream"})
            assert stream_resp.status_code == 200
            content = stream_resp.text
            assert "hello streaming" in content

            # 5. Stop sandbox
            stop_resp = await client.delete(f"/v1/sandboxes/{session_id}")
            assert stop_resp.status_code == 200
            assert stop_resp.json()["stopped"] is True

            # 6. Verify removed
            get_resp = await client.get(f"/v1/sandboxes/{session_id}")
            assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_stats_and_keys(auth_headers):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as client:
        stats_resp = await client.get("/v1/admin/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert "active_sandboxes" in stats
        assert "runtime_class" in stats

        # Issue key
        key_resp = await client.post("/v1/admin/keys", json={"prefix": "sk-custom"})
        assert key_resp.status_code == 200
        new_key = key_resp.json()["key"]
        assert new_key.startswith("sk-custom-")

        # Test new key works
        test_client_resp = await client.get("/v1/admin/stats", headers={"X-API-Key": new_key})
        assert test_client_resp.status_code == 200
