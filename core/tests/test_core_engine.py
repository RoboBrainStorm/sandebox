from pathlib import Path
import pytest

from core import (
    ContainerBuilder,
    GvisorSandbox,
    KnativeProvider,
    KnativeSandboxSession,
    SandboxConfig,
    SessionIdentity,
)
from core.utils import get_pod_name, get_service_name


def test_name_derivation():
    identity = SessionIdentity(
        workspace_id="test-workspace-id-with-a-lot-of-characters",
        user_id="user1",
        session_id="session1",
    )
    pod_name = get_pod_name(identity)
    assert pod_name.startswith("rb-sbx-")
    assert len(pod_name) <= 63
    assert pod_name == pod_name.lower()

    svc_name = get_service_name(identity, 8080)
    assert svc_name.startswith("rb-srv-")
    assert len(svc_name) <= 63
    assert svc_name == svc_name.lower()


def test_config_injection():
    config = SandboxConfig(
        namespace="custom-sandebox",
        image="python:3.12-alpine",
        runtime_class="gvisor-custom",
        cpu_limit="2",
        memory_limit="1Gi",
        min_scale=1,
        max_scale=5,
        execution_timeout=600,
        model_registry_push="registry.example.com:5000",
        model_registry_pull="registry.example.com:5000",
        buildkit_addr="tcp://buildkit.example.com:1234",
    )

    provider = KnativeProvider(config=config)
    assert provider.config.namespace == "custom-sandebox"
    assert provider.config.runtime_class == "gvisor-custom"

    identity = SessionIdentity(workspace_id="ws", user_id="u", session_id="s")
    session = KnativeSandboxSession(identity, config=config)
    assert session.namespace == "custom-sandebox"
    assert session.image == "python:3.12-alpine"
    assert session.cpus == "2"
    assert session.memory == "1Gi"

    gvisor = GvisorSandbox(config=config)
    assert gvisor.image == "python:3.12-alpine"
    assert gvisor.runtime == "gvisor-custom"
    assert gvisor.cpus == "2"
    assert gvisor.memory == "1g"

    builder = ContainerBuilder(config=config)
    assert builder.push_registry == "registry.example.com:5000"
    assert builder.buildkit_addr == "tcp://buildkit.example.com:1234"


def test_no_app_imports_in_core():
    core_src = Path(__file__).parent.parent / "src" / "core"
    assert core_src.exists()

    violating_files = []
    for py_file in core_src.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "from app" in content or "import app." in content:
            violating_files.append(str(py_file))

    assert violating_files == [], f"Found forbidden app.* imports in core modules: {violating_files}"
