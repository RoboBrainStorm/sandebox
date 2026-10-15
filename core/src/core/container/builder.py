"""BuildKit-based image builder for sandebox containers.

Builds container images using buildkitd and pushes to the configured registry.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import structlog

from ..config import SandboxConfig

logger = structlog.get_logger(__name__)

_RB_RUNNER_SRC = Path(__file__).parent / "rb_runner.py"
_AGENT_RUNNER_SRC = Path(__file__).parent / "agent_runner.py"


class ContainerBuilder:
    def __init__(self, config: SandboxConfig | None = None) -> None:
        self.config = config or SandboxConfig.from_env()

    @property
    def push_registry(self) -> str:
        return self.config.model_registry_push

    @property
    def pull_registry(self) -> str:
        return self.config.model_registry_pull

    @property
    def buildkit_addr(self) -> str:
        return self.config.buildkit_addr

    def build_and_push(
        self, repo_path: str, model_name: str, prefix: str = "sandebox-model"
    ) -> str:
        """
        Build a Docker image from repo_path using buildkitd and push to the registry.
        Returns the pull-side image tag.
        """
        safe_name = model_name.lower().replace("_", "-")
        push_tag = f"{self.push_registry}/{prefix}-{safe_name}:latest"
        pull_tag = f"{self.pull_registry}/{prefix}-{safe_name}:latest"

        if _RB_RUNNER_SRC.exists():
            shutil.copy(_RB_RUNNER_SRC, os.path.join(repo_path, "rb_runner.py"))

        self._build_with_buildctl(repo_path, push_tag)

        logger.info("container_build.done", model=model_name, pull_tag=pull_tag)
        return pull_tag

    def build_and_push_agent(
        self, repo_path: str, agent_name: str, prefix: str = "sandebox-agent"
    ) -> str:
        """
        Build an agent image from repo_path and push to the registry.
        """
        safe_name = agent_name.lower().replace("_", "-")
        push_tag = f"{self.push_registry}/{prefix}-{safe_name}:latest"
        pull_tag = f"{self.pull_registry}/{prefix}-{safe_name}:latest"

        if _AGENT_RUNNER_SRC.exists():
            shutil.copy(_AGENT_RUNNER_SRC, os.path.join(repo_path, "agent_runner.py"))

        self._build_with_buildctl(repo_path, push_tag)

        logger.info("container_build.done", agent=agent_name, pull_tag=pull_tag)
        return pull_tag

    def _build_with_buildctl(self, repo_path: str, tag: str) -> None:
        cmd = [
            "buildctl",
            "--addr",
            self.buildkit_addr,
            "build",
            "--frontend",
            "dockerfile.v0",
            "--local",
            f"context={repo_path}",
            "--local",
            f"dockerfile={repo_path}",
            "--output",
            f"type=image,name={tag},push=true",
        ]
        logger.info("container_build.buildctl", addr=self.buildkit_addr, tag=tag)
        self._run(cmd, "buildctl build+push")

    def _run(self, cmd: list[str], step: str) -> None:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(
                    f"{step} failed (exit {result.returncode}):\n{result.stderr[-2000:]}"
                )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"{step} timed out after 120 seconds. Is k3s or buildkit running?"
            ) from exc
