"""gVisor sandbox provider.

Runs untrusted generated code in a container under the gVisor runtime (`runsc`),
which interposes a user-space kernel between the workload and the host.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile

from .config import SandboxConfig
from .contract import ExecResult


class GvisorSandbox:
    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig.from_env()

    @property
    def image(self) -> str:
        return self.config.image

    @property
    def runtime(self) -> str:
        # If runtime_class is 'gvisor', the docker runtime name is typically 'runsc'
        return (
            "runsc"
            if self.config.runtime_class == "gvisor"
            else self.config.runtime_class
        )

    @property
    def cpus(self) -> str:
        return self.config.cpu_limit

    @property
    def memory(self) -> str:
        # Normalize memory format if needed e.g. 512Mi -> 512m
        mem = self.config.memory_limit
        if mem.endswith("Mi"):
            mem = mem[:-2] + "m"
        elif mem.endswith("Gi"):
            mem = mem[:-2] + "g"
        return mem

    async def run_python(
        self, files: dict[str, str], entry: str, timeout: float = 15.0
    ) -> ExecResult:
        workdir = tempfile.mkdtemp(prefix="sandebox-gvisor-")
        try:
            for name, content in files.items():
                path = os.path.join(workdir, name)
                parent = os.path.dirname(path)
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(content)

            cmd = [
                "docker",
                "run",
                "--rm",
                "--runtime",
                self.runtime,
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--user",
                "65534:65534",  # nobody
                "--cpus",
                self.cpus,
                "--memory",
                self.memory,
                "--pids-limit",
                "128",
                "--tmpfs",
                "/tmp:rw,size=64m",
                "-v",
                f"{workdir}:/work:ro",
                "-w",
                "/work",
                "-e",
                "PYTHONDONTWRITEBYTECODE=1",
                self.image,
                "python",
                "-I",
                "-c",
                entry,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout + 10,  # +10 for container spin-up
                )
            except TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return ExecResult(
                    ok=False, timed_out=True, stderr="execution timed out"
                )

            return ExecResult(
                ok=proc.returncode == 0,
                stdout=out.decode(errors="replace"),
                stderr=err.decode(errors="replace"),
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
