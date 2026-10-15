import pytest
from sandebox_server.app import app
from sandebox import (
    AdminStatsResponse,
    BuildResponse,
    DeploymentResponse,
    ExecutionResult,
    SandboxResponse,
)


def test_openapi_schema_parity():
    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    assert "ExecutionResult" in schemas
    assert set(ExecutionResult.model_fields.keys()) == set(schemas["ExecutionResult"]["properties"].keys())

    assert "SandboxResponse" in schemas
    assert set(SandboxResponse.model_fields.keys()) == set(schemas["SandboxResponse"]["properties"].keys())

    assert "BuildResponse" in schemas
    assert set(BuildResponse.model_fields.keys()) == set(schemas["BuildResponse"]["properties"].keys())

    assert "DeploymentResponse" in schemas
    assert set(DeploymentResponse.model_fields.keys()) == set(schemas["DeploymentResponse"]["properties"].keys())

    assert "AdminStatsResponse" in schemas
    assert set(AdminStatsResponse.model_fields.keys()) == set(schemas["AdminStatsResponse"]["properties"].keys())
