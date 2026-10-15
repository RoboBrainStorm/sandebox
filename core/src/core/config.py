from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class SandboxConfig:
    """Configuration injected into the sandebox core engine."""

    namespace: str = "sandebox"
    image: str = "python:3.12-slim"
    runtime_class: str = "gvisor"
    cpu_limit: str = "1"
    memory_limit: str = "512Mi"
    min_scale: int = 0
    max_scale: int = 1
    execution_timeout: int = 300
    model_registry_push: str = "sandebox-registry:5050"
    model_registry_pull: str = "sandebox-registry:5050"
    buildkit_addr: str = "tcp://localhost:1234"

    @classmethod
    def from_env(cls) -> SandboxConfig:
        return cls(
            namespace=os.environ.get(
                "SANDEBOX_NAMESPACE", os.environ.get("KNATIVE_NAMESPACE", "sandebox")
            ),
            image=os.environ.get(
                "SANDEBOX_IMAGE", os.environ.get("KNATIVE_IMAGE", "python:3.12-slim")
            ),
            runtime_class=os.environ.get(
                "SANDEBOX_RUNTIME_CLASS",
                os.environ.get("KNATIVE_RUNTIME_CLASS", "gvisor"),
            ),
            cpu_limit=os.environ.get(
                "SANDEBOX_CPU_LIMIT", os.environ.get("KNATIVE_CPU_LIMIT", "1")
            ),
            memory_limit=os.environ.get(
                "SANDEBOX_MEMORY_LIMIT", os.environ.get("KNATIVE_MEMORY_LIMIT", "512Mi")
            ),
            min_scale=int(
                os.environ.get(
                    "SANDEBOX_MIN_SCALE", os.environ.get("KNATIVE_MIN_SCALE", "0")
                )
            ),
            max_scale=int(
                os.environ.get(
                    "SANDEBOX_MAX_SCALE", os.environ.get("KNATIVE_MAX_SCALE", "1")
                )
            ),
            execution_timeout=int(
                os.environ.get(
                    "SANDEBOX_EXECUTION_TIMEOUT",
                    os.environ.get("KNATIVE_EXECUTION_TIMEOUT", "300"),
                )
            ),
            model_registry_push=os.environ.get(
                "SANDEBOX_REGISTRY_PUSH",
                os.environ.get("MODEL_REGISTRY_PUSH", "sandebox-registry:5050"),
            ),
            model_registry_pull=os.environ.get(
                "SANDEBOX_REGISTRY_PULL",
                os.environ.get("MODEL_REGISTRY_PULL", "sandebox-registry:5050"),
            ),
            buildkit_addr=os.environ.get(
                "SANDEBOX_BUILDKIT_ADDR",
                os.environ.get("BUILDKIT_ADDR", "tcp://localhost:1234"),
            ),
        )
