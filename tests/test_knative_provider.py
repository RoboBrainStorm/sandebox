import pytest
from core.contract import SessionIdentity
from core.utils import get_pod_name, get_service_name


def test_knative_name_derivation():
    identity = SessionIdentity(
        workspace_id="my-test-key-with-A-LOT-of-chars-" * 5, user_id="u", session_id="s"
    )

    pod_name = get_pod_name(identity)
    assert pod_name.startswith("rb-sbx-")
    assert len(pod_name) <= 63
    assert pod_name == pod_name.lower()

    svc_name = get_service_name(identity, 8080)
    assert svc_name.startswith("rb-srv-")
    assert len(svc_name) <= 63
    assert svc_name == svc_name.lower()
